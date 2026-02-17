#!/usr/bin/env python3
"""
MCP Server для работы с локальной видеотекой.
Сканирует папки с фильмами и мультиками, получает информацию из OMDb API.
"""

import os
import re
import json
import asyncio
import subprocess
import sys
import io
import logging
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import tmdbsimple as tmdb
from googlesearch import search
from bs4 import BeautifulSoup

# Настройка кодировки для Windows консоли
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка логирования
LOG_PATH = Path(__file__).parent / "mcp_server.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Загрузка конфигурации
CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config() -> dict:
    """Загружает конфигурацию из файла."""
    default_config = {
        "videos_root": "T:\\",
        "movies_folder": "Фильмы",
        "cartoons_folder": "Мультики",
        "video_extensions": [".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".m2ts"]
    }

    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception:
            pass

    return default_config

CONFIG = load_config()
VIDEOS_ROOT = CONFIG["videos_root"]
MOVIES_FOLDER = CONFIG["movies_folder"]
CARTOONS_FOLDER = CONFIG["cartoons_folder"]
VIDEO_EXTENSIONS = set(CONFIG["video_extensions"])

# OMDb API ключ (бесплатный, нужно получить на http://www.omdbapi.com/apikey.aspx)
OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")

# TMDb API ключ (бесплатный, получить на https://www.themoviedb.org/settings/api)
TMDB_API_KEY = CONFIG.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY", "")

# Kinopoisk API ключ (получить на https://kinopoiskapiunofficial.tech/)
KINOPOISK_API_KEY = CONFIG.get("kinopoisk_api_key") or os.environ.get("KINOPOISK_API_KEY", "")

# Настройка TMDb API
if TMDB_API_KEY:
    tmdb.API_KEY = TMDB_API_KEY

server = Server("videolibrary")


@dataclass
class VideoFile:
    """Информация о видеофайле."""
    name: str
    path: str
    size_mb: float
    extension: str
    folder: str


def transliterate_to_cyrillic(text: str) -> str:
    """Транслитерирует текст с латиницы на кириллицу (обратная транслитерация)."""
    # Словарь для транслитерации латиницы → кириллица
    # Включает множественные варианты написания одной буквы
    translit_map = {
        # Длинные комбинации (обрабатываем первыми)
        'shch': 'щ', 'shh': 'щ', 'sch': 'щ', 'shhh': 'щ',
        'zh': 'ж', 'ch': 'ч', 'sh': 'ш', 'yo': 'ё',
        'yu': 'ю', 'ya': 'я', 'kh': 'х', 'ts': 'ц',
        'ju': 'ю', 'ja': 'я', 'je': 'е', 'jo': 'ё',
        'eh': 'э', 'yy': 'ы', 'yi': 'ы', 'yh': 'ы',
        # Одиночные буквы
        'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д',
        'e': 'е', 'z': 'з', 'i': 'и', 'j': 'й', 'k': 'к',
        'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п',
        'r': 'р', 's': 'с', 't': 'т', 'u': 'у', 'f': 'ф',
        'h': 'х', 'c': 'ц', 'y': 'ы', 'w': 'в', 'x': 'кс',
        'q': 'к', "'": '', '"': ''
    }

    result = text.lower()

    # Сначала заменяем длинные комбинации (2-4 символа), потом короткие
    for lat, cyr in sorted(translit_map.items(), key=lambda x: -len(x[0])):
        result = result.replace(lat, cyr)

    # Специальные замены для частых ошибок ПОСЛЕ общей транслитерации
    # (когда текст уже в кириллице, но с ошибками)
    post_translit_fixes = {
        'стракса': 'страха',  # xa -> ха (не кса)
        'присыцтвие': 'присутствие',  # правильное написание
        'осеро': 'озеро',  # правильное написание
    }

    for wrong, correct in post_translit_fixes.items():
        result = result.replace(wrong, correct)

    return result


def sanitize_filename(name: str) -> str:
    """Убирает недопустимые символы из имени файла."""
    # Символы, запрещённые в Windows
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    # Убираем лишние пробелы
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def clean_movie_name(filename: str) -> str:
    """Очищает название файла для поиска в TMDb."""
    name = Path(filename).stem

    # ШАГ 0: Убираем номера в начале файла (например, "01.", "02.", "1 -", "2.")
    # Сначала убираем префиксы с решеткой: "5#Name" → "Name", "#01 Name" → "Name"
    name = re.sub(r'^\d+#', '', name)  # Убираем "5#"
    name = re.sub(r'^#\d+[\s._-]+', '', name)  # Убираем "#01 "
    # Затем убираем числовые префиксы, КРОМЕ случаев типа "1 Harry Potter" (для сохранения порядка серий)
    if not re.match(r'^\d+ [A-ZА-ЯЁ]', name):
        name = re.sub(r'^\d+[\s._-]+', '', name)

    # ШАГ 1: Убираем год в скобках или квадратных скобках
    name = re.sub(r"[\(\[]\d{4}[\)\]]", "", name)

    # ШАГ 2: Убираем оставшиеся круглые скобки и их содержимое, заменяя на пробел
    # Это предотвращает слипание слов (напр. "Prometheus(Extended)BDRip" → "Prometheus BDRip")
    name = re.sub(r'\([^)]*\)', " ", name)

    # ШАГ 3: КРИТИЧНО - Отбрасываем всё после разрешения/качества/кодека
    # После этих меток обычно идёт только мусор (группы релизов и т.д.)
    # ВАЖНО: Ищем САМОЕ РАННЕЕ вхождение среди всех паттернов
    cutoff_patterns = [
        r'[._\s](1080p|720p|480p|2160p|4k|UHD)',
        r'[._\s](HDRip|BDRip|BluRay|WEB-?DL(?:Rip)?|DVDRip|HDTV|WEBRip|BDRemux|REMUX)',
        r'[._\s](x264|x265|HEVC|AVC|h264|h265|XviD|DivX)',  # Кодеки
        r'[._\s](AAC|DTS|AC3|DD5)',  # Аудио кодеки
    ]
    earliest_match = None
    earliest_pos = len(name)

    for pattern in cutoff_patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if match and match.start() < earliest_pos:
            earliest_match = match
            earliest_pos = match.start()

    if earliest_match:
        # Обрезаем всё начиная с разделителя перед паттерном
        name = name[:earliest_match.start()]

    # Убираем всё в квадратных скобках (часто там теги)
    name = re.sub(r'\[.*?\]', "", name)

    # Убираем качество и прочие теги с разными разделителями (точка, пробел, подчеркивание)
    patterns_to_remove = [
        r'[._\s](1080p|720p|480p|2160p|4k|UHD)([._\s]|$)',
        r'[._\s](HDRip|BDRip|BluRay|WEB-?DL|DVDRip|HDTV|WEBRip|BDRemux|REMUX)([._\s]|$)',
        r'[._\s](x264|x265|HEVC|AVC|h264|h265)([._\s]|$)',
        r'[._\s](AAC|DTS|AC3|DD5[._]?1?|TrueHD|DDP5[._]?1?|DD\d[._]?\d?)([._\s]|$)',
        r'[._\s](Rus|Eng|ENG|RUS|DUAL|MVO|AVO|VO|UKR)([._\s]|$)',
        r'[._\s](NF|AMZN|DSNP|HBO|HULU)([._\s]|$)',
        r'[._\s](Open[._]?Matte|Extended|Unrated|IMAX)([._\s]|$)',
        r'[._\s]\d+bit([._\s]|$)',  # 10bit, etc
        r'[._\s](60\s?FPS)([._\s]|$)',  # FPS
        r'[._\s]by[._\s]\w+',  # "by TCG", "By EXCLUSIF" etc
        r'-(RARBG|YIFY|ETRG|FGT|FLEET|SPARKS|DEFLATE|CHD|NTb|HELLYWOOD|AsiaOne|Delia|ExKinoRay|HDUploaders|TCG|EXCLUSIF)([._\s]|$)',
    ]

    for pattern in patterns_to_remove:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)

    # Убираем оставшиеся круглые скобки (после удаления года)
    name = re.sub(r'\(.*?\)', "", name)

    # Теперь заменяем точки и подчеркивания на пробелы
    name = name.replace(".", " ").replace("_", " ")

    # Удаляем оставшиеся годы без скобок
    name = re.sub(r'\b\d{4}\b', "", name)

    # Убираем лишние пробелы
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_year(filename: str) -> Optional[int]:
    """Извлекает год из названия файла."""
    match = re.search(r"[\(\[]?(\d{4})[\)\]]?", filename)
    if match:
        year = int(match.group(1))
        if 1900 <= year <= 2030:
            return year
    return None


