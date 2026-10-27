"""Хранилище рамки: дома, экраны и настройки — общие для карточки на дашборде и для всех рамок (PWA, APK)."""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from .frames import FrameManager

from .const import CARD_TYPE, SETUP_DASHBOARD, STORAGE_KEY, STORAGE_VERSION


def media_source_dir(hass: HomeAssistant) -> str | None:
    """Источник «Моих медиа», куда класть фото: обычно local (= /media), но в configuration.yaml
    media_dirs можно назвать иначе (например, media: /media) — тогда берём первый."""
    dirs = hass.config.media_dirs
    if "local" in dirs:
        return "local"
    return next(iter(dirs), None)


async def async_ensure_media_folder(hass: HomeAssistant, folder: str) -> None:
    """Создать папку фото в медиатеке, если её нет: загружать фото в несуществующую папку HA не даёт."""
    source = media_source_dir(hass)
    if source is None or not folder:
        return
    path = Path(hass.config.media_dirs[source]) / folder.strip("/")
    try:
        await hass.async_add_executor_job(lambda: path.mkdir(parents=True, exist_ok=True))
    except OSError as err:
        _LOGGER.warning("Photo Frame: не удалось создать папку фото %s: %s", path, err)

_LOGGER = logging.getLogger(__name__)

# Ключи, которые хранит интеграция и которые можно менять через photoframe/config/save.
KEYS = ("homes", "layouts", "settings")


class FrameStore:
    """Данные рамки в .storage/photoframe и подписчики на их изменения."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {}
        self._listeners: list[Callable[[], None]] = []
        # Рамки как устройства — заводит async_setup_entry.
        self.frames: FrameManager

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data is None:
            # Первый запуск: забираем дома и экраны из карточки на дашборде, если она уже есть.
            data = await _import_from_dashboards(self.hass) or {}
            await self._store.async_save(data)
        self.data = data

    async def async_update(self, patch: dict[str, Any]) -> None:
        for key in KEYS:
            if key in patch:
                self.data[key] = patch[key]
        await self._store.async_save(self.data)
        self.async_notify()

    async def async_save_data(self) -> None:
        """Сохранить без рассылки конфига — для реестра рамок (рамкам он не нужен)."""
        await self._store.async_save(self.data)

    @callback
    def async_notify(self) -> None:
        """Разослать подписчикам свежий конфиг (сохранили данные или поменяли настройки интеграции)."""
        for listener in list(self._listeners):
            listener()

    @callback
    def async_listen(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove


def _find_card(node: Any) -> dict[str, Any] | None:
    """Карточка рамки в конфиге дашборда — в карточках вида, в секциях или во вложенных стеках."""
    if isinstance(node, dict):
        if node.get("type") == CARD_TYPE:
            return node
        for key in ("views", "cards", "sections"):
            for child in node.get(key) or []:
                found = _find_card(child)
                if found:
                    return found
        if isinstance(node.get("card"), dict):
            return _find_card(node["card"])
    return None


async def _import_from_dashboards(hass: HomeAssistant) -> dict[str, Any] | None:
    """Дома, экраны и настройки из карточки на дашборде (сначала «Фоторамка», потом остальные)."""
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA  # noqa: PLC0415

        dashboards = hass.data[LOVELACE_DATA].dashboards
    except (ImportError, KeyError, AttributeError):
        return None
    order = sorted(dashboards, key=lambda path: path != SETUP_DASHBOARD)
    for path in order:
        try:
            config = await dashboards[path].async_load(False)
        except Exception:  # noqa: BLE001 — дашборд в YAML, пустой или ещё не создан
            continue
        card = _find_card(config)
        if card:
            _LOGGER.info("Photo Frame: перенесены дома и экраны из карточки на дашборде %s", path or "по умолчанию")
            return {key: card[key] for key in KEYS if key in card}
    return None
