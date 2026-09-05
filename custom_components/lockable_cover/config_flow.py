"""Config flow for the lockable cover integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
)

from .const import CONF_COVER_ENTITY, CONF_INVERT, CONF_LOCK_ENTITY, CONF_NAME, DOMAIN

LOCK_SELECTOR = EntitySelector(
    EntitySelectorConfig(domain=["lock", "switch", "input_boolean"])
)


class LockableCoverConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for lockable cover."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cover_entity: str = user_input[CONF_COVER_ENTITY]
            registry_entry = er.async_get(self.hass).async_get(cover_entity)
            if registry_entry is not None and registry_entry.platform == DOMAIN:
                errors[CONF_COVER_ENTITY] = "recursive_source"
            else:
                await self.async_set_unique_id(cover_entity)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_COVER_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="cover")
                    ),
                    vol.Required(CONF_LOCK_ENTITY): LOCK_SELECTOR,
                    vol.Optional(CONF_INVERT, default=False): BooleanSelector(
                        BooleanSelectorConfig()
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return LockableCoverOptionsFlow(config_entry)


class LockableCoverOptionsFlow(OptionsFlow):
    """Handle lockable cover options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Store the entry the options belong to."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self._entry.options
        data = self._entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCK_ENTITY,
                        default=options.get(CONF_LOCK_ENTITY, data[CONF_LOCK_ENTITY]),
                    ): LOCK_SELECTOR,
                    vol.Optional(
                        CONF_INVERT,
                        default=options.get(CONF_INVERT, data.get(CONF_INVERT, False)),
                    ): BooleanSelector(BooleanSelectorConfig()),
                }
            ),
        )