def scan_folder(folder_path: Path, category: str) -> list[VideoFile]:
    """Сканирует папку и возвращает список видеофайлов."""
    logger.info(f"   📂 Сканирование {category}: {folder_path}")
    videos = []

    if not folder_path.exists():
        logger.info(f"   ⚠️  Папка не найдена")
        return videos

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in VIDEO_EXTENSIONS:
                full_path = Path(root) / file
                try:
                    size_mb = full_path.stat().st_size / (1024 * 1024)
                    videos.append(VideoFile(
                        name=file,
                        path=str(full_path),
                        size_mb=round(size_mb, 2),
                        extension=ext,
                        folder=category
                    ))
                except OSError:
                    continue

    logger.info(f"   📊 Найдено: {len(videos)} файлов")
    return videos


def get_video_metadata(filepath: str) -> dict:
    """Получает метаданные видеофайла через FFprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            filepath
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"error": "FFprobe не найден или произошла ошибка. Установите FFmpeg: https://ffmpeg.org/download.html"}

        data = json.loads(result.stdout)

        # Извлекаем информацию о видеопотоке
        video_stream = None
        audio_streams = []

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video' and not video_stream:
                video_stream = stream
            elif stream.get('codec_type') == 'audio':
                audio_streams.append(stream)

        # Формируем результат
        metadata = {
            "filename": Path(filepath).name,
            "filepath": filepath
        }

        # Информация о формате
        format_info = data.get('format', {})
        duration_sec = float(format_info.get('duration', 0))
        hours = int(duration_sec // 3600)
        minutes = int((duration_sec % 3600) // 60)
        seconds = int(duration_sec % 60)

        metadata["format"] = {
            "container": format_info.get('format_long_name', 'Unknown'),
            "duration": f"{hours}:{minutes:02d}:{seconds:02d}",
            "duration_seconds": round(duration_sec, 2),
            "size_mb": round(int(format_info.get('size', 0)) / (1024 * 1024), 2),
            "bitrate_kbps": round(int(format_info.get('bit_rate', 0)) / 1000)
        }

        # Информация о видео
        if video_stream:
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)

            # Определяем качество
            if height >= 2160:
                quality = "4K UHD"
            elif height >= 1080:
                quality = "Full HD (1080p)"
            elif height >= 720:
                quality = "HD (720p)"
            elif height >= 480:
                quality = "SD (480p)"
            else:
                quality = "Low"

            # Частота кадров
            fps_str = video_stream.get('r_frame_rate', '0/1')
            try:
                num, den = map(int, fps_str.split('/'))
                fps = round(num / den, 2) if den else 0
            except:
                fps = 0

            metadata["video"] = {
                "codec": video_stream.get('codec_long_name', video_stream.get('codec_name', 'Unknown')),
                "codec_short": video_stream.get('codec_name', 'Unknown'),
                "resolution": f"{width}x{height}",
                "width": width,
                "height": height,
                "quality": quality,
                "fps": fps,
                "bitrate_kbps": round(int(video_stream.get('bit_rate', 0)) / 1000) if video_stream.get('bit_rate') else None,
                "pixel_format": video_stream.get('pix_fmt', 'Unknown'),
                "hdr": "HDR" if video_stream.get('color_transfer') in ['smpte2084', 'arib-std-b67'] else "SDR"
            }

        # Информация об аудио
        if audio_streams:
            metadata["audio"] = []
            for audio in audio_streams:
                channels = audio.get('channels', 0)
                if channels == 1:
                    channel_layout = "Mono"
                elif channels == 2:
                    channel_layout = "Stereo"
                elif channels == 6:
                    channel_layout = "5.1"
                elif channels == 8:
                    channel_layout = "7.1"
                else:
                    channel_layout = audio.get('channel_layout', f"{channels} channels")

                audio_info = {
                    "codec": audio.get('codec_long_name', audio.get('codec_name', 'Unknown')),
                    "codec_short": audio.get('codec_name', 'Unknown'),
                    "channels": channel_layout,
                    "sample_rate": f"{int(audio.get('sample_rate', 0)) // 1000} kHz" if audio.get('sample_rate') else None,
                    "bitrate_kbps": round(int(audio.get('bit_rate', 0)) / 1000) if audio.get('bit_rate') else None,
                    "language": audio.get('tags', {}).get('language', 'Unknown')
                }
                metadata["audio"].append(audio_info)

        return metadata

    except subprocess.TimeoutExpired:
        return {"error": "Превышено время ожидания FFprobe"}
    except FileNotFoundError:
        return {"error": "FFprobe не найден. Установите FFmpeg: https://ffmpeg.org/download.html"}
    except json.JSONDecodeError:
        return {"error": "Ошибка парсинга ответа FFprobe"}
    except Exception as e:
        return {"error": f"Ошибка: {str(e)}"}


async def fetch_movie_info(title: str, year: Optional[int] = None) -> dict:
    """Получает информацию о фильме из OMDb API."""
    logger.info(f"   🌐 OMDb API → \"{title}\"" + (f" ({year})" if year else ""))

    if not OMDB_API_KEY:
        logger.info(f"   ❌ OMDb: ключ не настроен")
        return {"error": "OMDB_API_KEY не установлен. Получите бесплатный ключ на http://www.omdbapi.com/apikey.aspx"}

    params = {
        "apikey": OMDB_API_KEY,
        "t": title,
        "plot": "full"
    }
    if year:
        params["y"] = str(year)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://www.omdbapi.com/", params=params)
            data = response.json()

            if data.get("Response") == "False":
                logger.info(f"   ❌ OMDb: {data.get('Error', 'не найдено')}")
                return {"error": data.get("Error", "Фильм не найден")}

            logger.info(f"   ✅ OMDb: {data.get('Title')} ({data.get('Year')})")
            return {
                "title": data.get("Title"),
                "year": data.get("Year"),
                "rated": data.get("Rated"),
                "released": data.get("Released"),
                "runtime": data.get("Runtime"),
                "genre": data.get("Genre"),
                "director": data.get("Director"),
                "actors": data.get("Actors"),
                "plot": data.get("Plot"),
                "language": data.get("Language"),
                "country": data.get("Country"),
                "awards": data.get("Awards"),
                "poster": data.get("Poster"),
                "imdb_rating": data.get("imdbRating"),
                "imdb_votes": data.get("imdbVotes"),
                "imdb_id": data.get("imdbID"),
                "type": data.get("Type"),
                "box_office": data.get("BoxOffice")
            }
        except Exception as e:
            logger.info(f"   ❌ OMDb: {e}")
            return {"error": f"Ошибка при запросе к OMDb: {str(e)}"}


async def fetch_movie_info_tmdb(title: str, year: Optional[int] = None) -> dict:
    """Получает информацию о фильме из TMDb API."""
    logger.info(f"   🌐 TMDb → \"{title}\"" + (f" ({year})" if year else ""))

    if not TMDB_API_KEY:
        logger.info(f"   ❌ TMDb: ключ не настроен")
        return {"error": "TMDB_API_KEY не установлен. Получите бесплатный ключ на https://www.themoviedb.org/settings/api"}

    def _fetch():
        try:
            # Попытка 1: Поиск с полным названием
            search = tmdb.Search()
            if year:
                search.movie(query=title, year=year, language='en-US')
            else:
                search.movie(query=title, language='en-US')

            # Попытка 2: Если не нашли, попробуем упростить название (первые 3 слова)
            if not search.results and len(title.split()) > 3:
                simplified_title = ' '.join(title.split()[:3])
                logger.info(f"   ↳ не нашли, пробуем \"{simplified_title}\"")
                if year:
                    search.movie(query=simplified_title, year=year)
                else:
                    search.movie(query=simplified_title)

            # Попытка 3: Еще проще - только первые 2 слова
            if not search.results and len(title.split()) > 2:
                simplified_title = ' '.join(title.split()[:2])
                logger.info(f"   ↳ не нашли, пробуем \"{simplified_title}\"")
                if year:
                    search.movie(query=simplified_title, year=year)
                else:
                    search.movie(query=simplified_title)

            # Попытка 4: Самое простое - только ПЕРВОЕ слово + год
            if not search.results and len(title.split()) > 1 and year:
                first_word = title.split()[0]
                logger.info(f"   ↳ не нашли, пробуем \"{first_word}\" + {year}")
                search.movie(query=first_word, year=year)

            # Попытка 5: Транслитерация (латиница → кириллица)
            if not search.results:
                # Проверяем, есть ли в названии латинские буквы
                if any(c.isascii() and c.isalpha() for c in title):
                    translit_title = transliterate_to_cyrillic(title)
                    logger.info(f"   ↳ транслитерация: \"{translit_title}\"")
                    if year:
                        search.movie(query=translit_title, year=year)
                    else:
                        search.movie(query=translit_title)

            if not search.results:
                return {"error": f"Фильм '{title}' не найден в TMDb"}

            # Берем первый результат
            movie_data = search.results[0]
            movie_id = movie_data['id']

            # Получаем детальную информацию о фильме (с русским языком)
            movie = tmdb.Movies(movie_id)
            movie_info = movie.info(language='ru-RU')

            # Получаем информацию о актерах и режиссерах
            credits = movie.credits()

            # Извлекаем режиссеров
            directors = [crew['name'] for crew in credits.get('crew', []) if crew.get('job') == 'Director']
            director_str = ', '.join(directors[:3]) if directors else "N/A"

            # Извлекаем актеров
            actors = [cast['name'] for cast in credits.get('cast', [])[:5]]
            actor_str = ', '.join(actors) if actors else "N/A"

            # Извлекаем жанры
            genres = [genre['name'] for genre in movie_info.get('genres', [])]
            genre_str = ', '.join(genres) if genres else "N/A"

            # Извлекаем страны
            countries = [country['name'] for country in movie_info.get('production_countries', [])]
            country_str = ', '.join(countries) if countries else "N/A"

            # Формируем ответ в формате, совместимом с OMDb
            return {
                "title": movie_info.get('title', 'N/A'),
                "year": movie_info.get('release_date', 'N/A')[:4] if movie_info.get('release_date') else 'N/A',
                "rated": 'N/A',  # TMDb не предоставляет рейтинг возраста напрямую
                "released": movie_info.get('release_date', 'N/A'),
                "runtime": f"{movie_info.get('runtime', 'N/A')} min" if movie_info.get('runtime') else 'N/A',
                "genre": genre_str,
                "director": director_str,
                "actors": actor_str,
                "plot": movie_info.get('overview', 'N/A'),
                "language": movie_info.get('original_language', 'N/A'),
                "country": country_str,
                "awards": 'N/A',
                "poster": f"https://image.tmdb.org/t/p/original{movie_info.get('poster_path')}" if movie_info.get('poster_path') else 'N/A',
                "imdb_rating": str(movie_info.get('vote_average', 'N/A')),
                "imdb_votes": str(movie_info.get('vote_count', 'N/A')),
                "imdb_id": movie_info.get('imdb_id', 'N/A'),
                "type": "movie",
                "box_office": f"${movie_info.get('revenue', 0):,}" if movie_info.get('revenue') else 'N/A'
            }
        except Exception as e:
            return {"error": f"Ошибка при запросе к TMDb: {str(e)}"}

    # Выполняем синхронную функцию в отдельном потоке
    result = await asyncio.to_thread(_fetch)

    if "error" in result:
        logger.info(f"   ❌ TMDb: {result['error']}")
    else:
        logger.info(f"   ✅ TMDb: {result.get('title')} ({result.get('year')})")

    return result


async def fetch_tv_show_info_tmdb(title: str, year: Optional[int] = None) -> dict:
    """Получает информацию о ТВ-сериале из TMDb API."""
    logger.info(f"   🌐 TMDb TV → \"{title}\"" + (f" ({year})" if year else ""))

    if not TMDB_API_KEY:
        logger.info(f"   ❌ TMDb TV: ключ не настроен")
        return {"error": "TMDB_API_KEY не установлен"}

    def _fetch():
        try:
            # Поиск TV series (не movie!)
            search = tmdb.Search()
            if year:
                search.tv(query=title, first_air_date_year=year, language='en-US')
            else:
                search.tv(query=title, language='en-US')

            # Если не нашли - упрощаем название
            if not search.results and len(title.split()) > 2:
                simplified_title = ' '.join(title.split()[:2])
                logger.info(f"   ↳ не нашли, пробуем \"{simplified_title}\"")
                if year:
                    search.tv(query=simplified_title, first_air_date_year=year)
                else:
                    search.tv(query=simplified_title)

            # Попытка транслитерации
            if not search.results and any(c.isascii() and c.isalpha() for c in title):
                translit_title = transliterate_to_cyrillic(title)
                logger.info(f"   ↳ транслитерация: \"{translit_title}\"")
                if year:
                    search.tv(query=translit_title, first_air_date_year=year)
                else:
                    search.tv(query=translit_title)

            if not search.results:
                return {"error": f"Сериал '{title}' не найден в TMDb"}

            # Берем первый результат
            tv_data = search.results[0]
            tv_id = tv_data['id']

            # Получаем детальную информацию (с русским языком)
            tv = tmdb.TV(tv_id)
            tv_info = tv.info(language='ru-RU')

            # Формируем ответ
            return {
                "title": tv_info.get('name', 'N/A'),
                "year": tv_info.get('first_air_date', 'N/A')[:4] if tv_info.get('first_air_date') else 'N/A',
                "type": "tv",
            }
        except Exception as e:
            return {"error": f"Ошибка при запросе к TMDb TV: {str(e)}"}

    result = await asyncio.to_thread(_fetch)

    if "error" in result:
        logger.info(f"   ❌ TMDb TV: {result['error']}")
    else:
        logger.info(f"   ✅ TMDb TV: {result.get('title')} ({result.get('year')})")

    return result


async def fetch_movie_info_kinopoisk(title: str, year: Optional[int] = None) -> dict:
    """Получает информацию о фильме из Kinopoisk API."""
    logger.info(f"   🌐 Kinopoisk → \"{title}\"" + (f" ({year})" if year else ""))

    if not KINOPOISK_API_KEY:
        logger.info(f"   ❌ Kinopoisk: ключ не настроен")
        return {"error": "KINOPOISK_API_KEY не установлен. Получите бесплатный ключ на https://kinopoiskapiunofficial.tech/"}

    async with httpx.AsyncClient() as client:
        try:
            # Шаг 1: Поиск фильма по названию
            search_url = "https://kinopoiskapiunofficial.tech/api/v2.1/films/search-by-keyword"
            headers = {"X-API-KEY": KINOPOISK_API_KEY}
            params = {"keyword": title}

            response = await client.get(search_url, headers=headers, params=params)
            response.raise_for_status()
            search_data = response.json()

            films = search_data.get("films", [])
            if not films:
                # Попытка 2: Упрощаем название (первые 3 слова)
                if len(title.split()) > 3:
                    simplified_title = ' '.join(title.split()[:3])
                    logger.info(f"   ↳ не нашли, пробуем \"{simplified_title}\"")
                    params = {"keyword": simplified_title}
                    response = await client.get(search_url, headers=headers, params=params)
                    response.raise_for_status()
                    search_data = response.json()
                    films = search_data.get("films", [])

                # Попытка 3: Еще проще (первые 2 слова)
                if not films and len(title.split()) > 2:
                    simplified_title = ' '.join(title.split()[:2])
                    logger.info(f"   ↳ не нашли, пробуем \"{simplified_title}\"")
                    params = {"keyword": simplified_title}
                    response = await client.get(search_url, headers=headers, params=params)
                    response.raise_for_status()
                    search_data = response.json()
                    films = search_data.get("films", [])

                # Попытка 4: Только первое слово
                if not films and len(title.split()) > 1:
                    first_word = title.split()[0]
                    logger.info(f"   ↳ не нашли, пробуем \"{first_word}\"")
                    params = {"keyword": first_word}
                    response = await client.get(search_url, headers=headers, params=params)
                    response.raise_for_status()
                    search_data = response.json()
                    films = search_data.get("films", [])

                # Попытка 5: Транслитерация (латиница → кириллица)
                if not films and any(c.isascii() and c.isalpha() for c in title):
                    translit_title = transliterate_to_cyrillic(title)
                    logger.info(f"   ↳ транслитерация: \"{translit_title}\"")
                    params = {"keyword": translit_title}
                    response = await client.get(search_url, headers=headers, params=params)
                    response.raise_for_status()
                    search_data = response.json()
                    films = search_data.get("films", [])

            if not films:
                logger.info(f"   ❌ Kinopoisk: фильм не найден")
                return {"error": f"Фильм '{title}' не найден на Кинопоиске"}

            # Фильтруем по году, если указан
            best_match = None
            if year:
                for film in films:
                    film_year = film.get("year")
                    if film_year and str(film_year) == str(year):
                        best_match = film
                        break

            # Если не нашли по году или год не указан, берем первый результат
            if not best_match:
                best_match = films[0]

            kinopoisk_id = best_match.get("filmId")
            if not kinopoisk_id:
                logger.info(f"   ❌ Kinopoisk: не удалось получить ID")
                return {"error": "Не удалось получить ID фильма"}

            # Шаг 2: Получаем подробную информацию о фильме
            details_url = f"https://kinopoiskapiunofficial.tech/api/v2.2/films/{kinopoisk_id}"
            response = await client.get(details_url, headers=headers)
            response.raise_for_status()
            movie_info = response.json()

            # Извлекаем информацию
            russian_title = movie_info.get("nameRu") or movie_info.get("nameOriginal", "N/A")
            original_title = movie_info.get("nameOriginal", "N/A")
            movie_year = str(movie_info.get("year", "N/A"))

            # Получаем режиссёров и актёров из staff
            staff_url = f"https://kinopoiskapiunofficial.tech/api/v1/staff"
            response = await client.get(staff_url, headers=headers, params={"filmId": kinopoisk_id})
            response.raise_for_status()
            staff_data = response.json()

            directors = [person["nameRu"] or person.get("nameEn", "") for person in staff_data if person.get("professionKey") == "DIRECTOR"]
            actors = [person["nameRu"] or person.get("nameEn", "") for person in staff_data if person.get("professionKey") == "ACTOR"][:5]

            director_str = ', '.join(directors[:3]) if directors else "N/A"
            actor_str = ', '.join(actors) if actors else "N/A"

            # Извлекаем жанры
            genres = [genre["genre"] for genre in movie_info.get("genres", [])]
            genre_str = ', '.join(genres) if genres else "N/A"

            # Извлекаем страны
            countries = [country["country"] for country in movie_info.get("countries", [])]
            country_str = ', '.join(countries) if countries else "N/A"

            # Формируем ответ в формате, совместимом с нашим API
            logger.info(f"   ✅ Kinopoisk: {russian_title} ({movie_year})")
            return {
                "title": russian_title,  # Русское название
                "original_title": original_title,  # Оригинальное название
                "year": movie_year,
                "rated": "N/A",
                "released": str(movie_info.get("premiereRu", "N/A")),
                "runtime": f"{movie_info.get('filmLength', 'N/A')} min" if movie_info.get('filmLength') else 'N/A',
                "genre": genre_str,
                "director": director_str,
                "actors": actor_str,
                "plot": movie_info.get("description", "N/A"),
                "language": "N/A",
                "country": country_str,
                "awards": "N/A",
                "poster": movie_info.get("posterUrl", "N/A"),
                "imdb_rating": str(movie_info.get("ratingImdb", "N/A")),
                "kinopoisk_rating": str(movie_info.get("ratingKinopoisk", "N/A")),
                "imdb_votes": "N/A",
                "imdb_id": movie_info.get("imdbId", "N/A"),
                "kinopoisk_id": str(kinopoisk_id),
                "type": "movie",
                "box_office": "N/A"
            }
        except httpx.HTTPStatusError as e:
            logger.warning(f"   ❌ Kinopoisk HTTP {e.response.status_code}")
            if e.response.status_code == 402:
                return {"error": "Превышен лимит запросов к API Кинопоиска (500/день на бесплатном тарифе)"}
            return {"error": f"Ошибка HTTP при запросе к Кинопоиску: {e.response.status_code}"}
        except Exception as e:
            logger.warning(f"   ❌ Kinopoisk: {type(e).__name__}")
            return {"error": f"Кинопоиск недоступен: {type(e).__name__}"}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Возвращает список доступных инструментов."""
    return [
        Tool(
            name="list_movies",
            description="Получить список всех фильмов в видеотеке. Возвращает название, размер и путь к файлу.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (по умолчанию все)",
                        "default": 0
                    }
                }
            }
        ),
        Tool(
            name="list_cartoons",
            description="Получить список всех мультфильмов в видеотеке. Возвращает название, размер и путь к файлу.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (по умолчанию все)",
                        "default": 0
                    }
                }
            }
        ),
        Tool(
            name="get_movie_info",
            description="Получить подробную информацию о фильме из IMDb (через OMDb API). Включает рейтинг, актёров, режиссёра, описание и т.д.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Название фильма для поиска"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Год выпуска (опционально, для уточнения поиска)"
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="search_library",
            description="Поиск фильмов и мультиков по названию в локальной библиотеке.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос (часть названия)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Категория для поиска: movies, cartoons или all",
                        "enum": ["movies", "cartoons", "all"],
                        "default": "all"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_library_stats",
            description="Получить статистику по видеотеке: количество фильмов, мультиков, общий размер.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_movie_info_by_file",
            description="Получить информацию о фильме по имени файла из библиотеки. Автоматически очищает название и ищет в OMDb.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Имя файла из библиотеки"
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="rename_movie",
            description="Переименовать файл фильма в формат 'Название (Год) - Режиссёр.расширение'. Получает информацию из OMDb и переименовывает файл.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Полный путь к файлу фильма"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Если true, только показать новое имя без переименования",
                        "default": False
                    }
                },
                "required": ["filepath"]
            }
        ),
        Tool(
            name="get_video_metadata",
            description="Получить технические метаданные видеофайла: разрешение, кодек, битрейт, аудиодорожки и т.д. Требует установленный FFmpeg.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Полный путь к видеофайлу"
                    }
                },
                "required": ["filepath"]
            }
        )
    ]


