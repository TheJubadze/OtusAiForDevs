"""
Test script for Corrective RAG with LangGraph.
"""

from rag import create_rag_chain, ask_question


def main():
    print("=" * 60)
    print("🚀 Corrective RAG with LangGraph")
    print("=" * 60)

    # Create chain and index documents
    print("\n📦 Initializing RAG chain...")
    chain, vector_store, llm = create_rag_chain(
        chroma_path="./chroma_db_langgraph",
        collection_name="taskflow_docs",
    )

    # Index documents
    print("📂 Indexing documents...")
    result = vector_store.index_folder("./sample_docs", reset=True)
    print(f"   Documents: {result['documents_loaded']}")
    print(f"   Chunks: {result['chunks_indexed']}")

    # Test questions
    questions = [
        "Как работает авторизация в системе?",
        "Что делать, если RabbitMQ не принимает сообщения?",
        "Какие роли пользователей есть?",
        "Как запустить тесты?",
        "Какой пароль у тестового пользователя admin?",
    ]

    print("\n" + "=" * 60)
    print("📝 Testing Questions")
    print("=" * 60)

    for q in questions:
        print(f"\n❓ {q}")
        print("-" * 40)

        result = ask_question(q, chain=chain)

        if result["error"]:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"💬 {result['answer']}")
            if result["sources"]:
                print(f"📎 Источники: {', '.join(result['sources'])}")

        print()


if __name__ == "__main__":
    main()
