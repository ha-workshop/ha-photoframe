"""Обновление APK Android-рамки из HA: интеграция раздаёт APK своей версии (/photoframe/photoframe.apk),
рамка сообщает свою. «Установить» — рамка скачивает APK и ставит его (с root — сама, иначе нажать «Установить»
на рамке), потом перезапускается и подключается уже с новой версией.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.loader import async_get_integration

from . import PhotoFrameConfigEntry
from .const import DOMAIN
from .entity import FrameEntity, setup_frame_platform
from .frames import FrameManager

APK = Path(__file__).parent / "frontend" / "pwa" / "photoframe.apk"
RELEASES = "https://github.com/ha-workshop/ha-photoframe/releases/tag/v{}"
# Не подключилась с новой версией за это время (отменили установку на рамке, нет сети) — снова можно нажать.
INSTALL_TIMEOUT = 300


async def async_setup_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    manager = entry.runtime_data.frames
    # Версия APK, который раздаёт интеграция, — версия самой интеграции (релиз собирает его с ней вместе).
    version = (await async_get_integration(hass, DOMAIN)).version
    bundled = str(version) if version and await hass.async_add_executor_job(APK.is_file) else None

    def build(m: FrameManager, frame_id: str) -> list[FrameApkUpdate]:
        # Только рамки с APK: в браузере и PWA обновлять нечего — интерфейс и так берётся с HA.
        frame = m.frame(frame_id)
        return [FrameApkUpdate(m, frame_id, bundled)] if frame.get("apk") or frame.get("model") == "Android (APK)" else []

    entry.async_on_unload(setup_frame_platform(hass, manager, async_add_entities, build))


class FrameApkUpdate(FrameEntity, UpdateEntity):
    # PROGRESS — «устанавливается» держится, пока рамка не подключится с новой версией (или не выйдет время).
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    def __init__(self, manager: FrameManager, frame_id: str, bundled: str | None) -> None:
        super().__init__(manager, frame_id, "apk")
        self.bundled = bundled

    @property
    def installed_version(self) -> str | None:
        return self.manager.frame(self.frame_id).get("apk")

    @property
    def latest_version(self) -> str | None:
        # APK в интеграции нет (собрана без Android SDK) — обновлять нечем, считаем установленную последней.
        return self.bundled or self.installed_version

    @property
    def release_url(self) -> str | None:
        return RELEASES.format(self.bundled) if self.bundled else None

    @property
    def in_progress(self) -> bool:
        return bool(self.manager.live.get(self.frame_id, {}).get("updating"))

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        if not self.manager.async_command([self.frame_id], "update_apk"):
            return
        live = self.manager.live.setdefault(self.frame_id, {})
        live["updating"] = True
        self.async_write_ha_state()

        @callback
        def give_up(_now: Any) -> None:
            if live.pop("updating", None):
                self.async_write_ha_state()

        self.async_on_remove(async_call_later(self.hass, INSTALL_TIMEOUT, give_up))
