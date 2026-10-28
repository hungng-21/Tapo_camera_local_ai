"""Event entity for Tapo Camera Local AI Face Recognition."""
from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ALARM_TYPE,
    ATTR_CAMERA,
    ATTR_EVENT_TIME,
    ATTR_FACE_ID,
    ATTR_NAME,
    ATTR_RECOGNIZED,
    DOMAIN,
)
from .coordinator import TapoLocalAICoordinator
from .entity import TapoC260Entity

EVENT_RECOGNIZED = "face_recognized"
EVENT_UNKNOWN = "face_unknown"


class TapoC260FaceEvent(TapoC260Entity, EventEntity):
    """Trigger entity for Home Assistant automations: face_recognized / face_unknown."""

    _attr_icon = "mdi:face-recognition"
    _attr_name = "Sự kiện Khuôn mặt (Face Event)"
    _attr_event_types = [EVENT_RECOGNIZED, EVENT_UNKNOWN]

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_face_event"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_face_listener(self._handle_face)
        )

    @callback
    def _handle_face(self, payload: dict[str, Any]) -> None:
        event_type = (
            EVENT_RECOGNIZED if payload.get(ATTR_RECOGNIZED) else EVENT_UNKNOWN
        )
        self._trigger_event(
            event_type,
            {
                key: payload.get(key)
                for key in (
                    ATTR_FACE_ID,
                    ATTR_NAME,
                    ATTR_RECOGNIZED,
                    ATTR_EVENT_TIME,
                    ATTR_ALARM_TYPE,
                    ATTR_CAMERA,
                )
            },
        )
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the face event entity."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.supports_face:
        async_add_entities([TapoC260FaceEvent(coordinator)])
