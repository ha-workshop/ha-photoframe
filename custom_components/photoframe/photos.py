"""Фото на сервере: рамка только загружает файл и показывает готовый кадр — вся обработка здесь.

- Загрузка (POST /api/photoframe/upload): поворот по EXIF, HEIC → JPEG, оригинал уменьшается до MAX_SIDE.
- Показ (GET /api/photoframe/photo/<путь>?w=1280&h=800): кадр под экран рамки — ровно такой, чтобы закрыть
  экран (не мельче — иначе мыло, не крупнее — лишние байты); один раз уменьшается и лежит в JPEG-кэше.
  HEIC, положенные в папку напрямую, рамка тоже получает JPEG. Кэш, который не запрашивали 7 дней, удаляется.
  Ссылки подписаны (authSig) — <img> на рамке не может послать заголовок авторизации.
- Список (photoframe/photos): фото папки или альбома со ссылками под ширину экрана рамки.
- Источник (photoframe/photos с media): любая папка медиатеки HA — Google Photos, SMB-диск, «Мои медиа»
  или источник другой интеграции. Кадр идёт через прокси /api/photoframe/media, чтобы сервер уменьшил его
  под экран и закэшировал для офлайна так же, как локальные фото.
"""
from __future__ import annotations

import base64
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
from aiohttp import ClientTimeout, web

from homeassistant.components import media_source, websocket_api
from homeassistant.components.http import HomeAssistantView, KEY_HASS
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import ALBUM_ALL, CONF_EDIT, CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER, DOMAIN, EDIT_ADMINS, MEDIA_SOURCE_ID
from .store import media_source_dir

_LOGGER = logging.getLogger(__name__)

MAX_SIDE = 2560  # оригинал в медиатеке — больше рамкам не нужно
STEP = 160  # размеры экрана округляются вверх до кратных — меньше вариантов в кэше
MAX_REQUEST = 3840
CACHE_DAYS = 7
QUALITY = 86
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp"}
URL_PHOTO = "/api/photoframe/photo"
URL_MEDIA = "/api/photoframe/media"
# Любая папка источника может содержать тысячи снимков: рамке хватает нескольких сотен,
# а обход всех вложенных папок на каждом списке был бы слишком дорогим.
MAX_MEDIA_ITEMS = 300
MAX_MEDIA_DEPTH = 8
MAX_DOWNLOAD = 30 * 1024 * 1024
IMAGE_CLASSES = {"image", "photo"}
FOLDER_CLASSES = {"directory", "album", "channel"}

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


def photo_media_root(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """media_content_id локальной папки Photo Frame — как её видит медиатека HA."""
    source = media_source_dir(hass)
    if source is None:
        return None
    folder = entry.options.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER).strip("/")
    return f"media-source://media_source/{source}/{folder}"


def media_album_for(hass: HomeAssistant, entry: ConfigEntry, media: str) -> str | None:
    """Если media_content_id указывает внутрь локальной папки Photo Frame — вернуть альбом.
    Корень папки — ALBUM_ALL; None — это другой источник, его альбомом не заменить."""
    root = photo_media_root(hass, entry)
    if not root:
        return None
    value = media.rstrip("/")
    if value == root:
        return ALBUM_ALL
    prefix = root + "/"
    if not value.startswith(prefix):
        return None
    rel = value[len(prefix):].strip("/")
    if not rel:
        return ALBUM_ALL
    if any(part in ("", ".", "..") for part in rel.split("/")):
        return None
    return rel


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


def _save_resized(img: Any, out: Path, width: int, height: int) -> None:
    """Уменьшить кадр под экран (cover) и сохранить JPEG. Больше оригинала не увеличиваем."""
    from PIL import Image, ImageOps  # noqa: PLC0415

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    scale = min(1.0, max(width / img.width, height / img.height))
    if scale < 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.Resampling.LANCZOS)
    # Уникальное имя: один и тот же кадр могут готовить два запроса одновременно (поворот экрана).
    tmp = out.with_name(f"{out.name}.{os.getpid()}.{time.time_ns()}.tmp")
    img.save(tmp, "JPEG", quality=82, optimize=True)
    tmp.replace(out)


