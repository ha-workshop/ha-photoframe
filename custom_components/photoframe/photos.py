"""Фото на сервере: рамка только загружает файл и показывает готовый кадр — вся обработка здесь.

- Загрузка (POST /api/photoframe/upload): поворот по EXIF, HEIC → JPEG, оригинал уменьшается до MAX_SIDE.
- Показ (GET /api/photoframe/photo/<путь>?w=1280&h=800): кадр под экран рамки — ровно такой, чтобы закрыть
  экран (не мельче — иначе мыло, не крупнее — лишние байты); один раз уменьшается и лежит в JPEG-кэше.
  HEIC, положенные в папку напрямую, рамка тоже получает JPEG. Кэш, который не запрашивали 7 дней, удаляется.
  Ссылки подписаны (authSig) — <img> на рамке не может послать заголовок авторизации.
- Список (photoframe/photos): фото папки или альбома со ссылками под ширину экрана рамки.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import time
import re
from datetime import timedelta
from urllib.parse import quote
from pathlib import Path
from typing import Any

import voluptuous as vol
from aiohttp import web

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView, KEY_HASS
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import ALBUM_ALL, CONF_EDIT, CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER, DOMAIN, EDIT_ADMINS
from .store import media_source_dir

_LOGGER = logging.getLogger(__name__)

MAX_SIDE = 2560  # оригинал в медиатеке — больше рамкам не нужно
STEP = 160  # размеры экрана округляются вверх до кратных — меньше вариантов в кэше
MAX_REQUEST = 3840
CACHE_DAYS = 7
QUALITY = 86
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp"}
URL_PHOTO = "/api/photoframe/photo"

try:  # HEIC с iPhone/iPad — через pillow-heif (ставится вместе с интеграцией)
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC = True
except ImportError:  # pragma: no cover — без библиотеки остальные форматы работают
    HEIC = False


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0] if entries else None


def photo_root(hass: HomeAssistant, entry: ConfigEntry) -> Path | None:
    """Папка фото на диске (/media/photoframe) — с учётом того, как назван источник в media_dirs."""
    source = media_source_dir(hass)
    if source is None:
        return None
    folder = entry.options.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER).strip("/")
    return Path(hass.config.media_dirs[source]) / folder


def _safe(root: Path, rel: str) -> Path | None:
    """Путь внутри папки фото — без выхода наружу через .. и абсолютные пути."""
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def _clean_name(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^\w\-. ]+", "_", stem, flags=re.UNICODE).strip(" ._") or "photo"
    return stem[:80]


def _process(data: bytes, target_dir: Path, name: str) -> str:
    """Открыть (в т.ч. HEIC), повернуть по EXIF, уменьшить, сохранить JPEG. Возвращает имя файла."""
    from PIL import Image, ImageOps  # noqa: PLC0415 — Pillow тяжёлый, грузим только при загрузке фото

    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
        target_dir.mkdir(parents=True, exist_ok=True)
        base = _clean_name(name)
        out = target_dir / f"{base}.jpg"
        n = 2
        while out.exists():
            out, n = target_dir / f"{base}-{n}.jpg", n + 1
        img.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        return out.name


def _bucket(value: int) -> int:
    return max(STEP, min(MAX_REQUEST, -(-value // STEP) * STEP))


def _resized(src: Path, cache_dir: Path, width: int, height: int) -> Path:
    """Кадр под экран width×height из кэша; нет — сделать. Ключ — путь, время изменения и размер экрана.
    Масштаб — чтобы кадр закрыл экран целиком (как cover); больше оригинала не увеличиваем."""
    stat = src.stat()
    key = hashlib.sha1(f"{src}|{stat.st_mtime_ns}|{width}x{height}".encode()).hexdigest()
    out = cache_dir / f"{key}.jpg"
    if out.exists():
        # Запросили — кадр живёт ещё 7 дней (чистка смотрит на время изменения).
        os.utime(out)
        return out
    from PIL import Image, ImageOps  # noqa: PLC0415

    cache_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        scale = min(1.0, max(width / img.width, height / img.height))
        if scale < 1.0:
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.Resampling.LANCZOS)
        tmp = out.with_suffix(".tmp")
        img.save(tmp, "JPEG", quality=82, optimize=True)
        tmp.replace(out)
    return out


def _list(root: Path, album: str) -> list[str]:
    """Фото альбома (или всей папки без подпапок) — пути относительно папки фото, по имени."""
    folder = root if album in ("", ALBUM_ALL) else root / album
    if not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT and not p.name.startswith(".")]
    return [str(p.relative_to(root)) for p in sorted(files, key=lambda p: p.name.lower())]


class PhotoUploadView(HomeAssistantView):
    """Рамка присылает файл как есть (одно фото на запрос) — сервер обрабатывает и кладёт в альбом."""

    url = "/api/photoframe/upload"
    name = "api:photoframe:upload"

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        entry = _entry(hass)
        if entry is None:
            return self.json_message("Photo Frame is not set up", 404)
        user = request["hass_user"]
        if not (user.is_admin or entry.options.get(CONF_EDIT, EDIT_ADMINS) != EDIT_ADMINS):
            return self.json_message("Only administrators can upload photos", 403)
        root = photo_root(hass, entry)
        if root is None:
            return self.json_message("No media folder", 404)

        reader = await request.multipart()
        album, data, filename = "", b"", "photo"
        while (part := await reader.next()) is not None:
            if part.name == "album":
                album = (await part.text()).strip().strip("/")
            elif part.name == "file":
                filename = part.filename or filename
                data = await part.read(decode=False)
        if not data:
            return self.json_message("No file", 400)
        target = _safe(root, album) if album and album != ALBUM_ALL else root
        if target is None:
            return self.json_message("Bad album", 400)
        try:
            saved = await hass.async_add_executor_job(_process, data, target, filename)
        except Exception as err:  # noqa: BLE001 — битый файл или формат без поддержки
            _LOGGER.info("Photo Frame: не удалось обработать %s: %s", filename, err)
            code = "heic" if filename.lower().endswith((".heic", ".heif")) and not HEIC else "format"
            return self.json({"error": code, "message": str(err)}, 415)
        await entry.runtime_data.frames.async_refresh_albums()
        return self.json({"name": saved, "album": album or ALBUM_ALL})


class PhotoView(HomeAssistantView):
    """Кадр нужной ширины. Доступ — по подписанной ссылке из photoframe/photos."""

    url = URL_PHOTO + "/{path:.+}"
    name = "api:photoframe:photo"

    async def get(self, request: web.Request, path: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        entry = _entry(hass)
        root = photo_root(hass, entry) if entry else None
        src = _safe(root, path) if root else None
        if src is None or not src.is_file():
            raise web.HTTPNotFound
        try:
            width = _bucket(int(request.query.get("w", MAX_SIDE)))
            height = _bucket(int(request.query.get("h", width)))
        except ValueError:
            width = height = MAX_SIDE
        cache_dir = _cache_dir(hass)
        try:
            out = await hass.async_add_executor_job(_resized, src, cache_dir, width, height)
        except Exception as err:  # noqa: BLE001
            _LOGGER.info("Photo Frame: не удалось уменьшить %s: %s", src, err)
            raise web.HTTPUnsupportedMediaType from err
        return web.FileResponse(out, headers={"Cache-Control": "private, max-age=86400"})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "photoframe/photos",
        vol.Optional("album", default=ALBUM_ALL): str,
        vol.Optional("width", default=1920): vol.All(int, vol.Range(min=160, max=8000)),
        vol.Optional("height"): vol.All(int, vol.Range(min=160, max=8000)),
    }
)
@websocket_api.async_response
async def ws_photos(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Фото альбома со ссылками под ширину рамки (подписаны на сутки — рамка перечитывает список раньше)."""
    entry = _entry(hass)
    root = photo_root(hass, entry) if entry else None
    if root is None:
        connection.send_result(msg["id"], {"photos": [], "count": 0})
        return
    album = msg["album"].strip("/")
    if album not in ("", ALBUM_ALL) and _safe(root, album) is None:
        connection.send_error(msg["id"], "bad_album", "Bad album")
        return
    rels = await hass.async_add_executor_job(_list, root, album)
    width = _bucket(msg["width"])
    height = _bucket(msg.get("height", msg["width"]))
    photos = [
        {
            "id": rel,
            # Ширина — внутри подписи: подпись HA учитывает и параметры адреса.
            "url": async_sign_path(
                hass, f"{URL_PHOTO}/{quote(rel)}?w={width}&h={height}", timedelta(days=1), refresh_token_id=connection.refresh_token_id
            ),
        }
        for rel in rels
    ]
    connection.send_result(msg["id"], {"photos": photos, "count": len(photos), "heic": HEIC})


def _cache_dir(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(".storage", "photoframe_cache"))


def _cleanup(cache_dir: Path) -> int:
    """Удалить кадры, которые не запрашивали CACHE_DAYS дней. Возвращает, сколько удалено."""
    if not cache_dir.is_dir():
        return 0
    border = time.time() - CACHE_DAYS * 86400
    removed = 0
    for path in cache_dir.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < border:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


@callback
def async_setup(hass: HomeAssistant) -> None:
    async def cleanup(_now: Any = None) -> None:
        removed = await hass.async_add_executor_job(_cleanup, _cache_dir(hass))
        if removed:
            _LOGGER.debug("Photo Frame: из кэша удалено %s кадров", removed)

    # Чистим при запуске и дальше раз в 12 часов.
    hass.async_create_background_task(cleanup(), "photoframe cache cleanup")
    async_track_time_interval(hass, cleanup, timedelta(hours=12), cancel_on_shutdown=True)
    hass.http.register_view(PhotoUploadView())
    hass.http.register_view(PhotoView())
    websocket_api.async_register_command(hass, ws_photos)
