"""
Тестирование MCP-сервера локально (без MCP протокола).
Вызывает инструменты напрямую.
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from server import index_folder, ask_question, find_relevant_docs, summarize_document, index_status


def main():
    print("=" * 60)
    print("🧪 Тестирование RAG MCP Server")
    print("=" * 60)

    # 1. Статус индекса (до индексации)
    print("\n📊 Статус индекса (до индексации):")
    print(index_status())

    # 2. Индексация
    print("\n" + "=" * 60)
    print("📂 Индексация sample_docs/:")
    print(index_folder("./sample_docs", reset=True))

    # 3. Статус индекса (после)
    print("\n📊 Статус индекса (после индексации):")
    print(index_status())

    # 4. Поиск документов
    print("\n" + "=" * 60)
    print("🔍 Поиск: 'авторизация JWT'")
    print(find_relevant_docs("авторизация JWT", n_results=3))

    # 5. Вопросы
    print("\n" + "=" * 60)
    questions = [
        "Как работает авторизация в системе?",
        "Какой пароль у тестового пользователя admin?",
        "Как запустить тесты?",
    ]

    for q in questions:
        print(f"\n❓ {q}")
        print("-" * 40)
        print(ask_question(q))

    # 6. Суммаризация документа
    print("\n" + "=" * 60)
    print("📄 Суммаризация architecture.md:")
    print(summarize_document("./sample_docs/architecture.md"))


if __name__ == "__main__":
    main()
