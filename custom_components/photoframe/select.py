"""Альбом рамки (подпапка папки фото) и её стартовый экран."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PhotoFrameConfigEntry
from .const import ALBUM_ALL
from .entity import FrameEntity, setup_frame_platform
from .frames import FrameManager


async def async_setup_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager = entry.runtime_data.frames
    entry.async_on_unload(
        setup_frame_platform(hass, manager, async_add_entities, lambda m, f: [FrameAlbum(m, f), FrameStartScreen(m, f)])
    )


class FrameAlbum(FrameEntity, SelectEntity):
    """«all» — вся папка фото; остальное — её подпапки (/media/photoframe/<альбом>)."""

    def __init__(self, manager: FrameManager, frame_id: str) -> None:
        super().__init__(manager, frame_id, "album")

    @property
    def options(self) -> list[str]:
        current = self.manager.frame(self.frame_id).get("album") or ALBUM_ALL
        albums = [ALBUM_ALL, *self.manager.albums]
        # Альбом выбран, но папку удалили — пусть он всё равно виден, иначе HA сочтёт значение неверным.
        return albums if current in albums else [*albums, current]

    @property
    def current_option(self) -> str:
        return self.manager.frame(self.frame_id).get("album") or ALBUM_ALL

    async def async_select_option(self, option: str) -> None:
        await self.manager.async_set(self.frame_id, album=option)


class FrameStartScreen(FrameEntity, SelectEntity):
    """Экран, с которого рамка начинает и к которому возвращается без касаний (свой у каждой рамки)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager: FrameManager, frame_id: str) -> None:
        super().__init__(manager, frame_id, "start_screen")

    @property
    def options(self) -> list[str]:
        return list(self.manager.screen_options(self.frame_id))

    @property
    def current_option(self) -> str | None:
        value = self.manager.frame(self.frame_id).get("start_screen")
        for label, key in self.manager.screen_options(self.frame_id).items():
            if key == value:
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        key = self.manager.screen_options(self.frame_id).get(option)
        if key:
            await self.manager.async_set(self.frame_id, start_screen=key)
