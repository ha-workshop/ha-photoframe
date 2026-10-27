"""Текущее фото рамки — имя файла, а картинка сущности — само фото (ссылку рамка сообщает сама)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PhotoFrameConfigEntry
from .entity import FrameEntity, setup_frame_platform
from .frames import FrameManager


async def async_setup_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager = entry.runtime_data.frames
    entry.async_on_unload(setup_frame_platform(hass, manager, async_add_entities, lambda m, f: [FramePhoto(m, f)]))


class FramePhoto(FrameEntity, SensorEntity):
    def __init__(self, manager: FrameManager, frame_id: str) -> None:
        super().__init__(manager, frame_id, "photo")

    @property
    def available(self) -> bool:
        return self.online

    @property
    def native_value(self) -> str | None:
        return self.manager.live.get(self.frame_id, {}).get("photo")

    @property
    def entity_picture(self) -> str | None:
        url = self.manager.live.get(self.frame_id, {}).get("photo_url")
        # Только ссылки HA (медиатека): чужие адреса и встроенные data:-картинки сюда не годятся.
        return url if isinstance(url, str) and url.startswith("/") else None
