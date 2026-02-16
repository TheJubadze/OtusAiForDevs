"""
Corrective RAG: Utilities for ChromaDB and Ollama.
"""

import os
import re
import sys
import time
import chromadb
import chromadb.utils.embedding_functions as ef
import ollama
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

try:
    import snowballstemmer
    _stemmer_lang = os.environ.get("STEMMER_LANG", "russian")
    _stemmer = snowballstemmer.stemmer(_stemmer_lang)
    HAS_STEMMER = True
except ImportError:
    _stemmer = None
    HAS_STEMMER = False

# Text file extensions to index (code, docs, config)
TEXT_EXTENSIONS = {
    ".md", ".txt", ".rst", ".adoc",
    ".py", ".cs", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rb", ".rs", ".cpp", ".c", ".h", ".hpp", ".kt", ".swift",
    ".csx", ".vb", ".fs", ".fsx",
    ".csproj", ".vbproj", ".fsproj", ".sln", ".props", ".targets",
    ".razor", ".cshtml", ".xaml",
    ".resx", ".config", ".nuspec", ".runsettings", ".ruleset", ".editorconfig",
    ".sql", ".graphql",
    ".html", ".css", ".scss", ".less", ".vue", ".svelte",
    ".yaml", ".yml", ".json", ".xml", ".toml", ".ini", ".cfg", ".conf",
    ".sh", ".bash", ".bat", ".ps1", ".psm1",
    ".dockerfile", ".tf", ".hcl",
    ".env", ".properties", ".gradle",
    ".csv",
}

# Directories to skip during indexing
SKIP_DIRS = {
    "node_modules", "bin", "obj", "debug", "release",
    ".git", ".svn", ".hg",
    ".vs", ".idea", ".vscode",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    "packages", "testresults",
    "dist", "build", "out", "target",
    ".nuget", ".terraform",
    "coverage", "logs",
}

# Filename patterns to skip (generated/minified files)
SKIP_SUFFIXES = (
    ".designer.cs", ".generated.cs", ".g.cs", ".g.i.cs",
    ".assemblyinfo.cs", ".globalusings.g.cs",
    ".min.js", ".min.css", ".bundle.js", ".chunk.js",
    "-lock.json",
)
SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "composer.lock", "gemfile.lock", "poetry.lock",
    ".ds_store", "thumbs.db",
}

# Max file size to index (bytes) — larger files are usually generated
MAX_FILE_SIZE = 100 * 1024  # 100 KB


# Default configuration (with env var support for Docker)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_OLLAMA_URL = f"{OLLAMA_HOST}/api/embeddings"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:3b")
DEFAULT_CHROMA_PATH = os.environ.get("CHROMA_PATH", "./chroma_db")
DEFAULT_COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "documents")
DEFAULT_CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
DEFAULT_CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "100"))
DEFAULT_VECTOR_WEIGHT = float(os.environ.get("VECTOR_WEIGHT", "0.3"))


