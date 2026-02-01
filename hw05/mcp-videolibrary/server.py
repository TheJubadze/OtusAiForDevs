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
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

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

server = Server("videolibrary")


@dataclass
class VideoFile:
    """Информация о видеофайле."""
    name: str
    path: str
    size_mb: float
    extension: str
    folder: str


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
    """Очищает название файла для поиска в OMDb."""
    name = Path(filename).stem
    # Убираем год в скобках или без
    name = re.sub(r"[\(\[]?\d{4}[\)\]]?", "", name)
    # Убираем качество и прочие теги
    name = re.sub(r"(1080p|720p|480p|2160p|4k|HDRip|BDRip|BluRay|WEB-?DL|DVDRip|HDTV|x264|x265|HEVC|AAC|DTS|Rus|Eng)", "", name, flags=re.IGNORECASE)
    # Убираем точки и подчеркивания
    name = name.replace(".", " ").replace("_", " ")
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
    videos = []

    if not folder_path.exists():
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
    if not OMDB_API_KEY:
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
                return {"error": data.get("Error", "Фильм не найден")}

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
            return {"error": f"Ошибка при запросе к OMDb: {str(e)}"}


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


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Обрабатывает вызовы инструментов."""

    if name == "list_movies":
        limit = arguments.get("limit", 0)
        movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER
        videos = scan_folder(movies_path, "movies")

        if limit > 0:
            videos = videos[:limit]

        result = {
            "count": len(videos),
            "movies": [asdict(v) for v in videos]
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "list_cartoons":
        limit = arguments.get("limit", 0)
        cartoons_path = Path(VIDEOS_ROOT) / CARTOONS_FOLDER
        videos = scan_folder(cartoons_path, "cartoons")

        if limit > 0:
            videos = videos[:limit]

        result = {
            "count": len(videos),
            "cartoons": [asdict(v) for v in videos]
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "get_movie_info":
        title = arguments.get("title", "")
        year = arguments.get("year")

        info = await fetch_movie_info(title, year)
        return [TextContent(type="text", text=json.dumps(info, ensure_ascii=False, indent=2))]

    elif name == "search_library":
        query = arguments.get("query", "").lower()
        category = arguments.get("category", "all")

        results = []

        if category in ["movies", "all"]:
            movies_path = Path(VIDEOS_ROOT) / MOVIES_FOLDER
            movies = scan_folder(movies_path, "movies")
            results.extend([v for v in movies if query in v.name.lower()])

        if category in ["cartoons", "all"]:
            cartoons_path = Path(VIDEOS_ROOT) / CARTOONS_FOLDER
            cartoons = scan_folder(cartoons_path, "cartoons")
            results.extend([v for v in cartoons if query in v.name.lower()])

        result = {
            "query": query,
            "count": len(results),
            "results": [asdict(v) for v in results]
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

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

        result = {
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
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "get_movie_info_by_file":
        filename = arguments.get("filename", "")

        # Очищаем название файла
        clean_name = clean_movie_name(filename)
        year = extract_year(filename)

        info = await fetch_movie_info(clean_name, year)
        info["original_filename"] = filename
        info["parsed_title"] = clean_name
        if year:
            info["parsed_year"] = year

        return [TextContent(type="text", text=json.dumps(info, ensure_ascii=False, indent=2))]

    elif name == "rename_movie":
        filepath = arguments.get("filepath", "")
        dry_run = arguments.get("dry_run", False)

        file_path = Path(filepath)
        if not file_path.exists():
            return [TextContent(type="text", text=json.dumps({
                "error": f"Файл не найден: {filepath}"
            }, ensure_ascii=False, indent=2))]

        # Получаем информацию о фильме
        filename = file_path.name
        clean_name = clean_movie_name(filename)
        year = extract_year(filename)

        info = await fetch_movie_info(clean_name, year)

        if "error" in info:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Не удалось найти информацию о фильме: {info['error']}",
                "original_file": filename,
                "parsed_title": clean_name,
                "parsed_year": year
            }, ensure_ascii=False, indent=2))]

        # Формируем новое имя файла
        title = info.get("title", clean_name)
        movie_year = info.get("year", str(year) if year else "")
        director = info.get("director", "Unknown")
        extension = file_path.suffix

        # Убираем "N/A" значения
        if director == "N/A":
            director = "Unknown"

        new_filename = sanitize_filename(f"{title} ({movie_year}) - {director}{extension}")
        new_filepath = file_path.parent / new_filename

        result = {
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
            result["status"] = "dry_run - файл не переименован"
        else:
            try:
                file_path.rename(new_filepath)
                result["status"] = "success"
            except OSError as e:
                result["status"] = "error"
                result["error"] = str(e)

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "get_video_metadata":
        filepath = arguments.get("filepath", "")

        file_path = Path(filepath)
        if not file_path.exists():
            return [TextContent(type="text", text=json.dumps({
                "error": f"Файл не найден: {filepath}"
            }, ensure_ascii=False, indent=2))]

        metadata = get_video_metadata(filepath)
        return [TextContent(type="text", text=json.dumps(metadata, ensure_ascii=False, indent=2))]

    else:
        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]


async def main():
    """Запуск MCP сервера."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
