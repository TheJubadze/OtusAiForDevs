#!/usr/bin/env python3
"""
Генерация финального актуального отчёта со всеми исправлениями
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from server import (
    scan_folder, VIDEOS_ROOT, MOVIES_FOLDER,
    clean_movie_name, extract_year,
    fetch_movie_info_tmdb,
    sanitize_filename,
    VIDEO_EXTENSIONS
)

# Импортируем маппинги из fix_problematic_files
from fix_problematic_files import MANUAL_MAPPINGS, SKIP_FILES


def is_series_file(filename: str, parent_folder: str = '') -> bool:
    """Определяет, является ли файл частью сериала"""
    series_patterns = [
        'S01E', 'S02E', 'S03E', 'S04E', 'S05E', 'S06E', 'S07E', 'S08E',
        's01e', 's02e', 's03e', 's04e', 's05e', 's06e', 's07e', 's08e',
        'E01', 'E02', 'E03', 'E04', 'E05',
        '.e01.', '.e02.', '.e03.', '.e04.', '.e05.',
    ]

    filename_upper = filename.upper()
    if any(pattern.upper() in filename_upper for pattern in series_patterns):
        return True

    if parent_folder:
        folder_upper = parent_folder.upper()
        if any(keyword in folder_upper for keyword in ['SEASON', 'S01', 'S02', 'S03', 'SERIES']):
            return True

    return False


def find_series_folders(root_path: Path) -> dict:
    """Находит все папки с сериалами"""
    series_data = defaultdict(list)

    for root, dirs, files in os.walk(root_path):
        root_path_obj = Path(root)
        series_files_in_folder = []

        for file in files:
            if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                if is_series_file(file, root_path_obj.name):
                    series_files_in_folder.append(file)

        if series_files_in_folder:
            series_data[str(root_path_obj)] = series_files_in_folder

    return dict(series_data)


def get_all_video_files(root_path: Path) -> list:
    """Получает список всех видеофайлов рекурсивно"""
    video_files = []

    for root, dirs, files in os.walk(root_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                full_path = Path(root) / file
                video_files.append({
                    'path': str(full_path),
                    'name': file,
                    'parent_folder': Path(root).name,
                    'parent_path': str(Path(root))
                })

    return video_files


def is_already_correct_format(filename: str) -> bool:
    """Проверяет, соответствует ли имя файла правильному формату"""
    import re
    pattern = r'^.+\s\(\d{4}\)\.\w+$'
    return bool(re.match(pattern, filename))


async def process_problematic_file(filename: str, filepath: str) -> dict:
    """Обрабатывает проблемный файл с использованием ручного маппинга"""
    result = {
        'original_name': filename,
        'original_path': filepath,
        'new_name': None,
        'status': None,
        'error': None,
        'info': None
    }

    if filename in SKIP_FILES:
        result['status'] = 'error'
        result['error'] = 'Технический файл - требует ручного определения'
        return result

    if filename not in MANUAL_MAPPINGS:
        result['status'] = 'error'
        result['error'] = 'Нет ручного маппинга'
        return result

    mapping = MANUAL_MAPPINGS[filename]
    extension = Path(filename).suffix

    # Если есть готовое название
    if 'manual_title' in mapping:
        title = mapping['manual_title']
        year = mapping.get('year', '')
        part = mapping.get('part', '')

        if part:
            new_filename = sanitize_filename(f"{title} ({year}) - Часть {part}{extension}")
        elif year and year != 'NA':
            new_filename = sanitize_filename(f"{title} ({year}){extension}")
        else:
            new_filename = sanitize_filename(f"{title}{extension}")

        result['status'] = 'success'
        result['new_name'] = new_filename
        result['info'] = {'title': title, 'year': year, 'source': 'Manual'}
        return result

    # Получаем из TMDb
    search_title = mapping['search_title']
    year = mapping.get('year', '')
    part = mapping.get('part', '')

    info = await fetch_movie_info_tmdb(search_title, year)

    if "error" in info:
        result['status'] = 'error'
        result['error'] = f"Не найдено в TMDb: {info['error']}"
        return result

    title = info.get("title", search_title)
    movie_year = info.get("year", year)

    if part:
        new_filename = sanitize_filename(f"{title} ({movie_year}) - Часть {part}{extension}")
    elif movie_year and movie_year != "NA":
        new_filename = sanitize_filename(f"{title} ({movie_year}){extension}")
    else:
        new_filename = sanitize_filename(f"{title}{extension}")

    result['status'] = 'success'
    result['new_name'] = new_filename
    result['info'] = info

    return result


async def analyze_movie_rename(video_info: dict) -> dict:
    """Анализирует переименование одного фильма"""
    filename = video_info['name']
    filepath = video_info['path']
    parent_folder = video_info['parent_folder']
    parent_path = video_info['parent_path']

    result = {
        'original_name': filename,
        'original_path': filepath,
        'parent_folder': parent_folder,
        'new_name': None,
        'new_path': None,
        'status': None,
        'error': None,
        'info': None,
        'is_series': False
    }

    # Проверяем, является ли файл сериалом
    if is_series_file(filename, parent_folder):
        result['status'] = 'series'
        result['is_series'] = True
        result['error'] = 'Файл сериала'
        return result

    # Проверяем, является ли проблемным файлом
    if filename in MANUAL_MAPPINGS or filename in SKIP_FILES:
        problematic_result = await process_problematic_file(filename, filepath)
        result.update(problematic_result)
        if result['status'] == 'success':
            result['new_path'] = str(Path(parent_path) / result['new_name'])
        return result

    # Проверяем формат
    if is_already_correct_format(filename):
        result['status'] = 'skipped'
        result['error'] = 'Уже в правильном формате'
        result['new_name'] = filename
        return result

    # Обычная обработка
    clean_name = clean_movie_name(filename)
    year = extract_year(filename)

    info = await fetch_movie_info_tmdb(clean_name, year)

    if "error" in info:
        result['status'] = 'error'
        result['error'] = info['error']
        result['info'] = {'search_title': clean_name, 'search_year': year}
        return result

    title = info.get("title", clean_name)
    movie_year = info.get("year", str(year) if year else "")
    extension = Path(filename).suffix

    if movie_year and movie_year != "NA" and movie_year.strip():
        new_filename = sanitize_filename(f"{title} ({movie_year}){extension}")
    else:
        new_filename = sanitize_filename(f"{title}{extension}")

    if new_filename == filename:
        result['status'] = 'skipped'
        result['error'] = 'Имя уже правильное'
        result['new_name'] = new_filename
        result['info'] = info
        return result

    new_path = str(Path(parent_path) / new_filename)

    if Path(new_path).exists() and new_path != filepath:
        result['status'] = 'error'
        result['error'] = 'Файл с новым именем уже существует'
        result['new_name'] = new_filename
        result['info'] = info
        return result

    result['status'] = 'success'
    result['new_name'] = new_filename
    result['new_path'] = new_path
    result['info'] = info

    return result


def suggest_series_folder_rename(folder_path: str, files: list) -> dict:
    """Предлагает переименование папки сериала"""
    if not files:
        return {
            'original_path': folder_path,
            'original_name': Path(folder_path).name,
            'new_name': None,
            'status': 'error',
            'error': 'Нет файлов в папке'
        }

    folder_name = Path(folder_path).name
    import re

    clean_folder_name = re.sub(r'[Ss]\d{2}.*', '', folder_name)
    clean_folder_name = re.sub(r'\.WEB-DL.*', '', clean_folder_name)
    clean_folder_name = re.sub(r'\.BDRip.*', '', clean_folder_name)
    clean_folder_name = re.sub(r'\.HDRip.*', '', clean_folder_name)
    clean_folder_name = clean_folder_name.replace('.', ' ').strip()

    year_match = re.search(r'(19|20)\d{2}', folder_name)
    year = year_match.group(0) if year_match else None

    if re.match(r'^.+\s\(\d{4}\)$', folder_name):
        return {
            'original_path': folder_path,
            'original_name': folder_name,
            'new_name': folder_name,
            'status': 'skipped',
            'error': 'Папка уже в правильном формате'
        }

    if clean_folder_name and year:
        suggested_name = f"{clean_folder_name} ({year})"
    elif clean_folder_name:
        suggested_name = clean_folder_name
    else:
        return {
            'original_path': folder_path,
            'original_name': folder_name,
            'new_name': None,
            'status': 'error',
            'error': 'Не удалось извлечь название'
        }

    suggested_name = sanitize_filename(suggested_name)

    if suggested_name == folder_name:
        return {
            'original_path': folder_path,
            'original_name': folder_name,
            'new_name': suggested_name,
            'status': 'skipped',
            'error': 'Имя папки уже правильное'
        }

    return {
        'original_path': folder_path,
        'original_name': folder_name,
        'new_name': suggested_name,
        'new_path': str(Path(folder_path).parent / suggested_name),
        'status': 'success',
        'files_count': len(files)
    }


def generate_final_report(movie_results: list, series_results: list, output_file: str = 'FINAL_RENAME_REPORT.md'):
    """Генерирует финальный актуальный отчёт"""

    movies_success = [r for r in movie_results if r['status'] == 'success']
    movies_errors = [r for r in movie_results if r['status'] == 'error']
    movies_skipped = [r for r in movie_results if r['status'] == 'skipped']
    movies_series_files = [r for r in movie_results if r['status'] == 'series']

    series_success = [r for r in series_results if r['status'] == 'success']
    series_errors = [r for r in series_results if r['status'] == 'error']
    series_skipped = [r for r in series_results if r['status'] == 'skipped']

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('# 📋 ФИНАЛЬНЫЙ ОТЧЁТ О ПЕРЕИМЕНОВАНИИ ФИЛЬМОВ\n\n')
        f.write(f'**Дата создания:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write('> ⚠️ **ВНИМАНИЕ:** Это предварительный отчёт. Файлы НЕ были переименованы.\n')
        f.write('> Этот отчёт включает все исправления проблемных файлов.\n\n')

        # Общая статистика
        f.write('## 📊 Общая статистика\n\n')
        f.write('### Фильмы\n\n')
        f.write(f'- **Всего проанализировано:** {len(movie_results)} файлов\n')
        f.write(f'- **✅ Будут переименованы:** {len(movies_success)} файлов\n')
        f.write(f'- **⊘ Будут пропущены:** {len(movies_skipped)} файлов\n')
        f.write(f'- **📁 Файлы сериалов:** {len(movies_series_files)} файлов\n')
        f.write(f'- **❌ Проблемные:** {len(movies_errors)} файлов\n\n')

        success_rate = (len(movies_success) / len(movie_results) * 100) if movie_results else 0
        f.write(f'**Процент успешного распознавания:** {success_rate:.1f}%\n\n')

        f.write('### Сериалы (папки)\n\n')
        f.write(f'- **Всего найдено папок:** {len(series_results)}\n')
        f.write(f'- **✅ Будут переименованы:** {len(series_success)} папок\n')
        f.write(f'- **⊘ Будут пропущены:** {len(series_skipped)} папок\n')
        f.write(f'- **❌ Проблемные:** {len(series_errors)} папок\n\n')

        # Таблица фильмов
        if movies_success:
            f.write('## 🎬 Фильмы: Таблица "Было → Стало"\n\n')
            f.write('| № | Было | Стало | Источник |\n')
            f.write('|---|------|-------|----------|\n')
            for idx, r in enumerate(movies_success, 1):
                old_name = r['original_name'].replace('|', '\\|')
                new_name = r['new_name'].replace('|', '\\|')
                source = r.get('info', {}).get('source', 'TMDb')
                f.write(f'| {idx} | {old_name} | {new_name} | {source} |\n')
            f.write('\n')

        # Таблица сериалов
        if series_success:
            f.write('## 📺 Сериалы: Переименование папок\n\n')
            f.write('| № | Было (папка) | Стало | Файлов |\n')
            f.write('|---|--------------|-------|--------|\n')
            for idx, r in enumerate(series_success, 1):
                old_name = r['original_name'].replace('|', '\\|')
                new_name = r['new_name'].replace('|', '\\|')
                files_count = r.get('files_count', 0)
                f.write(f'| {idx} | {old_name} | {new_name} | {files_count} |\n')
            f.write('\n')

        # Пропущенные фильмы
        if movies_skipped:
            f.write('## ⊘ Пропущенные фильмы\n\n')
            f.write('| № | Имя файла | Причина |\n')
            f.write('|---|-----------|----------|\n')
            for idx, r in enumerate(movies_skipped, 1):
                filename = r['original_name'].replace('|', '\\|')
                reason = r['error'].replace('|', '\\|')
                f.write(f'| {idx} | {filename} | {reason} |\n')
            f.write('\n')

        # Проблемные файлы
        if movies_errors:
            f.write('## ❌ Проблемные файлы\n\n')
            f.write('| № | Имя файла | Проблема | Дополнительно |\n')
            f.write('|---|-----------|----------|---------------|\n')
            for idx, r in enumerate(movies_errors, 1):
                filename = r['original_name'].replace('|', '\\|')
                error = r['error'].replace('|', '\\|')
                extra = ''
                if r.get('info'):
                    search_title = r['info'].get('search_title', '')
                    search_year = r['info'].get('search_year', '')
                    if search_title:
                        extra = f"Искали: {search_title}"
                        if search_year:
                            extra += f" ({search_year})"
                extra = extra.replace('|', '\\|')
                f.write(f'| {idx} | {filename} | {error} | {extra} |\n')
            f.write('\n')

        # Файлы сериалов
        if movies_series_files:
            f.write('## 📁 Файлы сериалов\n\n')
            f.write(f'Всего файлов сериалов: **{len(movies_series_files)}**\n\n')
            f.write('Эти файлы не переименовываются индивидуально. ')
            f.write('Переименование произойдёт только для папок.\n\n')

        # Источники данных
        f.write('## 📚 Источники данных\n\n')
        sources = {}
        for r in movies_success:
            if r.get('info'):
                source = r['info'].get('source', 'Unknown')
                sources[source] = sources.get(source, 0) + 1

        for source, count in sorted(sources.items(), key=lambda x: -x[1]):
            f.write(f'- **{source}:** {count} фильмов\n')
        f.write('\n')

        f.write('---\n\n')
        f.write(f'*Отчёт сгенерирован автоматически {datetime.now().strftime("%Y-%m-%d в %H:%M:%S")}*\n\n')
        f.write('**Следующий шаг:** Запустите скрипт переименования для применения изменений.\n')

    print(f'\n✅ Финальный отчёт сохранён: {output_file}')


async def main():
    """Основная функция"""
    print('\n' + '='*80)
    print('📋 ГЕНЕРАЦИЯ ФИНАЛЬНОГО АКТУАЛЬНОГО ОТЧЁТА')
    print('='*80 + '\n')

    movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER
    print(f'📂 Директория: {movies_path}\n')

    print('🔍 Сканирование видеофайлов...')
    all_videos = get_all_video_files(movies_path)
    print(f'✅ Найдено {len(all_videos)} видеофайлов\n')

    print('📁 Поиск папок с сериалами...')
    series_folders = find_series_folders(movies_path)
    print(f'✅ Найдено {len(series_folders)} папок с сериалами\n')

    print('=' * 80)
    print('📝 АНАЛИЗ ФАЙЛОВ')
    print('=' * 80 + '\n')

    movie_results = []
    for idx, video in enumerate(all_videos, 1):
        print(f'[{idx}/{len(all_videos)}] Анализ: {video["name"][:70]}...', end='\r')
        result = await analyze_movie_rename(video)
        movie_results.append(result)

        if result['status'] == 'success' and result.get('info', {}).get('source') == 'TMDb':
            await asyncio.sleep(0.3)

    print('\n')

    print('=' * 80)
    print('📁 АНАЛИЗ ПАПОК СЕРИАЛОВ')
    print('=' * 80 + '\n')

    series_results = []
    for idx, (folder_path, files) in enumerate(series_folders.items(), 1):
        folder_name = Path(folder_path).name
        print(f'[{idx}/{len(series_folders)}] Анализ папки: {folder_name}')
        result = suggest_series_folder_rename(folder_path, files)
        series_results.append(result)

    print('\n' + '=' * 80)
    print('📊 ГЕНЕРАЦИЯ ОТЧЁТА')
    print('=' * 80)
    generate_final_report(movie_results, series_results)

    movies_success = len([r for r in movie_results if r['status'] == 'success'])
    movies_errors = len([r for r in movie_results if r['status'] == 'error'])
    movies_skipped = len([r for r in movie_results if r['status'] == 'skipped'])
    movies_series = len([r for r in movie_results if r['status'] == 'series'])

    series_success = len([r for r in series_results if r['status'] == 'success'])

    print('\n' + '=' * 80)
    print('✅ ЗАВЕРШЕНО')
    print('=' * 80)
    print('ФИЛЬМЫ:')
    print(f'  Всего:                   {len(movie_results)}')
    print(f'  ✅ Будут переименованы:   {movies_success}')
    print(f'  ⊘ Будут пропущены:        {movies_skipped}')
    print(f'  📁 Файлы сериалов:        {movies_series}')
    print(f'  ❌ Проблемные:            {movies_errors}')
    print('\nСЕРИАЛЫ:')
    print(f'  ✅ Будут переименованы:   {series_success} папок')
    print('=' * 80 + '\n')


if __name__ == "__main__":
    asyncio.run(main())
