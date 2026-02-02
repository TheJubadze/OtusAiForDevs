#!/usr/bin/env python3
"""
Обработка проблемных файлов с ручным маппингом названий
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


# Ручной маппинг проблемных файлов
MANUAL_MAPPINGS = {
    # Пираты Карибского моря
    "1#Proklyatiye.Chyornoy.Zhemchuzhyny.2003.DUAL.BDRip.x264.-HELLYWOOD.mkv": {
        "search_title": "Pirates of the Caribbean The Curse of the Black Pearl",
        "year": "2003"
    },
    "2#Sunduk.Mertvetca.2006.DUAL.BDRip.x264.-HELLYWOOD.mkv": {
        "search_title": "Pirates of the Caribbean Dead Man's Chest",
        "year": "2006"
    },
    "5#Mertvetcy.ne.Rasskazyvayut.Skazki.2017.DUAL.BDRip.x264.-HELLYWOOD.mkv": {
        "search_title": "Pirates of the Caribbean Dead Men Tell No Tales",
        "year": "2017"
    },

    # Красавица и чудовище
    "Krasavitca.i.Chudovische.2017.2xRus.Eng.BDRip.720p.-HELLYWOOD.mkv": {
        "search_title": "Beauty and the Beast",
        "year": "2017"
    },

    # Даун Хаус
    "Daun.Haus.2007_[torrents.ru].avi": {
        "search_title": "Down House",
        "year": "2001"
    },

    # Унесённые ветром
    "Unesennye.vetrom.1.avi": {
        "search_title": "Gone with the Wind",
        "year": "1939",
        "part": "1"
    },
    "Unesennye.vetrom.2.avi": {
        "search_title": "Gone with the Wind",
        "year": "1939",
        "part": "2"
    },

    # Поющие в терновнике (сериал - используем ручное название)
    "Pojuschie.v.ternovnike.1.of.4.1983.DVDRip.DivX.Rus.fenixclub.com.avi": {
        "manual_title": "Поющие в терновнике",
        "year": "1983",
        "part": "1"
    },
    "Pojuschie.v.ternovnike.2.of.4.1983.DVDRip.DivX.Rus.fenixclub.com.avi": {
        "manual_title": "Поющие в терновнике",
        "year": "1983",
        "part": "2"
    },
    "Pojuschie.v.ternovnike.3.of.4.1983.DVDRip.DivX.Rus.fenixclub.com.avi": {
        "manual_title": "Поющие в терновнике",
        "year": "1983",
        "part": "3"
    },
    "Pojuschie.v.ternovnike.4.of.4.1983.www.victu.clan.su.avi": {
        "manual_title": "Поющие в терновнике",
        "year": "1983",
        "part": "4"
    },

    # Гарри Поттер (файл с номером 1)
    "1 (2001) - Shelly Silver.avi": {
        "search_title": "Harry Potter and the Philosopher's Stone",
        "year": "2001"
    },

    # Сокровища царя Соломона
    "King.Solomons.Mines.2004.Part.2.mkv": {
        "search_title": "King Solomon's Mines",
        "year": "2004",
        "part": "2"
    },
    "Сокровище царя Соломона (2001) - Carlos Saura.mkv": {
        "manual_title": "Сокровище царя Соломона",
        "year": "2001"
    },
}


# Файлы, которые нужно пропустить (технические)
SKIP_FILES = [
    "00003.m2ts",
    "00004.m2ts",
    "00005.m2ts"
]


async def process_problematic_file(filepath: str, filename: str) -> dict:
    """Обрабатывает один проблемный файл"""

    result = {
        'original_name': filename,
        'original_path': filepath,
        'new_name': None,
        'new_path': None,
        'status': None,
        'error': None,
        'info': None
    }

    # Проверяем, нужно ли пропустить файл
    if filename in SKIP_FILES:
        result['status'] = 'skipped'
        result['error'] = 'Технический файл - требует ручного определения'
        return result

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
        part = mapping.get('part', '')

        if part:
            new_filename = sanitize_filename(f"{title} ({year}) - Часть {part}{extension}")
        elif year and year != 'NA':
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
    part = mapping.get('part', '')

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

    if part:
        new_filename = sanitize_filename(f"{title} ({movie_year}) - Часть {part}{extension}")
    elif movie_year and movie_year != "NA":
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


def find_problematic_files() -> list:
    """Находит все проблемные файлы в библиотеке"""
    movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER
    problematic_files = []

    for root, dirs, files in os.walk(movies_path):
        for file in files:
            if file in MANUAL_MAPPINGS or file in SKIP_FILES:
                full_path = Path(root) / file
                problematic_files.append({
                    'path': str(full_path),
                    'name': file
                })

    return problematic_files


def generate_report(results: list, output_file: str = 'problematic_files_report.md'):
    """Генерирует отчёт об обработке проблемных файлов"""

    success = [r for r in results if r['status'] == 'success']
    errors = [r for r in results if r['status'] == 'error']
    skipped = [r for r in results if r['status'] == 'skipped']

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('# Отчёт об обработке проблемных файлов\n\n')
        f.write(f'**Дата создания:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write('> ⚠️ **ВНИМАНИЕ:** Это предварительный отчёт. Файлы НЕ были переименованы.\n\n')

        # Статистика
        f.write('## Статистика\n\n')
        f.write(f'- **Всего обработано:** {len(results)} файлов\n')
        f.write(f'- **✅ Готовы к переименованию:** {len(success)} файлов\n')
        f.write(f'- **⊘ Пропущено:** {len(skipped)} файлов\n')
        f.write(f'- **❌ Ошибки:** {len(errors)} файлов\n\n')

        # Успешные
        if success:
            f.write('## Таблица "Было → Стало"\n\n')
            f.write('| № | Было | Стало | Источник |\n')
            f.write('|---|------|-------|----------|\n')
            for idx, r in enumerate(success, 1):
                old = r['original_name'].replace('|', '\\|')
                new = r['new_name'].replace('|', '\\|')
                source = r.get('info', {}).get('source', 'TMDb')
                f.write(f'| {idx} | {old} | {new} | {source} |\n')
            f.write('\n')

        # Пропущенные
        if skipped:
            f.write('## Пропущенные файлы\n\n')
            f.write('| № | Имя файла | Причина |\n')
            f.write('|---|-----------|----------|\n')
            for idx, r in enumerate(skipped, 1):
                name = r['original_name'].replace('|', '\\|')
                reason = r['error'].replace('|', '\\|')
                f.write(f'| {idx} | {name} | {reason} |\n')
            f.write('\n')

        # Ошибки
        if errors:
            f.write('## Файлы с ошибками\n\n')
            f.write('| № | Имя файла | Проблема |\n')
            f.write('|---|-----------|----------|\n')
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
    print('🔧 ОБРАБОТКА ПРОБЛЕМНЫХ ФАЙЛОВ')
    print('='*80 + '\n')

    # Находим проблемные файлы
    print('🔍 Поиск проблемных файлов...')
    problematic = find_problematic_files()
    print(f'✅ Найдено {len(problematic)} проблемных файлов\n')

    if not problematic:
        print('❌ Проблемные файлы не найдены!')
        return

    print('=' * 80)
    print('📝 АНАЛИЗ ФАЙЛОВ')
    print('=' * 80 + '\n')

    # Обрабатываем каждый файл
    results = []
    for idx, file_info in enumerate(problematic, 1):
        print(f'[{idx}/{len(problematic)}] {file_info["name"]}')
        result = await process_problematic_file(file_info['path'], file_info['name'])
        results.append(result)

        if result['status'] == 'success':
            print(f'  ✅ → {result["new_name"]}')
        elif result['status'] == 'error':
            print(f'  ❌ {result["error"]}')
        else:
            print(f'  ⊘ {result["error"]}')

        # Задержка для API
        if result['status'] == 'success' and result.get('info', {}).get('source') == 'TMDb':
            await asyncio.sleep(0.3)

    # Генерируем отчёт
    print('\n' + '=' * 80)
    print('📊 ГЕНЕРАЦИЯ ОТЧЁТА')
    print('=' * 80)
    generate_report(results)

    # Итоги
    success = len([r for r in results if r['status'] == 'success'])
    errors = len([r for r in results if r['status'] == 'error'])
    skipped = len([r for r in results if r['status'] == 'skipped'])

    print('\n' + '=' * 80)
    print('✅ ЗАВЕРШЕНО')
    print('=' * 80)
    print(f'Всего обработано:      {len(results)}')
    print(f'✅ Готовы:             {success}')
    print(f'⊘ Пропущено:           {skipped}')
    print(f'❌ Ошибки:             {errors}')
    print('=' * 80 + '\n')


if __name__ == "__main__":
    asyncio.run(main())