def log_response(result: list[TextContent], elapsed: float = 0) -> list[TextContent]:
    """Логирует ответ сервера."""
    logger.info("-" * 100)
    logger.info(f"📤 ОТВЕТ (⏱  {elapsed:.2f}с)")
    logger.info("=" * 100)

    for i, content in enumerate(result):
        logger.info(f"📦 Результат [{i + 1}]:")

        # Если результат большой, показываем только первые строки
        text = content.text
        if len(text) > 1000:
            lines = text.split('\n')
            preview_lines = lines[:15]
            remaining_lines = len(lines) - 15

            logger.info("   " + "\n   ".join(preview_lines))
            if remaining_lines > 0:
                logger.info(f"   ... (еще {remaining_lines} строк, всего {len(text)} символов)")
        else:
            # Для коротких результатов выводим всё
            for line in text.split('\n'):
                logger.info(f"   {line}")

    logger.info("=" * 100)
    logger.info("")
    return result


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обрабатывает вызовы инструментов."""
    start_time = time.perf_counter()

    # ──── ВХОДЯЩИЙ ЗАПРОС ────
    logger.info("")
    logger.info("=" * 100)
    logger.info("🤖 ВХОДЯЩИЙ ЗАПРОС ОТ AI АГЕНТА (CLAUDE)")
    logger.info("=" * 100)
    logger.info(f"📥 Инструмент: {name}")
    logger.info(f"📋 Аргументы:")
    for key, value in arguments.items():
        logger.info(f"   • {key}: {value}")
    logger.info("-" * 100)
    logger.info("⚙️  Обработка:")

    # ──── ДИСПЕТЧЕР ТУЛОВ ────
    response = None

    if name == "list_movies":
        limit = arguments.get("limit", 0)
        movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER
        videos = scan_folder(movies_path, "movies")

        if limit > 0:
            videos = videos[:limit]
            logger.info(f"   ✂️  Лимит: показано {limit}")

        response = [TextContent(type="text", text=json.dumps({
            "count": len(videos),
            "movies": [asdict(v) for v in videos]
        }, ensure_ascii=False, indent=2))]

    elif name == "list_cartoons":
        limit = arguments.get("limit", 0)
        cartoons_path = Path(VIDEOS_ROOT) / CARTOONS_FOLDER
        videos = scan_folder(cartoons_path, "cartoons")

        if limit > 0:
            videos = videos[:limit]
            logger.info(f"   ✂️  Лимит: показано {limit}")

        response = [TextContent(type="text", text=json.dumps({
            "count": len(videos),
            "cartoons": [asdict(v) for v in videos]
        }, ensure_ascii=False, indent=2))]

    elif name == "get_movie_info":
        title = arguments.get("title", "")
        year = arguments.get("year")

        info = await fetch_movie_info_tmdb(title, year)
        response = [TextContent(type="text", text=json.dumps(info, ensure_ascii=False, indent=2))]

    elif name == "search_library":
        query = arguments.get("query", "").lower()
        category = arguments.get("category", "all")
        logger.info(f"   🔍 Запрос: \"{query}\" | Категория: {category}")

        results = []

        if category in ["movies", "all"]:
            movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER
            movies = scan_folder(movies_path, "movies")
            results.extend([v for v in movies if query in v.name.lower()])

        if category in ["cartoons", "all"]:
            cartoons_path = Path(VIDEOS_ROOT) / CARTOONS_FOLDER
            cartoons = scan_folder(cartoons_path, "cartoons")
            results.extend([v for v in cartoons if query in v.name.lower()])

        logger.info(f"   🎯 Совпадений: {len(results)}")
        response = [TextContent(type="text", text=json.dumps({
            "query": query,
            "count": len(results),
            "results": [asdict(v) for v in results]
        }, ensure_ascii=False, indent=2))]

    elif name == "get_library_stats":
        movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER
        cartoons_path = Path(VIDEOS_ROOT) / CARTOONS_FOLDER

        movies = scan_folder(movies_path, "movies")
        cartoons = scan_folder(cartoons_path, "cartoons")

        total_movies_size = sum(v.size_mb for v in movies)
        total_cartoons_size = sum(v.size_mb for v in cartoons)

        # Статистика по форматам
        movie_formats = {}
        for v in movies:
            movie_formats[v.extension] = movie_formats.get(v.extension, 0) + 1

        cartoon_formats = {}
        for v in cartoons:
            cartoon_formats[v.extension] = cartoon_formats.get(v.extension, 0) + 1

        logger.info(f"   📊 Фильмы:   {len(movies)} файлов | {round(total_movies_size / 1024, 2)} ГБ")
        logger.info(f"   📊 Мультики: {len(cartoons)} файлов | {round(total_cartoons_size / 1024, 2)} ГБ")

        response = [TextContent(type="text", text=json.dumps({
            "movies": {
                "count": len(movies),
                "total_size_gb": round(total_movies_size / 1024, 2),
                "formats": movie_formats
            },
            "cartoons": {
                "count": len(cartoons),
                "total_size_gb": round(total_cartoons_size / 1024, 2),
                "formats": cartoon_formats
            },
            "total": {
                "count": len(movies) + len(cartoons),
                "total_size_gb": round((total_movies_size + total_cartoons_size) / 1024, 2)
            }
        }, ensure_ascii=False, indent=2))]

    elif name == "get_movie_info_by_file":
        filename = arguments.get("filename", "")

        # Очищаем название файла
        clean_name = clean_movie_name(filename)
        year = extract_year(filename)
        logger.info(f"   🧹 Очищенное имя: \"{clean_name}\"  |  📅 Год: {year or 'не найден'}")

        info = await fetch_movie_info_tmdb(clean_name, year)
        info["original_filename"] = filename
        info["parsed_title"] = clean_name
        if year:
            info["parsed_year"] = year

        response = [TextContent(type="text", text=json.dumps(info, ensure_ascii=False, indent=2))]

    elif name == "rename_movie":
        filepath = arguments.get("filepath", "")
        dry_run = arguments.get("dry_run", False)

        file_path = Path(filepath)
        if not file_path.exists():
            logger.info(f"   ❌ Файл не найден: {filepath}")
            response = [TextContent(type="text", text=json.dumps({
                "error": f"Файл не найден: {filepath}"
            }, ensure_ascii=False, indent=2))]
        else:
            filename = file_path.name
            clean_name = clean_movie_name(filename)
            year = extract_year(filename)
            logger.info(f"   📂 Файл: {filename}")
            logger.info(f"   🧹 Очищенное имя: \"{clean_name}\"  |  📅 Год: {year or 'не найден'}")

            info = await fetch_movie_info_tmdb(clean_name, year)

            if "error" in info:
                response = [TextContent(type="text", text=json.dumps({
                    "error": f"Не удалось найти информацию о фильме: {info['error']}",
                    "original_file": filename,
                    "parsed_title": clean_name,
                    "parsed_year": year
                }, ensure_ascii=False, indent=2))]
            else:
                # Формируем новое имя файла
                title = info.get("title", clean_name)
                movie_year = info.get("year", str(year) if year else "")
                director = info.get("director", "Unknown")
                extension = file_path.suffix

                if director == "N/A":
                    director = "Unknown"

                new_filename = sanitize_filename(f"{title} ({movie_year}) - {director}{extension}")
                new_filepath = file_path.parent / new_filename
                logger.info(f"   📝 Новое имя: {new_filename}")

                rename_result = {
                    "original_file": filename,
                    "new_file": new_filename,
                    "original_path": str(file_path),
                    "new_path": str(new_filepath),
                    "movie_info": {
                        "title": title,
                        "year": movie_year,
                        "director": director
                    },
                    "dry_run": dry_run
                }

                if dry_run:
                    rename_result["status"] = "dry_run - файл не переименован"
                    logger.info(f"   ⏭️  dry_run — файл не переименован")
                else:
                    try:
                        file_path.rename(new_filepath)
                        rename_result["status"] = "success"
                        logger.info(f"   ✅ Переименован успешно")
                    except OSError as e:
                        rename_result["status"] = "error"
                        rename_result["error"] = str(e)
                        logger.info(f"   ❌ Ошибка переименования: {e}")

                response = [TextContent(type="text", text=json.dumps(rename_result, ensure_ascii=False, indent=2))]

    elif name == "get_video_metadata":
        filepath = arguments.get("filepath", "")

        file_path = Path(filepath)
        if not file_path.exists():
            logger.info(f"   ❌ Файл не найден: {filepath}")
            response = [TextContent(type="text", text=json.dumps({
                "error": f"Файл не найден: {filepath}"
            }, ensure_ascii=False, indent=2))]
        else:
            logger.info(f"   🔧 FFprobe: {file_path.name}")
            metadata = get_video_metadata(filepath)

            if "error" not in metadata:
                video = metadata.get("video", {})
                fmt = metadata.get("format", {})
                logger.info(f"   ✅ {video.get('resolution', '?')} | {video.get('codec_short', '?')} | {fmt.get('duration', '?')} | {video.get('quality', '?')}")
            else:
                logger.info(f"   ❌ FFprobe: {metadata['error']}")

            response = [TextContent(type="text", text=json.dumps(metadata, ensure_ascii=False, indent=2))]

    else:
        logger.info(f"   ❌ Неизвестный инструмент: {name}")
        response = [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    elapsed = time.perf_counter() - start_time
    return log_response(response, elapsed)


async def main():
    """Запуск MCP сервера."""
    logger.info("")
    logger.info("=" * 100)
    logger.info("🚀 MCP СЕРВЕР 'videolibrary' ЗАПУЩЕН")
    logger.info("=" * 100)
    logger.info(f"   📂 Фильмы:    {Path(VIDEOS_ROOT) / MOVIES_FOLDER}")
    logger.info(f"   📂 Мультики:  {Path(VIDEOS_ROOT) / CARTOONS_FOLDER}")
    logger.info(f"   🔑 TMDb API:  {'✅ настроен' if TMDB_API_KEY else '❌ не настроен'}")
    logger.info(f"   🔑 OMDb API:  {'✅ настроен' if OMDB_API_KEY else '❌ не настроен'}")
    logger.info(f"   🔑 Kinopoisk: {'✅ настроен' if KINOPOISK_API_KEY else '❌ не настроен'}")
    logger.info("=" * 100)
    logger.info("")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
