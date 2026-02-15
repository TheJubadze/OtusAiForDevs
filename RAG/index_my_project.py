"""
Индексация проекта и вики в векторную базу ChromaDB.

Настройки: скопируйте .env.example в .env и укажите свои пути.
Запуск:     python index_my_project.py
"""

import os
from dotenv import load_dotenv
from rag.utils import VectorStore

load_dotenv()

FOLDERS = os.environ.get("INDEX_FOLDERS", "./sample_docs").split(";")
CHROMA_PATH = os.environ.get("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "documents")


def main():
    print("Создаю VectorStore...")
    vector_store = VectorStore(
        chroma_path=CHROMA_PATH,
        collection_name=COLLECTION_NAME,
    )

    for i, folder in enumerate(FOLDERS):
        folder = folder.strip()
        if not folder:
            continue

        if not os.path.isdir(folder):
            print(f"\nПапка не найдена, пропускаю: {folder}")
            continue

        reset = (i == 0)  # reset только для первой папки
        print(f"\nИндексирую: {folder} {'(с нуля)' if reset else '(добавляю)'}")

        result = vector_store.index_folder(folder, reset=reset)

        print(f"  Загружено файлов: {result['documents_loaded']}")
        print(f"  Создано чанков:   {result['chunks_indexed']}")
        print(f"  Всего в индексе:  {result['collection_size']}")

    print(f"\nГотово! Индекс сохранён в: {CHROMA_PATH}")


if __name__ == "__main__":
    main()
