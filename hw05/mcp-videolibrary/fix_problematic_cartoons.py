#!/usr/bin/env python3
"""
Обработка проблемных мультфильмов с ручным маппингом
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
    sanitize_filename
)


# Ручной маппинг проблемных файлов
MANUAL_MAPPINGS = {
    # Brave - Храбрая сердцем
    "Brave.2012.Rus.Video.BDRip.1080p.dfcbit.mkv": {
        "search_title": "Brave",
        "year": "2012"
    },

    # Упс... Приплыли (первая часть)
    "UpZZ...NO1Y.UpLL1LLL.2015.D.HDRip.1400MB.avi": {
        "manual_title": "Упс... Ной уплыл",
        "year": "2015"
    },

    # WALL-E
    "WALL.E.(2008).BDRip.720p.[envy].[60fps].mkv": {
        "manual_title": "WALL-E",
        "year": "2008"
    },

    # Вверх
    "Vverh.(2009).BDRip.720p.[envy].[60fps].mkv": {
        "search_title": "Up",
        "year": "2009"
    },

    # Как приручить дракона
    "Как приручить дракона (2010) BDRip 720p [envy] [60fps].mkv": {
        "search_title": "How to Train Your Dragon",
        "year": "2010"
    },

    # Как приручить дракона 2
    "Как приручить дракона 2 (2014) BDRip 720p [envy] [60fps].mkv": {
        "search_title": "How to Train Your Dragon 2",
        "year": "2014"
    },

    # Клаус
    "Клаус_2019_WEB-DLRip.avi": {
        "search_title": "Klaus",
        "year": "2019"
    },

    # Русалочка (Disney)
    "Русалочка.mkv": {
        "search_title": "The Little Mermaid",
        "year": "1989"
    },

    # Холодное сердце
    "Холодное сердце.2013.HDRip.FD.avi": {
        "search_title": "Frozen",
        "year": "2013"
    },

    # Моана
    "Moana.2016.720p_BDRip_[scarabey.org].mkv": {
        "search_title": "Moana",
        "year": "2016"
    },

    # Барашек Шон
    "Барашек Шон.2015.720p.BluRay.x264-LEONARDO.mkv": {
        "search_title": "Shaun the Sheep Movie",
        "year": "2015"
    },
}


async def process_problematic_cartoon(filepath: str, filename: str) -> dict:
    """Обрабатывает один проблемный мультфильм"""

    result = {
        'original_name': filename,
        'original_path': filepath,
        'new_name': None,
        'new_path': None,
        'status': None,
        'error': None,
        'info': None
    }

    # Проверяем, есть ли ручной маппинг
    if filename not in MANUAL_MAPPINGS:
        result['status'] = 'error'
        result['error'] = 'Нет ручного маппинга для этого файла'
        return result

    mapping = MANUAL_MAPPINGS[filename]
    extension = Path(filename).suffix

    # Если есть готовое название (manual_title), используем его
    if 'manual_title' in mapping:
        title = mapping['manual_title']
        year = mapping.get('year', '')

        if year and year != 'NA':
            new_filename = sanitize_filename(f"{title} ({year}){extension}")
        else:
            new_filename = sanitize_filename(f"{title}{extension}")

        result['status'] = 'success'
        result['new_name'] = new_filename
        result['new_path'] = str(Path(filepath).parent / new_filename)
        result['info'] = {'title': title, 'year': year, 'source': 'Manual'}
        return result

    # Получаем информацию из TMDb
    search_title = mapping['search_title']
    year = mapping.get('year', '')

    print(f"  🔍 Поиск в TMDb: '{search_title}' ({year})")

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

    # Формируем новый путь
    new_path = str(Path(filepath).parent / new_filename)

    # Проверяем, не существует ли уже файл
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


def find_problematic_cartoons() -> list:
    """Находит все проблемные мультфильмы в библиотеке"""
    cartoons_path = Path(VIDEOS_ROOT) / CARTOONS_FOLDER
    problematic_files = []

    for root, dirs, files in os.walk(cartoons_path):
        for file in files:
            if file in MANUAL_MAPPINGS:
                full_path = Path(root) / file
                problematic_files.append({
                    'path': str(full_path),
                    'name': file
                })

    return problematic_files


def generate_report(results: list, output_file: str = 'problematic_cartoons_report.md'):
    """Генерирует отчёт об обработке проблемных мультфильмов"""

    success = [r for r in results if r['status'] == 'success']
    errors = [r for r in results if r['status'] == 'error']

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('# Отчёт об обработке проблемных мультфильмов\n\n')
        f.write(f'**Дата создания:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write('> ⚠️ **ВНИМАНИЕ:** Это предварительный отчёт. Файлы НЕ были переименованы.\n\n')

        # Статистика
        f.write('## Статистика\n\n')
        f.write(f'- **Всего обработано:** {len(results)} файлов\n')
        f.write(f'- **✅ Готовы к переименованию:** {len(success)} файлов\n')
        f.write(f'- **❌ Ошибки:** {len(errors)} файлов\n\n')

        # Успешные
        if success:
            f.write('## Таблица "Было → Стало"\n\n')
            f.write('| № | Было | Стало | Источник |\n')
            f.write('|---|------|-------|----------|\\n')
            for idx, r in enumerate(success, 1):
                old = r['original_name'].replace('|', '\\|')
                new = r['new_name'].replace('|', '\\|')
                source = r.get('info', {}).get('source', 'TMDb')
                f.write(f'| {idx} | {old} | {new} | {source} |\n')
            f.write('\n')

        # Ошибки
        if errors:
            f.write('## Файлы с ошибками\n\n')
            f.write('| № | Имя файла | Проблема |\n')
            f.write('|---|-----------|----------|\\n')
            for idx, r in enumerate(errors, 1):
                name = r['original_name'].replace('|', '\\|')
                error = r['error'].replace('|', '\\|')
                f.write(f'| {idx} | {name} | {error} |\n')
            f.write('\n')

        f.write('---\n')
        f.write(f'\n*Отчёт сгенерирован автоматически {datetime.now().strftime("%Y-%m-%d в %H:%M:%S")}*\n')

    print(f'\n✅ Отчёт сохранён: {output_file}')


async def main():
    """Основная функция"""
    import os

    print('\n' + '='*80)
    print('🔧 ОБРАБОТКА ПРОБЛЕМНЫХ МУЛЬТФИЛЬМОВ')
    print('='*80 + '\n')

    # Находим проблемные файлы
    print('🔍 Поиск проблемных мультфильмов...')
    problematic = find_problematic_cartoons()
    print(f'✅ Найдено {len(problematic)} проблемных файлов\n')

    if not problematic:
        print('❌ Проблемные мультфильмы не найдены!')
        return

    print('=' * 80)
    print('📝 АНАЛИЗ ФАЙЛОВ')
    print('=' * 80 + '\n')

    # Обрабатываем каждый файл
    results = []
    for idx, file_info in enumerate(problematic, 1):
        print(f'[{idx}/{len(problematic)}] {file_info["name"]}')
        result = await process_problematic_cartoon(file_info['path'], file_info['name'])
        results.append(result)

        if result['status'] == 'success':
            print(f'  ✅ → {result["new_name"]}')
        else:
            print(f'  ❌ {result["error"]}')

        # Задержка для API
        if result['status'] == 'success' and result.get('info', {}).get('source') != 'Manual':
            await asyncio.sleep(0.3)

    # Генерируем отчёт
    print('\n' + '=' * 80)
    print('📊 ГЕНЕРАЦИЯ ОТЧЁТА')
    print('=' * 80)
    generate_report(results)

    # Итоги
    success = len([r for r in results if r['status'] == 'success'])
    errors = len([r for r in results if r['status'] == 'error'])

    print('\n' + '=' * 80)
    print('✅ ЗАВЕРШЕНО')
    print('=' * 80)
    print(f'Всего обработано:      {len(results)}')
    print(f'✅ Готовы:             {success}')
    print(f'❌ Ошибки:             {errors}')
    print('=' * 80 + '\n')


if __name__ == "__main__":
    asyncio.run(main())
