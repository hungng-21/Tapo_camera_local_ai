"""Siren platform for Tapo Camera Local AI (Turn On/Off Siren with Duration & Volume control)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_VOLUME_LEVEL,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TapoLocalAICoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tapo Camera Siren entity from a config entry."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TapoCameraSiren(coordinator)])


class TapoCameraSiren(CoordinatorEntity[TapoLocalAICoordinator], SirenEntity):
    """Representation of the built-in Siren on a Tapo camera."""

    _attr_has_entity_name = True
    _attr_translation_key = "siren"
    _attr_name = "Siren (Còi báo động)"
    _attr_icon = "mdi:bullhorn-variant"
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.DURATION
        | SirenEntityFeature.VOLUME_SET
    )

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Siren entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_siren"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return True if the manual siren is currently sounding."""
        return bool(self.coordinator.siren_is_on)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return current siren configuration attributes."""
        return {
            "alarm_mode": self.coordinator.alarm_mode,
            "siren_volume": self.coordinator.siren_volume,
            "siren_volume_level": self.coordinator.siren_volume_level,
            "siren_duration": self.coordinator.siren_duration,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the camera siren with optional duration and volume_level."""
        duration = kwargs.get(ATTR_DURATION)
        volume_level = kwargs.get(ATTR_VOLUME_LEVEL)
        await self.coordinator.async_turn_on_siren(
            duration=int(duration) if duration is not None else None,
            volume_level=float(volume_level) if volume_level is not None else None,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the camera siren."""
        await self.coordinator.async_turn_off_siren()