class VectorStore:
    """ChromaDB wrapper for document storage and retrieval."""

    def __init__(
        self,
        chroma_path: str = DEFAULT_CHROMA_PATH,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ):
        self.chroma_path = chroma_path
        self.collection_name = collection_name

        self.embedding_function = ef.OllamaEmbeddingFunction(
            url=ollama_url,
            model_name=embed_model,
        )

        self.client = chromadb.PersistentClient(path=chroma_path)
        self._collection = None
        self._bm25_index = None
        self._bm25_docs = None
        self._bm25_metas = None

    @property
    def collection(self):
        """Get or create the collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index_folder(
        self,
        folder_path: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        reset: bool = False,
    ) -> Dict[str, Any]:
        """Index all documents in a folder."""

        if reset:
            try:
                self.client.delete_collection(self.collection_name)
                self._collection = None
            except Exception:
                pass

        def _ts(start: float) -> str:
            elapsed = int(time.time() - start)
            if elapsed < 3600:
                m, s = divmod(elapsed, 60)
                return f"[{m:02d}:{s:02d}]"
            h, remainder = divmod(elapsed, 3600)
            m, s = divmod(remainder, 60)
            return f"[{h}:{m:02d}:{s:02d}]"

        t0 = time.time()

        # Collect text files, skipping irrelevant directories
        print(f"  {_ts(t0)} Сканирую файлы...", end="", flush=True)
        files = []
        for file_path in Path(folder_path).rglob("*"):
            if not file_path.is_file():
                continue
            # Skip files inside excluded directories
            parts_lower = {p.lower() for p in file_path.relative_to(folder_path).parts[:-1]}
            if parts_lower & SKIP_DIRS:
                continue
            if file_path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            # Skip generated/minified files
            name_lower = file_path.name.lower()
            if name_lower in SKIP_FILENAMES:
                continue
            if any(name_lower.endswith(s) for s in SKIP_SUFFIXES):
                continue
            # Skip large files (likely generated)
            try:
                if file_path.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            files.append(file_path)
        print(f" найдено {len(files)} файлов")

        # Load documents (try UTF-8 first, then autodetect)
        documents = []
        errors = 0
        for i, file_path in enumerate(files, 1):
            if i % 200 == 0 or i == len(files):
                print(f"  {_ts(t0)} Загрузка: {i}/{len(files)}", flush=True)
            try:
                loader = TextLoader(str(file_path), encoding="utf-8")
                documents.extend(loader.load())
            except (UnicodeDecodeError, RuntimeError):
                try:
                    loader = TextLoader(str(file_path), autodetect_encoding=True)
                    documents.extend(loader.load())
                except Exception:
                    errors += 1
            except Exception:
                errors += 1
        if errors:
            print(f"  {_ts(t0)} Пропущено (ошибки чтения): {errors}")

        # Split into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
        )
        chunks = splitter.split_documents(documents)
        chunks = [c for c in chunks if c.page_content.strip()]
        print(f"  {_ts(t0)} Чанков для индексации: {len(chunks)}")

        # Index in batches
        batch_size = 200
        indexed = 0
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        for batch_num, i in enumerate(range(0, len(chunks), batch_size), 1):
            batch = chunks[i : i + batch_size]
            try:
                self.collection.add(
                    ids=[f"chunk_{i+j}" for j in range(len(batch))],
                    documents=[c.page_content for c in batch],
                    metadatas=[{"source": c.metadata.get("source", "unknown")} for c in batch],
                )
                indexed += len(batch)
            except Exception as e:
                print(f"  {_ts(t0)} Ошибка батча {batch_num}: {e}")
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"  {_ts(t0)} Эмбеддинг: {batch_num}/{total_batches} батчей ({indexed} чанков)", flush=True)

        print(f"  {_ts(t0)} Готово!")

        return {
            "documents_loaded": len(documents),
            "chunks_indexed": indexed,
            "collection_size": self.collection.count(),
        }

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenizer for BM25 with optional Russian stemming."""
        tokens = re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9]+', text.lower())
        if HAS_STEMMER:
            tokens = [_stemmer.stemWord(t) for t in tokens]
        return tokens

    def _build_bm25_index(self):
        """Build BM25 index from all documents in the collection."""
        if not HAS_BM25:
            return
        all_data = self.collection.get(include=["documents", "metadatas"])
        self._bm25_docs = all_data["documents"]
        self._bm25_metas = all_data["metadatas"]
        tokenized = [self._tokenize(doc) for doc in self._bm25_docs]
        self._bm25_index = BM25Okapi(tokenized)

    def _search_bm25(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """Keyword search using BM25."""
        if self._bm25_index is None:
            self._build_bm25_index()
        if self._bm25_index is None:
            return []
        tokens = self._tokenize(query)
        scores = self._bm25_index.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results]
        docs = []
        for idx in top_indices:
            if scores[idx] > 0:
                docs.append({
                    "content": self._bm25_docs[idx],
                    "source": self._bm25_metas[idx].get("source", "unknown"),
                    "bm25_score": float(scores[idx]),
                })
        return docs

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents using vector similarity."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        docs = []
        for i, doc in enumerate(results["documents"][0]):
            docs.append({
                "content": doc,
                "source": results["metadatas"][0][i].get("source", "unknown"),
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })

        return docs

    def hybrid_search(self, query: str, n_results: int = 5, vector_weight: float = DEFAULT_VECTOR_WEIGHT) -> List[Dict[str, Any]]:
        """Hybrid search combining vector similarity and BM25 keyword matching."""
        # Vector search (fetch more candidates for merging)
        vector_results = self.search(query, n_results=n_results * 2)

        # BM25 search
        bm25_results = self._search_bm25(query, n_results=n_results * 2)

        # Normalize and merge scores using Reciprocal Rank Fusion
        doc_scores: Dict[str, Dict[str, Any]] = {}

        for rank, doc in enumerate(vector_results):
            key = doc["content"][:100]
            rrf = 1.0 / (rank + 60)  # RRF constant k=60
            doc_scores[key] = {
                "content": doc["content"],
                "source": doc["source"],
                "distance": doc.get("distance"),
                "score": vector_weight * rrf,
            }

        bm25_weight = 1.0 - vector_weight
        for rank, doc in enumerate(bm25_results):
            key = doc["content"][:100]
            rrf = 1.0 / (rank + 60)  # RRF
            if key in doc_scores:
                doc_scores[key]["score"] += bm25_weight * rrf
            else:
                doc_scores[key] = {
                    "content": doc["content"],
                    "source": doc["source"],
                    "distance": None,
                    "score": bm25_weight * rrf,
                }

        # Sort by combined score and return top results
        ranked = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:n_results]

    def get_status(self) -> Dict[str, Any]:
        """Get index status."""
        try:
            count = self.collection.count()
            return {
                "indexed": True,
                "total_chunks": count,
                "collection_name": self.collection_name,
                "chroma_path": self.chroma_path,
            }
        except Exception as e:
            return {
                "indexed": False,
                "error": str(e),
            }


class LLM:
    """Ollama LLM wrapper."""

    def __init__(self, model: str = DEFAULT_LLM_MODEL, host: str = OLLAMA_HOST):
        self.model = model
        self.client = ollama.Client(host=host)

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Generate text from prompt."""
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
        )
        return response["message"]["content"]

    def generate_json(self, prompt: str, temperature: float = 0.0) -> str:
        """Generate JSON response (for structured outputs)."""
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
            format="json",
        )
        return response["message"]["content"]
