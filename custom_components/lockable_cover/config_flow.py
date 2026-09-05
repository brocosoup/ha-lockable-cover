"""Config flow for the lockable cover integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    CONF_COVER_ENTITY,
    CONF_INVERT,
    CONF_LOCK_ENTITY,
    CONF_NAME,
    DOMAIN,
    SUBENTRY_TYPE_COVER,
)

TITLE = "Lockable Cover"

LOCK_SELECTOR = EntitySelector(
    EntitySelectorConfig(domain=["lock", "switch", "input_boolean"])
)


def _lock_schema(name: str = "", invert: bool = False) -> dict[Any, Any]:
    """Return the fields shared by the add and reconfigure steps."""
    return {
        vol.Required(CONF_NAME, default=name): str,
        vol.Required(CONF_LOCK_ENTITY): LOCK_SELECTOR,
        vol.Optional(CONF_INVERT, default=invert): BooleanSelector(
            BooleanSelectorConfig()
        ),
    }


class LockableCoverConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the single container entry for lockable cover."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the one entry that holds every proxy cover."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title=TITLE, data={})

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types this integration supports."""
        return {SUBENTRY_TYPE_COVER: LockableCoverSubentryFlow}


class LockableCoverSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure one proxy cover."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a proxy for a source cover."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cover_entity: str = user_input[CONF_COVER_ENTITY]
            registry_entry = er.async_get(self.hass).async_get(cover_entity)
            if registry_entry is not None and registry_entry.platform == DOMAIN:
                errors[CONF_COVER_ENTITY] = "recursive_source"
            elif any(
                subentry.data.get(CONF_COVER_ENTITY) == cover_entity
                for subentry in self._get_entry().subentries.values()
            ):
                errors[CONF_COVER_ENTITY] = "already_configured"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                    unique_id=cover_entity,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COVER_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="cover")
                    ),
                    **_lock_schema(),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change the lock of an existing proxy.

        The source cover is deliberately absent: changing it would change the
        identity of the entity rather than reconfigure it.
        """
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            self.hass.config_entries.async_update_subentry(
                self._get_entry(),
                subentry,
                data={**subentry.data, **user_input},
                title=user_input[CONF_NAME],
            )
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    _lock_schema(
                        name=subentry.data[CONF_NAME],
                        invert=subentry.data.get(CONF_INVERT, False),
                    )
                ),
                subentry.data,
            ),
            description_placeholders={
                "source_entity": subentry.data[CONF_COVER_ENTITY]
            },
        )
