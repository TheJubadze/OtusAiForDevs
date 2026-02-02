#!/usr/bin/env python3
"""
Генерация финального отчёта о переименовании мультфильмов с учетом ручных маппингов
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from server import (
    VIDEOS_ROOT, CARTOONS_FOLDER,
    fetch_movie_info_tmdb,
    clean_movie_name,
    sanitize_filename
)

from fix_problematic_cartoons import MANUAL_MAPPINGS, process_problematic_cartoon


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


async def analyze_cartoon_rename(filepath: str, filename: str) -> dict:
    """Анализирует мультфильм и предлагает новое имя"""
    import re

    result = {
        'original_name': filename,
        'original_path': filepath,
        'new_name': None,
        'new_path': None,
        'status': None,
        'error': None,
        'info': None
    }

    # Сначала проверяем, является ли это проблемным файлом с ручным маппингом
    if filename in MANUAL_MAPPINGS:
        problematic_result = await process_problematic_cartoon(filepath, filename)
        result.update(problematic_result)
        return result

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
        result['info'] = {'search_title': search_title, 'search_year': year}
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
        result['info'] = info
        return result

    # Проверяем, изменится ли имя
    if new_path == filepath:
        result['status'] = 'success'
        result['new_name'] = new_filename
        result['new_path'] = new_path
        result['error'] = 'Имя файла уже корректное'
        result['info'] = info
        return result

    result['status'] = 'success'
    result['new_name'] = new_filename
    result['new_path'] = new_path
    result['info'] = info

    return result


def suggest_series_folder_rename(folder_path: str) -> dict:
    """Предлагает новое имя для папки сериала"""
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

    return {
        'original_name': folder_name,
        'original_path': folder_path,
        'new_name': new_folder_name,
        'new_path': new_folder_path
    }


def get_all_cartoons_and_folders():
    """Получает все мультфильмы и папки с сериалами"""
    cartoons_path = Path(VIDEOS_ROOT) / CARTOONS_FOLDER

    if not cartoons_path.exists():
        print(f'❌ Папка не найдена: {cartoons_path}')
        return [], []

    files_to_process = []
    series_folders = set()

    for root, dirs, files in os.walk(cartoons_path):
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
        if series_files_in_dir and root != str(cartoons_path):
            series_folders.add(root)

        # Добавляем обычные файлы
        files_to_process.extend(other_files_in_dir)

    return files_to_process, list(series_folders)


def generate_report(cartoon_results: list, series_results: list, output_file: str = 'FINAL_CARTOONS_RENAME_REPORT.md'):
    """Генерирует финальный отчёт о переименовании мультфильмов"""

    # Классификация результатов
    to_rename = [r for r in cartoon_results if r['status'] == 'success' and r.get('error') != 'Имя файла уже корректное']
    already_correct = [r for r in cartoon_results if r['status'] == 'success' and r.get('error') == 'Имя файла уже корректное']
    errors = [r for r in cartoon_results if r['status'] == 'error']
    skipped = [r for r in cartoon_results if r['status'] == 'skipped']

    # Подсчёт файлов сериалов
    series_file_count = sum(
        len([f for f in os.listdir(folder) if f.lower().endswith(('.mkv', '.avi', '.mp4'))])
        for folder in [r['original_path'] for r in series_results]
        if os.path.exists(folder)
    ) if series_results else 0

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('# Финальный отчёт о переименовании мультфильмов\n\n')
        f.write(f'**Дата создания:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write('> ⚠️ **ВНИМАНИЕ:** Это предварительный отчёт. Файлы НЕ были переименованы.\n\n')

        # Статистика
        f.write('## Статистика\n\n')
        f.write('### Мультфильмы\n')
        f.write(f'- **Всего обработано:** {len(cartoon_results)} файлов\n')
        f.write(f'- ✅ **Будут переименованы:** {len(to_rename)} файлов\n')
        f.write(f'- ⊘ **Будут пропущены:** {len(already_correct)} файлов (уже в правильном формате)\n')
        if series_file_count > 0:
            f.write(f'- 📁 **Файлы сериалов:** {series_file_count} файлов (не переименовываются)\n')
        f.write(f'- ❌ **Проблемные:** {len(errors) + len(skipped)} файлов\n\n')

        if series_results:
            f.write('### Сериалы\n')
            f.write(f'- ✅ **Будут переименованы:** {len(series_results)} папок\n\n')

        # Файлы для переименования
        if to_rename:
            f.write('## Будут переименованы\n\n')
            f.write('| № | Было | Стало | Год | Источник |\n')
            f.write('|---|------|-------|-----|----------|\n')
            for idx, r in enumerate(to_rename, 1):
                old = r['original_name'].replace('|', '\\|')
                new = r['new_name'].replace('|', '\\|')
                year = r.get('info', {}).get('year', 'N/A')
                source = r.get('info', {}).get('source', 'TMDb')
                f.write(f'| {idx} | {old} | {new} | {year} | {source} |\n')
            f.write('\n')

        # Папки сериалов
        if series_results:
            f.write('## Папки сериалов\n\n')
            f.write('| № | Было | Стало |\n')
            f.write('|---|------|-------|\n')
            for idx, r in enumerate(series_results, 1):
                old = r['original_name'].replace('|', '\\|')
                new = r['new_name'].replace('|', '\\|')
                f.write(f'| {idx} | {old} | {new} |\n')
            f.write('\n')

        # Уже правильные
        if already_correct:
            f.write('## Уже в правильном формате\n\n')
            f.write('| № | Имя файла |\n')
            f.write('|---|-----------|\\n')
            for idx, r in enumerate(already_correct, 1):
                name = r['original_name'].replace('|', '\\|')
                f.write(f'| {idx} | {name} |\n')
            f.write('\n')

        # Проблемные файлы
        if errors or skipped:
            f.write('## Проблемные файлы\n\n')
            f.write('| № | Имя файла | Проблема |\n')
            f.write('|---|-----------|----------|\n')
            idx = 1
            for r in errors:
                name = r['original_name'].replace('|', '\\|')
                error = r['error'].replace('|', '\\|')
                f.write(f'| {idx} | {name} | {error} |\n')
                idx += 1
            for r in skipped:
                name = r['original_name'].replace('|', '\\|')
                error = r['error'].replace('|', '\\|')
                f.write(f'| {idx} | {name} | {error} |\n')
                idx += 1
            f.write('\n')

        f.write('---\n')
        f.write(f'\n*Отчёт сгенерирован автоматически {datetime.now().strftime("%Y-%m-%d в %H:%M:%S")}*\n')

    print(f'\n✅ Отчёт сохранён: {output_file}')


async def main():
    """Основная функция"""

    print('\n' + '='*80)
    print('📊 ФИНАЛЬНЫЙ АНАЛИЗ МУЛЬТФИЛЬМОВ ДЛЯ ПЕРЕИМЕНОВАНИЯ')
    print('='*80 + '\n')

    # Получаем все мультфильмы и папки
    print('🔍 Сканирование библиотеки мультфильмов...')
    files_to_process, series_folders = get_all_cartoons_and_folders()
    print(f'✅ Найдено {len(files_to_process)} файлов и {len(series_folders)} папок с сериалами\n')

    if not files_to_process and not series_folders:
        print('❌ Мультфильмы не найдены!')
        return

    print('=' * 80)
    print('🎬 АНАЛИЗ МУЛЬТФИЛЬМОВ')
    print('=' * 80 + '\n')

    # Анализируем каждый файл
    cartoon_results = []
    for idx, file_info in enumerate(files_to_process, 1):
        filepath = file_info['path']
        filename = file_info['name']

        print(f'[{idx}/{len(files_to_process)}] {filename}')

        result = await analyze_cartoon_rename(filepath, filename)
        cartoon_results.append(result)

        if result['status'] == 'success' and result.get('error') != 'Имя файла уже корректное':
            source = result.get('info', {}).get('source', 'TMDb')
            print(f'  ✅ → {result["new_name"]} ({source})')
        elif result['status'] == 'success':
            print(f'  ⊘ {result["error"]}')
        elif result['status'] == 'skipped':
            print(f'  ⊘ {result["error"]}')
        else:
            print(f'  ❌ {result["error"]}')

        # Задержка для API
        if result['status'] == 'success' and result.get('info', {}).get('source') != 'Manual':
            await asyncio.sleep(0.3)

    # Анализируем папки сериалов
    series_results = []
    if series_folders:
        print('\n' + '=' * 80)
        print('📁 АНАЛИЗ ПАПОК СЕРИАЛОВ')
        print('=' * 80 + '\n')

        for idx, folder_path in enumerate(series_folders, 1):
            folder_name = Path(folder_path).name
            print(f'[{idx}/{len(series_folders)}] {folder_name}')

            result = suggest_series_folder_rename(folder_path)
            series_results.append(result)

            if result['new_name'] != result['original_name']:
                print(f'  ✅ → {result["new_name"]}')
            else:
                print(f'  ⊘ Имя уже корректное')

    # Генерируем отчёт
    print('\n' + '=' * 80)
    print('📊 ГЕНЕРАЦИЯ ОТЧЁТА')
    print('=' * 80)
    generate_report(cartoon_results, series_results)

    # Итоги
    to_rename = len([r for r in cartoon_results if r['status'] == 'success' and r.get('error') != 'Имя файла уже корректное'])
    already_correct = len([r for r in cartoon_results if r['status'] == 'success' and r.get('error') == 'Имя файла уже корректное'])
    errors = len([r for r in cartoon_results if r['status'] == 'error'])
    skipped = len([r for r in cartoon_results if r['status'] == 'skipped'])

    print('\n' + '=' * 80)
    print('✅ ЗАВЕРШЕНО')
    print('=' * 80)
    print(f'\nМУЛЬТФИЛЬМЫ:')
    print(f'  Всего:                   {len(cartoon_results)}')
    print(f'  ✅ Будут переименованы:   {to_rename}')
    print(f'  ⊘ Будут пропущены:        {already_correct}')
    print(f'  ❌ Проблемные:            {errors + skipped}')

    if series_results:
        print(f'\nСЕРИАЛЫ:')
        print(f'  ✅ Будут переименованы:   {len(series_results)} папок')

    print('=' * 80 + '\n')


if __name__ == "__main__":
    asyncio.run(main())
