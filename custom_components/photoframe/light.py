"""Экран рамки как свет: включить/выключить (сон) и яркость. Ночью — выключить, по датчику движения — включить.

В APK это настоящая подсветка; в браузере — затемнение поверх страницы, «сон» — чёрный экран.
Коснулись спящей рамки — она просыпается и сообщает об этом, сущность тоже включается.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PhotoFrameConfigEntry
from .entity import FrameEntity, setup_frame_platform
from .frames import FrameManager


async def async_setup_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager = entry.runtime_data.frames
    entry.async_on_unload(setup_frame_platform(hass, manager, async_add_entities, lambda m, f: [FrameScreen(m, f)]))


class FrameScreen(FrameEntity, LightEntity):
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, manager: FrameManager, frame_id: str) -> None:
        super().__init__(manager, frame_id, "screen")

    @property
    def is_on(self) -> bool:
        return self.manager.frame(self.frame_id).get("screen_on", True)

    @property
    def brightness(self) -> int:
        # У рамки яркость в процентах, у HA — 0…255.
        return round(self.manager.frame(self.frame_id).get("brightness", 100) * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        patch: dict[str, Any] = {"screen_on": True}
        if ATTR_BRIGHTNESS in kwargs:
            patch["brightness"] = max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))
        await self.manager.async_set(self.frame_id, **patch)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set(self.frame_id, screen_on=False)
