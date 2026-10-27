"""Кнопки рамки: следующее фото, открыть панель, вернуться к фото, перезагрузить."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PhotoFrameConfigEntry
from .entity import FrameEntity, setup_frame_platform
from .frames import FrameManager

COMMANDS = ("next_photo", "show_panel", "show_photos", "reload")


async def async_setup_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager = entry.runtime_data.frames
    entry.async_on_unload(
        setup_frame_platform(hass, manager, async_add_entities, lambda m, f: [FrameButton(m, f, c) for c in COMMANDS])
    )


class FrameButton(FrameEntity, ButtonEntity):
    def __init__(self, manager: FrameManager, frame_id: str, command: str) -> None:
        super().__init__(manager, frame_id, command)
        self.command = command
        if command == "reload":
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        return self.online

    async def async_press(self) -> None:
        self.manager.async_command([self.frame_id], self.command)
