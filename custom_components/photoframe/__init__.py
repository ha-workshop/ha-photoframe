"""Photo Frame — фоторамка с управлением домом для Home Assistant.

Интеграция хранит дома, экраны и настройки рамки в HA (.storage/photoframe) и раздаёт интерфейс:
карточку для дашбордов и отдельное приложение (PWA) по адресу /photoframe/ — его же открывает
APK-оболочка на старых Android-рамках. Вход — обычный вход в HA, без токенов.
"""
from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from . import websocket_api
from .const import DOMAIN, URL_CARD, URL_PWA
from .store import FrameStore

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Собранный интерфейс (CI кладёт сюда сборку из ha-workshop/lovelace-photoframe).
FRONTEND = Path(__file__).parent / "frontend"

type PhotoFrameConfigEntry = ConfigEntry[FrameStore]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    websocket_api.async_setup(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry) -> bool:
    store = FrameStore(hass)
    await store.async_load()
    entry.runtime_data = store
    await _async_register_frontend(hass)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PhotoFrameConfigEntry) -> bool:
    # Раздачу файлов в HA отменить нельзя — она остаётся до перезапуска; данные выгружать незачем.
    return True


async def _async_options_updated(hass: HomeAssistant, entry: PhotoFrameConfigEntry) -> None:
    entry.runtime_data.async_notify()


class PwaRedirectView(HomeAssistantView):
    """/photoframe и /photoframe/ → /photoframe/index.html (каталог HA не отдаёт).
    Регистрируется раньше раздачи файлов — поэтому срабатывает первым."""

    url = URL_PWA
    extra_urls = [URL_PWA + "/"]
    name = "photoframe:pwa"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        raise web.HTTPFound(URL_PWA + "/index.html")


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Раздать PWA и карточку и подключить карточку ко всем дашбордам.

    Свою карточку подключаем всегда, даже если отдельно стоит Dashboard-карточка из HACS: наш скрипт
    грузится раньше ресурсов дашбордов, а элемент регистрируется только один раз — работает версия
    из интеграции. Угадывать «стоит ли отдельная карточка» по ресурсам ненадёжно: после удаления из HACS
    ресурс часто остаётся, а HACS уже не отдаёт файл — и карточки не было бы совсем.
    """
    flags = hass.data.setdefault(DOMAIN, {})
    if flags.get("frontend"):
        return
    flags["frontend"] = True

    pwa = FRONTEND / "pwa"
    card = FRONTEND / "photoframe-card.js"
    paths = []
    if pwa.is_dir():
        paths.append(StaticPathConfig(URL_PWA, str(pwa), cache_headers=False))
        hass.http.register_view(PwaRedirectView())
    if card.is_file():
        paths.append(StaticPathConfig(URL_CARD, str(card), cache_headers=False))
    if not paths:
        _LOGGER.warning("Photo Frame: нет собранного интерфейса в %s", FRONTEND)
        return
    await hass.http.async_register_static_paths(paths)

    if card.is_file():
        # В адресе — версия и время сборки: после обновления браузер не возьмёт старую карточку из кэша.
        version = (await async_get_integration(hass, DOMAIN)).version
        built = int(card.stat().st_mtime)
        add_extra_js_url(hass, f"{URL_CARD}?v={version}-{built}")
