"""Binary sensor platform for Tapo Camera Local AI detections (Baby Cry, Dog Bark, etc.)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AI_BINARY_SENSORS, DOMAIN, TapoAIBinarySensorSpec
from .coordinator import TapoLocalAICoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo AI detection binary sensors from a config entry."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        TapoAIBinarySensor(coordinator, spec)
        for spec in AI_BINARY_SENSORS
    ]
    async_add_entities(entities)


class TapoAIBinarySensor(CoordinatorEntity[TapoLocalAICoordinator], BinarySensorEntity):
    """Representation of a Tapo Local AI Event Binary Sensor (Baby Cry, Bark, Person, Pet, etc.)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TapoLocalAICoordinator,
        spec: TapoAIBinarySensorSpec,
    ) -> None:
        """Initialize the AI binary sensor."""
        super().__init__(coordinator)
        self.spec = spec
        self._attr_unique_id = f"{coordinator.serial_number}_{spec.key}"
        self._attr_translation_key = spec.translation_key
        self._attr_name = spec.name_vi
        self._attr_device_class = spec.device_class
        self._attr_icon = spec.icon
        self._attr_entity_registry_enabled_default = spec.enabled_by_default
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return True if the AI event is currently detected."""
        if not self.coordinator.data:
            return False
        sensor_data = self.coordinator.data.get("sensors", {}).get(self.spec.key, {})
        return bool(sensor_data.get("is_on", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed attributes for the AI event sensor."""
        if not self.coordinator.data:
            return {}
        sensor_data = self.coordinator.data.get("sensors", {}).get(self.spec.key, {})
        last_ts = sensor_data.get("last_triggered_ts", 0.0)
        attrs: dict[str, Any] = {
            "event_key": self.spec.key,
            "supported_alarm_types": list(self.spec.alarm_types),
            "hold_seconds": self.coordinator.hold_seconds,
            "last_triggered": (
                datetime.fromtimestamp(last_ts).isoformat() if last_ts > 0 else None
            ),
        }
        for field in (
            "last_event_start",
            "last_event_end",
            "alarm_type_id",
            "events_1_bitmask",
            "onvif_field",
            "detection_source",
        ):
            if field in sensor_data:
                attrs[field] = sensor_data[field]
        return attrs