def _resized(src: Path, cache_dir: Path, width: int, height: int) -> Path:
    """Кадр под экран width×height из кэша; нет — сделать. Ключ — путь, время изменения и размер экрана."""
    stat = src.stat()
    key = hashlib.sha1(f"{src}|{stat.st_mtime_ns}|{width}x{height}".encode()).hexdigest()
    out = cache_dir / f"{key}.jpg"
    if out.exists():
        # Запросили — кадр живёт ещё 7 дней (чистка смотрит на время изменения).
        os.utime(out)
        return out
    from PIL import Image  # noqa: PLC0415

    cache_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        _save_resized(img, out, width, height)
    return out


def _resize_bytes(data: bytes, cache_dir: Path, key: str, width: int, height: int) -> Path:
    """Кадр из внешнего источника (Google Photos, SMB и т.п.): скачали — уменьшили и положили в кэш."""
    out = cache_dir / f"{key}.jpg"
    if out.exists():
        os.utime(out)
        return out
    from PIL import Image  # noqa: PLC0415

    cache_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(data)) as img:
        _save_resized(img, out, width, height)
    return out


# ── Источник фото: любая папка медиатеки HA ─────────────────
def media_token(content_id: str) -> str:
    """Непрозрачный для глаза токен media_content_id: в адресе прокси не должно быть слэшей и двоеточий."""
    return base64.urlsafe_b64encode(content_id.encode()).decode().rstrip("=")


def media_id(token: str) -> str:
    pad = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + pad).decode()


def media_url(hass: HomeAssistant, content_id: str, width: int, height: int, refresh_token_id: str | None) -> str:
    """Подписанная ссылка на прокси кадра: <img> не может послать заголовок авторизации."""
    token = media_token(content_id)
    return async_sign_path(
        hass,
        f"{URL_MEDIA}/{token}?w={width}&h={height}",
        timedelta(days=1),
        refresh_token_id=refresh_token_id,
    )


async def _collect_media(hass: HomeAssistant, content_id: str) -> list[tuple[str, str]]:
    """Изображения из папки любого источника медиатеки — рекурсивно, с разумным пределом."""
    found: list[tuple[str, str]] = []
    # Стартовая папка тоже в seen: источник может сослаться на неё же — не ходим по кругу.
    seen: set[str] = {content_id}

    async def walk(cid: str, depth: int) -> None:
        if len(found) >= MAX_MEDIA_ITEMS or depth > MAX_MEDIA_DEPTH:
            return
        try:
            item = await media_source.async_browse_media(hass, cid)
        except Exception as err:  # noqa: BLE001 — источник может быть недоступен, папка удалена
            _LOGGER.debug("Photo Frame: не удалось открыть %s: %s", cid, err)
            return
        for child in item.children or []:
            if len(found) >= MAX_MEDIA_ITEMS:
                return
            if child.media_content_id in seen:
                continue
            seen.add(child.media_content_id)
            # Одни источники помечают кадры media_class=image, другие — типом содержимого.
            if child.media_class in IMAGE_CLASSES or child.media_content_type in IMAGE_CLASSES:
                found.append((child.media_content_id, child.title))
            elif child.can_expand or child.media_class in FOLDER_CLASSES:
                await walk(child.media_content_id, depth + 1)

    await walk(content_id, 0)
    return found


