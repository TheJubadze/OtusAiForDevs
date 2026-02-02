#!/usr/bin/env python3
"""
Выполнение переименования файлов на основе финального отчёта
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from server import (
    VIDEOS_ROOT, MOVIES_FOLDER,
    fetch_movie_info_tmdb,
    sanitize_filename
)

from fix_problematic_files import MANUAL_MAPPINGS, SKIP_FILES, process_problematic_file


# Паттерны для определения файлов сериалов
SERIES_PATTERNS = [
    r'[Ss]\d+[Ee]\d+',  # S01E01
    r'\d+x\d+',  # 1x01
    r'[Ee]pisode[\s\._-]*\d+',  # Episode 01
    r'[Ss]eason[\s\._-]*\d+',  # Season 1
]


def is_series_file(filename: str) -> bool:
    """Определяет, является ли файл частью сериала"""
    import re
    for pattern in SERIES_PATTERNS:
        if re.search(pattern, filename):
            return True
    return False


async def analyze_and_rename_movie(filepath: str, filename: str) -> dict:
    """Анализирует фильм и переименовывает его"""
    from server import clean_movie_name
    import re

    result = {
        'original_name': filename,
        'original_path': filepath,
        'new_name': None,
        'new_path': None,
        'status': None,
        'error': None,
        'renamed': False
    }

    extension = Path(filename).suffix

    # Очищаем название
    cleaned_name = clean_movie_name(filename)

    # Извлекаем год
    year_match = re.search(r'(19\d{2}|20\d{2})', cleaned_name)
    year = year_match.group(1) if year_match else ''

    # Убираем год из названия для поиска
    search_title = re.sub(r'\s*(19\d{2}|20\d{2})\s*', ' ', cleaned_name).strip()

    # Получаем информацию из TMDb
    info = await fetch_movie_info_tmdb(search_title, year)

    if "error" in info:
        result['status'] = 'error'
        result['error'] = f"Не найдено в TMDb: {info['error']}"
        return result

    # Формируем новое имя
    title = info.get("title", search_title)
    movie_year = info.get("year", year)

    if movie_year and movie_year != "NA":
        new_filename = sanitize_filename(f"{title} ({movie_year}){extension}")
    else:
        new_filename = sanitize_filename(f"{title}{extension}")

    new_path = str(Path(filepath).parent / new_filename)

    # Проверяем, не существует ли уже файл
    if Path(new_path).exists() and new_path != filepath:
        result['status'] = 'error'
        result['error'] = 'Файл с новым именем уже существует'
        result['new_name'] = new_filename
        return result

    # Переименовываем файл
    if new_path != filepath:
        try:
            os.rename(filepath, new_path)
            result['status'] = 'success'
            result['new_name'] = new_filename
            result['new_path'] = new_path
            result['renamed'] = True
        except Exception as e:
            result['status'] = 'error'
            result['error'] = f'Ошибка переименования: {str(e)}'
            result['new_name'] = new_filename
    else:
        result['status'] = 'success'
        result['new_name'] = new_filename
        result['new_path'] = new_path
        result['renamed'] = False
        result['error'] = 'Имя файла уже корректное'

    return result


async def process_and_rename_problematic(filepath: str, filename: str) -> dict:
    """Обрабатывает и переименовывает проблемный файл"""

    # Сначала анализируем
    result = await process_problematic_file(filepath, filename)

    if result['status'] != 'success':
        return result

    # Переименовываем
    new_path = result['new_path']
    if new_path != filepath:
        try:
            os.rename(filepath, new_path)
            result['renamed'] = True
        except Exception as e:
            result['status'] = 'error'
            result['error'] = f'Ошибка переименования: {str(e)}'
            result['renamed'] = False
    else:
        result['renamed'] = False
        result['error'] = 'Имя файла уже корректное'

    return result


def suggest_and_rename_series_folder(folder_path: str) -> dict:
    """Предлагает новое имя для папки сериала и переименовывает"""
    import re

    folder_name = Path(folder_path).name

    # Паттерны для очистки
    patterns_to_remove = [
        r'\.DVDRip.*',
        r'\.BDRip.*',
        r'\.\d{3,4}p.*',
        r'\[.*?\]',
        r'\(.*?\)',
        r'\.-.+',
    ]

    cleaned = folder_name
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Заменяем точки на пробелы
    cleaned = cleaned.replace('.', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Извлекаем год
    year_match = re.search(r'(19\d{2}|20\d{2})', cleaned)
    year = f" ({year_match.group(1)})" if year_match else ""
    title = re.sub(r'\s*(19\d{2}|20\d{2})\s*', ' ', cleaned).strip()

    new_folder_name = sanitize_filename(f"{title}{year}")
    new_folder_path = str(Path(folder_path).parent / new_folder_name)

    result = {
        'original_name': folder_name,
        'original_path': folder_path,
        'new_name': new_folder_name,
        'new_path': new_folder_path,
        'renamed': False,
        'error': None
    }

    # Переименовываем папку
    if new_folder_path != folder_path and not Path(new_folder_path).exists():
        try:
            os.rename(folder_path, new_folder_path)
            result['renamed'] = True
        except Exception as e:
            result['error'] = f'Ошибка переименования: {str(e)}'
    elif Path(new_folder_path).exists():
        result['error'] = 'Папка с новым именем уже существует'
    else:
        result['error'] = 'Имя папки уже корректное'

    return result


def get_all_files_and_folders():
    """Получает все файлы и папки с сериалами"""
    movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER

    files_to_process = []
    series_folders = set()

    for root, dirs, files in os.walk(movies_path):
        # Проверяем, является ли папка папкой сериала
        series_files_in_dir = []
        other_files_in_dir = []

        for file in files:
            if file.lower().endswith(('.mkv', '.avi', '.mp4', '.m2ts')):
                full_path = Path(root) / file
                if is_series_file(file):
                    series_files_in_dir.append(str(full_path))
                else:
                    other_files_in_dir.append({
                        'path': str(full_path),
                        'name': file
                    })

        # Если в папке есть файлы сериала, помечаем папку
        if series_files_in_dir and root != str(movies_path):
            series_folders.add(root)

        # Добавляем обычные файлы
        files_to_process.extend(other_files_in_dir)

    return files_to_process, list(series_folders)


async def main():
    """Основная функция"""

    print('\n' + '='*80)
    print('🚀 ВЫПОЛНЕНИЕ ПЕРЕИМЕНОВАНИЯ ФАЙЛОВ')
    print('='*80 + '\n')

    # Получаем все файлы и папки
    print('🔍 Сканирование библиотеки...')
    files_to_process, series_folders = get_all_files_and_folders()
    print(f'✅ Найдено {len(files_to_process)} файлов и {len(series_folders)} папок с сериалами\n')

    # Обрабатываем фильмы
    print('=' * 80)
    print('🎬 ПЕРЕИМЕНОВАНИЕ ФИЛЬМОВ')
    print('=' * 80 + '\n')

    renamed_count = 0
    skipped_count = 0
    error_count = 0

    for idx, file_info in enumerate(files_to_process, 1):
        filepath = file_info['path']
        filename = file_info['name']

        print(f'[{idx}/{len(files_to_process)}] {filename}')

        # Проверяем, является ли файл проблемным
        if filename in MANUAL_MAPPINGS or filename in SKIP_FILES:
            result = await process_and_rename_problematic(filepath, filename)
        else:
            result = await analyze_and_rename_movie(filepath, filename)

        if result['status'] == 'success' and result.get('renamed'):
            print(f'  ✅ → {result["new_name"]}')
            renamed_count += 1
        elif result['status'] == 'success':
            print(f'  ⊘ {result.get("error", "Без изменений")}')
            skipped_count += 1
        elif result['status'] == 'skipped':
            print(f'  ⊘ {result["error"]}')
            skipped_count += 1
        else:
            print(f'  ❌ {result["error"]}')
            error_count += 1

        # Задержка для API
        if result['status'] == 'success':
            await asyncio.sleep(0.3)

    # Обрабатываем папки сериалов
    if series_folders:
        print('\n' + '=' * 80)
        print('📁 ПЕРЕИМЕНОВАНИЕ ПАПОК СЕРИАЛОВ')
        print('=' * 80 + '\n')

        series_renamed = 0
        series_skipped = 0

        for idx, folder_path in enumerate(series_folders, 1):
            folder_name = Path(folder_path).name
            print(f'[{idx}/{len(series_folders)}] {folder_name}')

            result = suggest_and_rename_series_folder(folder_path)

            if result['renamed']:
                print(f'  ✅ → {result["new_name"]}')
                series_renamed += 1
            else:
                error_msg = result.get('error', 'Без изменений')
                print(f'  ⊘ {error_msg}')
                series_skipped += 1

    # Итоги
    print('\n' + '=' * 80)
    print('✅ ЗАВЕРШЕНО')
    print('=' * 80)
    print(f'\nФИЛЬМЫ:')
    print(f'  Всего обработано:      {len(files_to_process)}')
    print(f'  ✅ Переименовано:      {renamed_count}')
    print(f'  ⊘ Пропущено:           {skipped_count}')
    print(f'  ❌ Ошибки:             {error_count}')

    if series_folders:
        print(f'\nСЕРИАЛЫ:')
        print(f'  ✅ Переименовано:      {series_renamed} папок')
        print(f'  ⊘ Пропущено:           {series_skipped} папок')

    print('=' * 80 + '\n')


if __name__ == "__main__":
    asyncio.run(main())
