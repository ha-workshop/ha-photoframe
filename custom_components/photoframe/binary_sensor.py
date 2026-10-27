"""Рамка в сети: открыта ли её подписка на интеграцию (без опросов)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PhotoFrameConfigEntry
from .entity import FrameEntity, setup_frame_platform
from .frames import FrameManager


async def async_setup_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager = entry.runtime_data.frames
    entry.async_on_unload(setup_frame_platform(hass, manager, async_add_entities, lambda m, f: [FrameOnline(m, f)]))


class FrameOnline(FrameEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, manager: FrameManager, frame_id: str) -> None:
        super().__init__(manager, frame_id, "online")

    @property
    def is_on(self) -> bool:
        return self.online
