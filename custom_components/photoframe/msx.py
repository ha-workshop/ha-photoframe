"""Media Station X (MSX) — запуск рамки на телевизоре через приложение из магазина.

MSX — «браузер» для телевизоров Samsung/LG/Android TV: при старте он забирает стартовый JSON
с адреса `http://<сервер>/msx/start.json` и показывает меню или контент. Своё приложение для
телевизора тогда не нужно — MSX открывает PWA рамки действием `link:`.

Здесь отдаём два адреса:
  /msx/start.json   — стартовый объект (MSX всегда ищет его по этому пути);
  /msx/content.json — страница-мостик: действие `link:` открывает /photoframe/?tv=1.
                      Оно выполняется при старте MSX; после возврата из рамки не повторяется,
                      и на экране остаётся кнопка «Открыть рамку».

Адрес HA собираем из запроса: MSX на телевизоре ходит к HA напрямую, поэтому схема и хост
совпадают с тем, что ввели в настройках MSX. Ответы — с CORS: JSON MSX загружает через fetch.
"""
from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import URL_PWA

_LOGGER = logging.getLogger(__name__)

MSX_START = "/msx/start.json"
MSX_CONTENT = "/msx/content.json"

_CORS = {"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"}


def _origin(request: web.Request) -> str:
    """Адрес HA, по которому пришёл MSX (с учётом обратного прокси)."""
    proto = request.headers.get("X-Forwarded-Proto", request.scheme).split(",")[0].strip()
    host = request.headers.get("X-Forwarded-Host", request.host).split(",")[0].strip()
    return f"{proto}://{host}"


class MsxStartView(HomeAssistantView):
    """Стартовый объект MSX. {SERVER} MSX подставляет только в этом файле."""

    url = MSX_START
    name = "photoframe:msx:start"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "name": "Photo Frame",
                "version": "1.0.0",
                # {SERVER} MSX подставляет только в стартовом файле. http:// — чтобы работало и на
                # старых MSX (0.1.65+); в HTTPS-режиме MSX сам поднимет JSON-адреса до https.
                "parameter": f"content:http://{{SERVER}}{MSX_CONTENT}",
            },
            headers=_CORS,
        )


class MsxContentView(HomeAssistantView):
    """Страница-мостик: сразу открывает рамку, а после возврата показывает кнопку."""

    url = MSX_CONTENT
    name = "photoframe:msx:content"
    requires_auth = False

    def __init__(self, language: str) -> None:
        self.label = "Открыть рамку" if language.startswith("ru") else "Open the frame"

    async def get(self, request: web.Request) -> web.Response:
        action = f"link:{_origin(request)}{URL_PWA}/?tv=1"
        return web.json_response(
            {
                "name": "Photo Frame",
                "version": "1.0.0",
                # Действие стартовой страницы: MSX выполняет его при запуске и не повторяет,
                # когда пользователь возвращается из рамки (start action skipped on restore).
                "action": action,
                "headline": "Photo Frame",
                "type": "list",
                "pages": [
                    {
                        "items": [
                            {
                                "layout": "0,0,12,1",
                                "label": self.label,
                                "action": action,
                                "focus": True,
                            }
                        ]
                    }
                ],
            },
            headers=_CORS,
        )


def async_setup(hass: HomeAssistant) -> None:
    """Зарегистрировать адреса MSX. Занятый путь не должен ломать запуск интеграции."""
    for view in (MsxStartView(), MsxContentView(hass.config.language)):
        try:
            hass.http.register_view(view)
        except RuntimeError:
            _LOGGER.warning("Photo Frame: адрес MSX %s уже занят другим приложением", view.url)
