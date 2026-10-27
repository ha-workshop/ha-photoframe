"""Фото на сервере: рамка только загружает файл и показывает готовый кадр — вся обработка здесь.

- Загрузка (POST /api/photoframe/upload): поворот по EXIF, HEIC → JPEG, оригинал уменьшается до MAX_SIDE.
- Показ (GET /api/photoframe/photo/<путь>?w=1280): кадр нужной ширины, один раз уменьшается и лежит в кэше.
  Ссылки подписаны (authSig) — <img> на рамке не может послать заголовок авторизации.
- Список (photoframe/photos): фото папки или альбома со ссылками под ширину экрана рамки.
"""
from __future__ import annotations

import hashlib
import io
import logging
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

from .const import ALBUM_ALL, CONF_EDIT, CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER, DOMAIN, EDIT_ADMINS
from .store import media_source_dir

_LOGGER = logging.getLogger(__name__)

MAX_SIDE = 2560  # оригинал в медиатеке — больше рамкам не нужно
WIDTHS = (640, 960, 1280, 1920, 2560)  # ширины кэша: рамка просит свою, получает ближайшую сверху
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


def _resized(src: Path, cache_dir: Path, width: int) -> Path:
    """Кадр нужной ширины из кэша; нет — сделать. Ключ — путь, время изменения и ширина."""
    stat = src.stat()
    key = hashlib.sha1(f"{src}|{stat.st_mtime_ns}|{width}".encode()).hexdigest()
    out = cache_dir / f"{key}.jpg"
    if out.exists():
        return out
    from PIL import Image, ImageOps  # noqa: PLC0415

    cache_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)
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
            width = int(request.query.get("w", WIDTHS[-1]))
        except ValueError:
            width = WIDTHS[-1]
        width = next((w for w in WIDTHS if w >= width), WIDTHS[-1])
        cache_dir = Path(hass.config.path(".storage", "photoframe_cache"))
        try:
            out = await hass.async_add_executor_job(_resized, src, cache_dir, width)
        except Exception as err:  # noqa: BLE001
            _LOGGER.info("Photo Frame: не удалось уменьшить %s: %s", src, err)
            raise web.HTTPUnsupportedMediaType from err
        return web.FileResponse(out, headers={"Cache-Control": "private, max-age=86400"})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "photoframe/photos",
        vol.Optional("album", default=ALBUM_ALL): str,
        vol.Optional("width", default=1920): vol.All(int, vol.Range(min=160, max=8000)),
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
    width = next((w for w in WIDTHS if w >= msg["width"]), WIDTHS[-1])
    photos = [
        {
            "id": rel,
            # Ширина — внутри подписи: подпись HA учитывает и параметры адреса.
            "url": async_sign_path(
                hass, f"{URL_PHOTO}/{quote(rel)}?w={width}", timedelta(days=1), refresh_token_id=connection.refresh_token_id
            ),
        }
        for rel in rels
    ]
    connection.send_result(msg["id"], {"photos": photos, "count": len(photos), "heic": HEIC})


@callback
def async_setup(hass: HomeAssistant) -> None:
    hass.http.register_view(PhotoUploadView())
    hass.http.register_view(PhotoView())
    websocket_api.async_register_command(hass, ws_photos)
