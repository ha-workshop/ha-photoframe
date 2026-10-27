"""Общее для сущностей рамки: устройство, обновление по сигналу, создание сущностей для новых рамок."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_FRAME_ADDED, SIGNAL_FRAME_UPDATED
from .frames import FrameManager


class FrameEntity(Entity):
    """Сущность одной рамки. Обновляется, когда рамка подключилась, отключилась или что-то сообщила."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: FrameManager, frame_id: str, key: str) -> None:
        self.manager = manager
        self.frame_id = frame_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{frame_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, frame_id)})

    @property
    def online(self) -> bool:
        return self.frame_id in self.manager.online

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_FRAME_UPDATED.format(self.frame_id), self.async_write_ha_state)
        )


def setup_frame_platform(
    hass: HomeAssistant,
    manager: FrameManager,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[FrameManager, str], list[Entity]],
) -> Callable[[], None]:
    """Сущности для уже известных рамок — сразу, для новых — когда рамка впервые подключится."""
    async_add_entities([e for frame_id in manager.frames for e in build(manager, frame_id)])

    @callback
    def added(frame_id: str) -> None:
        async_add_entities(build(manager, frame_id))

    return async_dispatcher_connect(hass, SIGNAL_FRAME_ADDED, added)
