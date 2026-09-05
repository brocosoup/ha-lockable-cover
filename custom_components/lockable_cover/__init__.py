"""The lockable cover integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_COVER_ENTITY,
    CONF_INVERT,
    CONF_LOCK_ENTITY,
    CONF_NAME,
    DOMAIN,
    SUBENTRY_TYPE_COVER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the lockable cover config entry."""
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the lockable cover config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when a subentry is added, changed, or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a v1 entry, which held one proxy, into a subentry of a container.

    Version 1 stored a single proxy per config entry. Version 2 keeps one entry
    that holds every proxy as a subentry, so more covers can be added without
    setting the integration up again.
    """
    if entry.version != 1:
        return True

    if CONF_COVER_ENTITY not in entry.data:
        # Nothing to carry over; just mark the entry as migrated.
        hass.config_entries.async_update_entry(entry, version=2)
        return True

    # Options took precedence over data in version 1.
    proxy = {
        CONF_NAME: entry.data[CONF_NAME],
        CONF_COVER_ENTITY: entry.data[CONF_COVER_ENTITY],
        CONF_LOCK_ENTITY: entry.options.get(
            CONF_LOCK_ENTITY, entry.data[CONF_LOCK_ENTITY]
        ),
        CONF_INVERT: entry.options.get(CONF_INVERT, entry.data.get(CONF_INVERT, False)),
    }

    subentry = ConfigSubentry(
        data=proxy,
        subentry_type=SUBENTRY_TYPE_COVER,
        title=proxy[CONF_NAME],
        unique_id=proxy[CONF_COVER_ENTITY],
    )
    hass.config_entries.async_add_subentry(entry, subentry)

    # The entity used to be keyed on the entry id. Re-key it on the subentry so
    # the existing entity_id, name, and history survive the migration.
    registry = er.async_get(hass)
    if entity_id := registry.async_get_entity_id(
        Platform.COVER, DOMAIN, entry.entry_id
    ):
        registry.async_update_entity(
            entity_id,
            new_unique_id=subentry.subentry_id,
            config_subentry_id=subentry.subentry_id,
        )
        _LOGGER.debug("Re-keyed %s onto subentry %s", entity_id, subentry.subentry_id)

    hass.config_entries.async_update_entry(
        entry, data={}, options={}, title="Lockable Cover", version=2
    )
    return True