async def _remote_image(hass: HomeAssistant, url: str, cache_dir: Path, width: int, height: int) -> Path:
    """Скачать кадр внешнего источника и уменьшить. Кэш — по адресу и размеру экрана."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Unsupported media url: {url}")
    key = hashlib.sha1(f"{url}|{width}x{height}".encode()).hexdigest()
    out = cache_dir / f"{key}.jpg"
    if out.exists():
        os.utime(out)
        return out
    session = async_get_clientsession(hass)
    async with session.get(url, timeout=ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            raise ValueError(f"Media returned {resp.status}")
        length = int(resp.headers.get("Content-Length") or 0)
        if length > MAX_DOWNLOAD:
            raise ValueError("Media is too large")
        data = await resp.read()
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("Media is too large")
    return await hass.async_add_executor_job(_resize_bytes, data, cache_dir, key, width, height)


def _list(root: Path, album: str) -> list[str]:
    """Фото альбома (или всей папки без подпапок) — пути относительно папки фото, по имени."""
    folder = root if album in ("", ALBUM_ALL) else root / album
    if not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT and not p.name.startswith(".")]
    return [str(p.relative_to(root)) for p in sorted(files, key=lambda p: p.name.lower())]


def _walk(root: Path, max_depth: int = 8) -> list[dict[str, Any]]:
    """Дерево папок медиатеки: путь от папки фото, фото в ней и всего в подпапках.
    Папки без фото тоже нужны — по ним видно, куда складывать снимки."""
    out: list[dict[str, Any]] = []

    def scan(rel: str, depth: int) -> int:
        folder = root / rel if rel else root
        try:
            entries = list(folder.iterdir())
        except OSError:
            return 0
        direct = 0
        subdirs: list[str] = []
        for item in entries:
            if item.name.startswith("."):
                continue
            if item.is_dir():
                subdirs.append(item.name)
            elif item.is_file() and item.suffix.lower() in IMAGE_EXT:
                direct += 1
        total = direct
        if depth < max_depth:
            for name in sorted(subdirs, key=str.lower):
                total += scan(f"{rel}/{name}" if rel else name, depth + 1)
        out.append({"path": rel, "count": direct, "total": total})
        return total

    scan("", 0)
    return sorted(out, key=lambda x: x["path"].lower())


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
        if album and album != ALBUM_ALL:
            target = await hass.async_add_executor_job(_safe, root, album)
            if target is None:
                return self.json_message("Bad album", 400)
        else:
            target = root
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
        src = await hass.async_add_executor_job(_safe, root, path) if root else None
        if src is None or not await hass.async_add_executor_job(src.is_file):
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


def _frame_media(entry: ConfigEntry, frame_id: str | None) -> str:
    """Выбранная рамкой папка медиатеки: media_content_id любого источника. Пусто — обычная папка фото."""
    if not frame_id or not hasattr(entry.runtime_data, "frames"):
        return ""
    frame = entry.runtime_data.frames.frame(frame_id)
    media = frame.get("media") or ""
    return media if MEDIA_SOURCE_ID.match(media) else ""


@websocket_api.websocket_command(
    {
        vol.Required("type"): "photoframe/photos",
        # Явно не задан — берём альбом рамки (для предпросмотра в разделе «Фоторамки»).
        vol.Optional("album"): str,
        vol.Optional("frame_id"): str,
        # Явный источник — для предпросмотра в разделе «Фоторамки» ещё до сохранения.
        vol.Optional("media"): str,
        vol.Optional("width", default=1920): vol.All(int, vol.Range(min=160, max=8000)),
        vol.Optional("height"): vol.All(int, vol.Range(min=160, max=8000)),
    }
)
@websocket_api.async_response
async def ws_photos(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Фото рамки со ссылками под её экран (подписаны на сутки — рамка перечитывает список раньше).
    Если у рамки выбран источник медиатеки — отдаём кадры из него, тоже через прокси с уменьшением."""
    entry = _entry(hass)
    width = _bucket(msg["width"])
    height = _bucket(msg.get("height", msg["width"]))
    media = (msg.get("media") or "").strip() or (_frame_media(entry, msg.get("frame_id")) if entry else "")
    if media:
        if not MEDIA_SOURCE_ID.match(media):
            connection.send_error(msg["id"], "bad_media", "Bad media source")
            return
        items = await _collect_media(hass, media)
        photos = [
            {"id": cid, "url": media_url(hass, cid, width, height, connection.refresh_token_id)}
            for cid, _title in items
        ]
        connection.send_result(msg["id"], {"photos": photos, "count": len(photos), "media": media})
        return

    root = photo_root(hass, entry) if entry else None
    if root is None:
        connection.send_result(msg["id"], {"photos": [], "count": 0})
        return
    album = (msg.get("album") or "").strip("/")
    # Альбом не передали (предпросмотр в разделе «Фоторамки») — берём тот, что выбран на рамке.
    if not album and entry is not None and msg.get("frame_id"):
        album = (entry.runtime_data.frames.frame(msg["frame_id"]).get("album") or ALBUM_ALL).strip("/")
    if not album:
        album = ALBUM_ALL
    if album not in ("", ALBUM_ALL):
        safe = await hass.async_add_executor_job(_safe, root, album)
        if safe is None:
            connection.send_error(msg["id"], "bad_album", "Bad album")
            return
    rels = await hass.async_add_executor_job(_list, root, album)
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


