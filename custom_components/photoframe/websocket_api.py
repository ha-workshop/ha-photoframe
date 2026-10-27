"""WebSocket API рамки: конфиг (дома, экраны, настройки) для карточки и PWA — через обычное подключение к HA."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import CONF_EDIT, CONF_KIOSK, CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER, DOMAIN, EDIT_ADMINS
from .store import KEYS, FrameStore, media_source_dir


@callback
def async_setup(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_config)
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_frame_connect)
    websocket_api.async_register_command(hass, ws_frame_report)


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0] if entries else None


def _can_edit(entry: ConfigEntry, user: Any) -> bool:
    return bool(user and (user.is_admin or entry.options.get(CONF_EDIT, EDIT_ADMINS) != EDIT_ADMINS))


def _payload(hass: HomeAssistant, entry: ConfigEntry, user: Any) -> dict[str, Any]:
    """Конфиг для рамки: данные хранилища + настройки интеграции + может ли этот пользователь править."""
    store: FrameStore = entry.runtime_data
    data = {key: store.data[key] for key in KEYS if key in store.data}
    return {
        **data,
        "media_folder": entry.options.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER),
        # Как называется источник «Моих медиа» (обычно local) — для media-source://media_source/<он>/<папка>.
        "media_source": media_source_dir(hass),
        "kiosk": entry.options.get(CONF_KIOSK, False),
        "can_edit": _can_edit(entry, user),
    }


def _not_loaded(connection: websocket_api.ActiveConnection, msg_id: int) -> None:
    connection.send_error(msg_id, "not_loaded", "Photo Frame is not set up")


@websocket_api.websocket_command({vol.Required("type"): "photoframe/config"})
@callback
def ws_config(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg["id"])
        return
    connection.send_result(msg["id"], _payload(hass, entry, connection.user))


@websocket_api.websocket_command({vol.Required("type"): "photoframe/config/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Сразу текущий конфиг, потом — каждый раз, когда его кто-то сохранил (другая рамка, карточка)."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg["id"])
        return
    store: FrameStore = entry.runtime_data

    @callback
    def changed() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], _payload(hass, entry, connection.user)))

    connection.subscriptions[msg["id"]] = store.async_listen(changed)
    connection.send_result(msg["id"])
    changed()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "photoframe/config/save",
        vol.Optional("homes"): list,
        vol.Optional("layouts"): dict,
        vol.Optional("settings"): dict,
    }
)
@websocket_api.async_response
async def ws_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg["id"])
        return
    if not _can_edit(entry, connection.user):
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, "Only administrators can change the frame")
        return
    store: FrameStore = entry.runtime_data
    await store.async_update({key: msg[key] for key in KEYS if key in msg})
    connection.send_result(msg["id"])


# ── Рамки как устройства ──────────────────────────────────
@websocket_api.websocket_command(
    {
        vol.Required("type"): "photoframe/frame/connect",
        vol.Required("frame_id"): vol.All(str, vol.Length(min=8, max=64)),
        vol.Optional("name"): str,
        vol.Optional("model"): str,
        vol.Optional("version"): str,
    }
)
@callback
def ws_frame_connect(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Рамка на связи: пока подписка открыта — «в сети». Сюда же ей приходят её настройки и команды."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg["id"])
        return
    store: FrameStore = entry.runtime_data

    @callback
    def send(data: dict[str, Any]) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], data))

    info = {key: msg[key] for key in ("name", "model", "version") if key in msg}
    connection.subscriptions[msg["id"]] = store.frames.async_connect(msg["frame_id"], info, send)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "photoframe/frame/report",
        vol.Required("frame_id"): str,
        vol.Optional("photo"): vol.Any(str, None),
        vol.Optional("photo_url"): vol.Any(str, None),
        vol.Optional("screen"): vol.Any(str, None),
    }
)
@callback
def ws_frame_report(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Рамка сообщает, что сейчас показывает: фото, экран."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg["id"])
        return
    store: FrameStore = entry.runtime_data
    store.frames.async_report(msg["frame_id"], {k: msg[k] for k in ("photo", "photo_url", "screen") if k in msg})
    connection.send_result(msg["id"])

