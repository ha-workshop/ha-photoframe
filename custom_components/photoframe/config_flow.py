"""Мастер настройки: одна интеграция на HA; параметры — в «Настроить»."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_EDIT, CONF_KIOSK, CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER, DOMAIN, EDIT_ADMINS, EDIT_USERS


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_MEDIA_FOLDER, default=options.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER)): str,
            vol.Required(CONF_KIOSK, default=options.get(CONF_KIOSK, False)): bool,
            vol.Required(CONF_EDIT, default=options.get(CONF_EDIT, EDIT_ADMINS)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[EDIT_ADMINS, EDIT_USERS],
                    translation_key=CONF_EDIT,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
    )


class PhotoFrameConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Photo Frame", data={}, options=user_input)
        return self.async_show_form(step_id="user", data_schema=_options_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PhotoFrameOptionsFlow()


class PhotoFrameOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=_options_schema(dict(self.config_entry.options)))
