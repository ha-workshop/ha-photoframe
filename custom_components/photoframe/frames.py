"""Рамки как устройства: какие рамки есть, какая сейчас в сети, их альбом и стартовый экран, команды им.

Рамка (APK, PWA, вкладка браузера) открывает подписку photoframe/frame/connect со своим постоянным id:
пока подписка жива — рамка «в сети»; по ней же рамка получает своё состояние и команды.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ALBUM_ALL,
    CONF_MEDIA_FOLDER,
    DEFAULT_MEDIA_FOLDER,
    DOMAIN,
    MANUFACTURER,
    SIGNAL_FRAME_ADDED,
    SIGNAL_FRAME_UPDATED,
)
from .store import FrameStore, media_source_dir

_LOGGER = logging.getLogger(__name__)

Send = Callable[[dict[str, Any]], None]


class FrameManager:
    """Реестр рамок (хранится вместе с домами в .storage/photoframe) и живые подключения."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: FrameStore) -> None:
        self.hass = hass
        self.entry = entry
        self.store = store
        self.online: dict[str, Send] = {}
        # Что рамка сообщила о себе: текущее фото, показанный экран.
        self.live: dict[str, dict[str, Any]] = {}
        self.albums: list[str] = []

    # ── Реестр ────────────────────────────────────────────
    @property
    def frames(self) -> dict[str, dict[str, Any]]:
        return self.store.data.setdefault("frames", {})

    def frame(self, frame_id: str) -> dict[str, Any]:
        return self.frames.get(frame_id, {})

    async def async_start(self) -> None:
        await self.async_refresh_albums()
        # Поменялись дома или экраны — у сущностей «Стартовый экран» новый список.
        self.entry.async_on_unload(self.store.async_listen(self._async_all_updated))
        self.entry.async_on_unload(
            async_track_time_interval(self.hass, self._async_refresh_albums_tick, timedelta(minutes=10))
        )

    @callback
    def _async_all_updated(self) -> None:
        for frame_id in self.frames:
            async_dispatcher_send(self.hass, SIGNAL_FRAME_UPDATED.format(frame_id))

    async def _async_refresh_albums_tick(self, _now: Any) -> None:
        await self.async_refresh_albums()

    # ── Альбомы: подпапки папки фото ──────────────────────
    async def async_refresh_albums(self) -> None:
        source = media_source_dir(self.hass)
        folder = self.entry.options.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER).strip("/")
        if source is None:
            albums: list[str] = []
        else:
            root = Path(self.hass.config.media_dirs[source]) / folder

            def scan() -> list[str]:
                if not root.is_dir():
                    return []
                return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))

            albums = await self.hass.async_add_executor_job(scan)
        if albums != self.albums:
            self.albums = albums
            # Рамкам — новый список альбомов (выбор при загрузке), сущностям — новые варианты.
            self.store.async_notify()

    # ── Экраны: «Дом · Экран» для выбора стартового экрана рамки ──
    def screen_options(self) -> dict[str, str]:
        """Подпись → «дом/экран». Подписи уникальны: повтор получает номер."""
        data = self.store.data
        homes = data.get("homes") or [{"id": "main", "name": "Home"}]
        layouts = data.get("layouts") or {}
        many = len(homes) > 1
        out: dict[str, str] = {}
        for home in homes:
            screens = (layouts.get(home["id"]) or {}).get("screens") or [{"id": "main", "name": ""}]
            for i, screen in enumerate(screens):
                title = screen.get("name") or f"#{i + 1}"
                label = f"{home['name']} · {title}" if many else title
                base, n = label, 2
                while label in out:
                    label, n = f"{base} ({n})", n + 1
                out[label] = f"{home['id']}/{screen['id']}"
        return out

    # ── Подключение рамки ─────────────────────────────────
    @callback
    def async_connect(self, frame_id: str, info: dict[str, Any], send: Send) -> Callable[[], None]:
        frames = self.frames
        new = frame_id not in frames
        frame = frames.setdefault(frame_id, {"album": ALBUM_ALL})
        name = info.get("name") or frame.get("name") or f"Photo Frame {frame_id[:4]}"
        frame["name"] = frame.get("name") or name
        frame["model"] = info.get("model") or frame.get("model")
        # Версия APK-оболочки (только у Android-рамок) — для обновления APK из HA.
        if info.get("apk"):
            frame["apk"] = info["apk"]
            self.live.setdefault(frame_id, {}).pop("updating", None)
        self.hass.async_create_task(self.store.async_save_data())

        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, frame_id)},
            manufacturer=MANUFACTURER,
            model=frame.get("model") or "Photo Frame",
            name=frame["name"],
            sw_version=info.get("version"),
        )
        # Имя рамки в HA — главное: переименовали устройство — рамка узнает.
        frame["name"] = device.name_by_user or device.name or frame["name"]

        self.online[frame_id] = send
        send(self.state_message(frame_id))
        if new:
            async_dispatcher_send(self.hass, SIGNAL_FRAME_ADDED, frame_id)
        async_dispatcher_send(self.hass, SIGNAL_FRAME_UPDATED.format(frame_id))
        self.hass.async_create_task(self.async_refresh_albums())

        @callback
        def disconnect() -> None:
            if self.online.get(frame_id) is send:
                del self.online[frame_id]
                async_dispatcher_send(self.hass, SIGNAL_FRAME_UPDATED.format(frame_id))

        return disconnect

    def state_message(self, frame_id: str) -> dict[str, Any]:
        frame = self.frame(frame_id)
        return {
            "type": "state",
            "name": frame.get("name"),
            "album": frame.get("album") or ALBUM_ALL,
            "start_screen": frame.get("start_screen"),
            # Экран: включён ли (иначе спит — чёрный) и яркость в процентах.
            "screen_on": frame.get("screen_on", True),
            "brightness": frame.get("brightness", 100),
        }

    @callback
    def async_report(self, frame_id: str, data: dict[str, Any]) -> None:
        """Рамка сообщила о себе: текущее фото, экран."""
        self.live.setdefault(frame_id, {}).update(data)
        async_dispatcher_send(self.hass, SIGNAL_FRAME_UPDATED.format(frame_id))

    @callback
    def async_set_grid(self, frame_id: str, grid: dict[str, Any] | None) -> None:
        """Рамка сообщила свою сетку экрана с фото — помним её (другие рамки могут её взять)."""
        frame = self.frames.get(frame_id)
        if frame is None or frame.get("grid") == grid:
            return
        frame["grid"] = grid
        self.hass.async_create_task(self.store.async_save_data())

    # ── Настройки рамки из HA ─────────────────────────────
    async def async_set(self, frame_id: str, **patch: Any) -> None:
        if frame_id not in self.frames:
            return
        self.frames[frame_id].update(patch)
        await self.store.async_save_data()
        send = self.online.get(frame_id)
        if send:
            send(self.state_message(frame_id))
        async_dispatcher_send(self.hass, SIGNAL_FRAME_UPDATED.format(frame_id))

    @callback
    def async_command(self, frame_ids: list[str] | None, command: str, **data: Any) -> int:
        """Команда рамкам (все, если не указаны). Возвращает, скольким ушла (кто в сети)."""
        targets = frame_ids if frame_ids is not None else list(self.online)
        sent = 0
        for frame_id in targets:
            send = self.online.get(frame_id)
            if send:
                send({"type": "command", "command": command, **data})
                sent += 1
        return sent

    async def async_remove(self, frame_id: str) -> None:
        self.frames.pop(frame_id, None)
        self.live.pop(frame_id, None)
        await self.store.async_save_data()

    def frame_ids_for_devices(self, device_ids: list[str]) -> list[str]:
        registry = dr.async_get(self.hass)
        out = []
        for device_id in device_ids:
            device = registry.async_get(device_id)
            if device:
                out += [ident[1] for ident in device.identifiers if ident[0] == DOMAIN]
        return out
