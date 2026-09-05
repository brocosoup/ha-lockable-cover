"""Constants for the lockable cover integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "lockable_cover"

# One config entry holds every proxy; each proxy is a subentry of this type.
SUBENTRY_TYPE_COVER: Final = "cover"

CONF_NAME: Final = "name"
CONF_COVER_ENTITY: Final = "cover_entity"
CONF_LOCK_ENTITY: Final = "lock_entity"
CONF_INVERT: Final = "invert"
