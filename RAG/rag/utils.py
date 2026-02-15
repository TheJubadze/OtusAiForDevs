"""
Corrective RAG: Utilities for ChromaDB and Ollama.
"""

import os
import chromadb
import chromadb.utils.embedding_functions as ef
import ollama
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

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


# Default configuration (with env var support for Docker)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_OLLAMA_URL = f"{OLLAMA_HOST}/api/embeddings"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:3b")
DEFAULT_CHROMA_PATH = os.environ.get("CHROMA_PATH", "./chroma_db")
DEFAULT_COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "documents")


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
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        reset: bool = False,
    ) -> Dict[str, Any]:
        """Index all documents in a folder."""

        if reset:
            try:
                self.client.delete_collection(self.collection_name)
                self._collection = None
            except Exception:
                pass

        # Load only text files with known extensions
        documents = []
        skipped = 0
        for file_path in Path(folder_path).rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in TEXT_EXTENSIONS:
                skipped += 1
                continue
            try:
                loader = TextLoader(str(file_path), autodetect_encoding=True)
                documents.extend(loader.load())
            except Exception:
                skipped += 1

        # Split into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
        )
        chunks = splitter.split_documents(documents)

        # Filter out empty chunks
        chunks = [c for c in chunks if c.page_content.strip()]

        # Index in batches
        batch_size = 20
        indexed = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            try:
                self.collection.add(
                    ids=[f"chunk_{i+j}" for j in range(len(batch))],
                    documents=[c.page_content for c in batch],
                    metadatas=[{"source": c.metadata.get("source", "unknown")} for c in batch],
                )
                indexed += len(batch)
            except Exception as e:
                print(f"Warning: batch {i}-{i+len(batch)} failed: {e}")

        return {
            "documents_loaded": len(documents),
            "chunks_indexed": indexed,
            "collection_size": self.collection.count(),
        }

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents."""
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
