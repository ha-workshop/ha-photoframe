"""Службы для автоматизаций: камера на рамках по звонку, альбом на ночь, экран, следующее фото.
Рамки выбираются устройствами (device_id); не выбраны — все рамки в сети."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ALBUM_ALL, DOMAIN
from .frames import FrameManager

DEVICES = {vol.Optional("device_id"): vol.All(cv.ensure_list, [str])}


def _manager(hass: HomeAssistant) -> FrameManager:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Photo Frame is not set up")
    return entries[0].runtime_data.frames


def _targets(manager: FrameManager, call: ServiceCall) -> list[str] | None:
    devices = call.data.get("device_id")
    return manager.frame_ids_for_devices(devices) if devices else None


@callback
def async_setup(hass: HomeAssistant) -> None:
    async def next_photo(call: ServiceCall) -> None:
        manager = _manager(hass)
        manager.async_command(_targets(manager, call), "next_photo")

    async def show_camera(call: ServiceCall) -> None:
        manager = _manager(hass)
        manager.async_command(_targets(manager, call), "show_camera", entity=call.data["camera"], duration=call.data["duration"])

    async def show_screen(call: ServiceCall) -> None:
        manager = _manager(hass)
        screen = call.data["screen"]
        # Можно подписью из списка («Квартира · Камеры») или «дом/экран».
        key = manager.screen_options().get(screen, screen)
        manager.async_command(_targets(manager, call), "show_screen", screen=key)

    async def set_album(call: ServiceCall) -> None:
        manager = _manager(hass)
        album = call.data.get("album") or ALBUM_ALL
        targets = _targets(manager, call)
        for frame_id in targets if targets is not None else list(manager.frames):
            await manager.async_set(frame_id, album=album)

    hass.services.async_register(DOMAIN, "next_photo", next_photo, vol.Schema(DEVICES))
    hass.services.async_register(
        DOMAIN,
        "show_camera",
        show_camera,
        vol.Schema({vol.Required("camera"): cv.entity_id, vol.Optional("duration", default=30): vol.All(int, vol.Range(min=5, max=3600)), **DEVICES}),
    )
    hass.services.async_register(DOMAIN, "show_screen", show_screen, vol.Schema({vol.Required("screen"): str, **DEVICES}))
    hass.services.async_register(DOMAIN, "set_album", set_album, vol.Schema({vol.Optional("album"): str, **DEVICES}))
