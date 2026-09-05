"""Lock-aware cover platform for the lockable cover integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_LOCKED,
    STATE_ON,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)

from .const import CONF_COVER_ENTITY, CONF_INVERT, CONF_LOCK_ENTITY, CONF_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

LOCKED_STATES: frozenset[str] = frozenset({STATE_ON, STATE_LOCKED})
UNUSABLE_STATES: frozenset[str] = frozenset({STATE_UNAVAILABLE, STATE_UNKNOWN})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lockable cover platform from a config entry."""
    async_add_entities([LockableCover(entry)])


class LockableCover(CoverEntity):
    """A cover proxy that refuses to open while its lock is engaged."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the proxy cover from its config entry."""
        self._entry = entry
        self._source_entity: str = entry.data[CONF_COVER_ENTITY]
        self._lock_entity: str = entry.options.get(
            CONF_LOCK_ENTITY, entry.data[CONF_LOCK_ENTITY]
        )
        self._invert: bool = entry.options.get(
            CONF_INVERT, entry.data.get(CONF_INVERT, False)
        )
        self._lock_warning_logged = False
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.data[CONF_NAME]

    async def async_added_to_hass(self) -> None:
        """Subscribe to source cover and lock state changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity, self._lock_entity],
                self._async_source_changed,
            )
        )

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        """Write a new proxy state whenever an input entity changes."""
        self.async_write_ha_state()

    @property
    def _source_state(self) -> State | None:
        """Return the current state object of the source cover."""
        return self.hass.states.get(self._source_entity)

    def _source_attribute(self, attribute: str) -> Any | None:
        """Return an attribute of the source cover, if it has one."""
        if (source_state := self._source_state) is None:
            return None
        return source_state.attributes.get(attribute)

    @property
    def available(self) -> bool:
        """Return whether the source cover exists and is available."""
        source_state = self._source_state
        return source_state is not None and source_state.state != STATE_UNAVAILABLE

    @property
    def state(self) -> str | None:
        """Return the state mirrored from the source cover."""
        if (source_state := self._source_state) is None:
            return STATE_UNAVAILABLE
        return source_state.state

    @property
    def current_cover_position(self) -> int | None:
        """Return the position mirrored from the source cover."""
        return self._source_attribute(ATTR_CURRENT_POSITION)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the tilt position mirrored from the source cover."""
        return self._source_attribute(ATTR_CURRENT_TILT_POSITION)

    @property
    def is_opening(self) -> bool:
        """Return whether the source cover is opening."""
        return self.state == STATE_OPENING

    @property
    def is_closing(self) -> bool:
        """Return whether the source cover is closing."""
        return self.state == STATE_CLOSING

    @property
    def is_closed(self) -> bool:
        """Return whether the source cover is closed."""
        return self.state == STATE_CLOSED

    @property
    def device_class(self) -> str | None:
        """Return the device class of the source cover."""
        return self._source_attribute(ATTR_DEVICE_CLASS)

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return the features the source cover currently supports."""
        features = self._source_attribute(ATTR_SUPPORTED_FEATURES)
        if features is None:
            return CoverEntityFeature(0)
        return CoverEntityFeature(features)

    @property
    def icon(self) -> str | None:
        """Return a lock-aware icon when no device class applies."""
        if self.device_class is not None:
            return None
        return "mdi:lock" if self.is_locked else "mdi:lock-open-variant"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the lock state and the entities this proxy is built from."""
        return {
            "locked": self.is_locked,
            "lock_entity": self._lock_entity,
            "source_entity": self._source_entity,
        }

    @property
    def is_locked(self) -> bool:
        """Return whether the lock is engaged, failing closed when unusable."""
        lock_state = self.hass.states.get(self._lock_entity)

        if lock_state is None or lock_state.state in UNUSABLE_STATES:
            if not self._lock_warning_logged:
                self._lock_warning_logged = True
                _LOGGER.warning(
                    (
                        "Lock entity %s for %s is missing or unavailable; treating it"
                        " as locked until it reports a usable state"
                    ),
                    self._lock_entity,
                    self.entity_id,
                )
            return True

        self._lock_warning_logged = False
        locked = lock_state.state in LOCKED_STATES
        return not locked if self._invert else locked

    def _check_opening_allowed(self) -> None:
        """Raise if movement toward open is blocked by the lock."""
        if self.is_locked:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="cover_locked",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "lock_entity_id": self._lock_entity,
                },
            )

    def _check_position_allowed(self, target: int | None, current: int | None) -> None:
        """Raise if a target position moves the cover further open while locked."""
        if not self.is_locked:
            return
        # Fail closed: without both numbers we cannot prove the move is not an open.
        if target is None or current is None or target > current:
            self._check_opening_allowed()

    async def _async_call_source(
        self, service: str, service_data: dict[str, Any] | None = None
    ) -> None:
        """Forward an allowed command to the source cover."""
        data: dict[str, Any] = {ATTR_ENTITY_ID: self._source_entity}
        if service_data:
            data.update(service_data)
        await self.hass.services.async_call(COVER_DOMAIN, service, data, blocking=True)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the source cover unless the lock is engaged."""
        self._check_opening_allowed()
        await self._async_call_source(SERVICE_OPEN_COVER)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the source cover, which the lock never blocks."""
        await self._async_call_source(SERVICE_CLOSE_COVER)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the source cover, which the lock never blocks."""
        await self._async_call_source(SERVICE_STOP_COVER)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the source cover tilt unless the lock is engaged."""
        self._check_opening_allowed()
        await self._async_call_source(SERVICE_OPEN_COVER_TILT)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the source cover tilt, which the lock never blocks."""
        await self._async_call_source(SERVICE_CLOSE_COVER_TILT)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the source cover tilt, which the lock never blocks."""
        await self._async_call_source(SERVICE_STOP_COVER_TILT)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the source position, blocking moves toward open while locked."""
        position: int | None = kwargs.get(ATTR_POSITION)
        self._check_position_allowed(position, self.current_cover_position)
        await self._async_call_source(
            SERVICE_SET_COVER_POSITION, {ATTR_POSITION: position}
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the source tilt, blocking moves toward open while locked."""
        position: int | None = kwargs.get(ATTR_TILT_POSITION)
        self._check_position_allowed(position, self.current_cover_tilt_position)
        await self._async_call_source(
            SERVICE_SET_COVER_TILT_POSITION, {ATTR_TILT_POSITION: position}
        )

    async def async_toggle(self, **kwargs: Any) -> None:
        """Resolve the toggle to an open or a close, then apply the lock rules."""
        if self.state in (STATE_CLOSED, STATE_CLOSING):
            await self.async_open_cover(**kwargs)
            return
        await self.async_close_cover(**kwargs)

    async def async_toggle_tilt(self, **kwargs: Any) -> None:
        """Resolve the tilt toggle to an open or a close, then apply the lock rules."""
        if self.current_cover_tilt_position == 0:
            await self.async_open_cover_tilt(**kwargs)
            return
        await self.async_close_cover_tilt(**kwargs)