class MediaPhotoView(HomeAssistantView):
    """Кадр из любой папки медиатеки: сервер сам решает — файл на диске или внешний адрес.
    Ссылка подписана, как и у PhotoView: рамка не может прислать заголовок авторизации в <img>."""

    url = URL_MEDIA + "/{token:.+}"
    name = "api:photoframe:media"

    async def get(self, request: web.Request, token: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        try:
            content_id = media_id(token)
        except Exception:  # noqa: BLE001 — битый или подделанный токен
            raise web.HTTPBadRequest
        if not MEDIA_SOURCE_ID.match(content_id):
            raise web.HTTPBadRequest
        try:
            width = _bucket(int(request.query.get("w", MAX_SIDE)))
            height = _bucket(int(request.query.get("h", width)))
        except ValueError:
            width = height = MAX_SIDE
        try:
            play = await media_source.async_resolve_media(hass, content_id, None)
        except Exception as err:  # noqa: BLE001 — источник не отвечает или файл удалён
            _LOGGER.info("Photo Frame: кадр недоступен (%s): %s", content_id, err)
            raise web.HTTPNotFound from err
        cache_dir = _cache_dir(hass)
        try:
            if play.path is not None and await hass.async_add_executor_job(Path(play.path).is_file):
                out = await hass.async_add_executor_job(_resized, Path(play.path), cache_dir, width, height)
            elif play.url:
                out = await _remote_image(hass, play.url, cache_dir, width, height)
            else:
                raise web.HTTPUnsupportedMediaType
        except web.HTTPException:
            raise
        except Exception as err:  # noqa: BLE001 — битый файл или формат без поддержки
            _LOGGER.info("Photo Frame: не удалось подготовить кадр %s: %s", content_id, err)
            raise web.HTTPUnsupportedMediaType from err
        return web.FileResponse(out, headers={"Cache-Control": "private, max-age=86400"})


@websocket_api.websocket_command({vol.Required("type"): "photoframe/folders"})
@websocket_api.async_response
async def ws_folders(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Папки медиатеки внутри папки фото — дерево для выбора «что показывать» на рамке."""
    entry = _entry(hass)
    root = photo_root(hass, entry) if entry else None
    if root is None:
        connection.send_result(msg["id"], {"folders": []})
        return
    folders = await hass.async_add_executor_job(_walk, root)
    connection.send_result(msg["id"], {"folders": folders})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "photoframe/photo/delete",
        vol.Required("frame_id"): str,
        vol.Required("photo"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_photo_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Раздел «Фоторамки» удаляет кадр из локальной папки Photo Frame.
    Внешние источники (Google Photos, SMB, камеры) — только для показа: их файлами управляет интеграция."""
    entry = _entry(hass)
    root = photo_root(hass, entry) if entry else None
    if entry is None or root is None:
        connection.send_error(msg["id"], "no_media_folder", "No media folder")
        return
    frame = entry.runtime_data.frames.frame(msg["frame_id"])
    media = frame.get("media") or ""
    photo = msg["photo"].strip()
    if media:
        # Явно выбранная локальная папка: id кадра — полный media_content_id.
        local_root = photo_media_root(hass, entry)
        if not local_root or not photo.startswith(local_root + "/"):
            connection.send_error(msg["id"], "read_only", "External media is read-only")
            return
        rel = photo[len(local_root) + 1 :]
    else:
        rel = photo
    rel = rel.strip().strip("/")
    if not rel or any(part in ("", ".", "..") for part in rel.split("/")):
        connection.send_error(msg["id"], "bad_photo", "Bad photo path")
        return
    path = await hass.async_add_executor_job(_safe, root, rel)
    if path is None:
        connection.send_error(msg["id"], "not_found", "Photo not found")
        return
    is_file = await hass.async_add_executor_job(path.is_file)
    if not is_file or path.suffix.lower() not in IMAGE_EXT:
        connection.send_error(msg["id"], "not_found", "Photo not found")
        return
    try:
        await hass.async_add_executor_job(path.unlink)
    except OSError as err:
        connection.send_error(msg["id"], "delete_failed", str(err))
        return
    await entry.runtime_data.frames.async_refresh_albums()
    connection.send_result(msg["id"], {"deleted": True})


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
    hass.http.register_view(MediaPhotoView())
    websocket_api.async_register_command(hass, ws_photos)
    websocket_api.async_register_command(hass, ws_folders)
    websocket_api.async_register_command(hass, ws_photo_delete)
