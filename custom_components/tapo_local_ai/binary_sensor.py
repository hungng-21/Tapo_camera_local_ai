"""Binary sensor platform for Tapo Camera Local AI detections & Face Recognition."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AI_BINARY_SENSORS, ATTR_RECOGNIZED, DOMAIN, TapoAIBinarySensorSpec
from .coordinator import TapoLocalAICoordinator
from .entity import TapoC260Entity, TapoC260HealthEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo AI detection and Face Recognition binary sensors from a config entry."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        TapoAIBinarySensor(coordinator, spec)
        for spec in AI_BINARY_SENSORS
    ]
    entities.append(TapoC260ConnectionBinarySensor(coordinator))
    if coordinator.supports_face:
        entities.extend(
            [
                TapoC260RecognizedBinarySensor(coordinator),
                TapoC260StrangerBinarySensor(coordinator),
            ]
        )
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


class TapoC260RecognizedBinarySensor(TapoC260Entity, BinarySensorEntity):
    """Whether the current detected Face ID is a configured known person."""

    _attr_icon = "mdi:face-recognition"
    _attr_name = "Nhận diện người quen (Face Recognized)"

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_face_recognized"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.current.get(ATTR_RECOGNIZED, False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.coordinator.current)


class TapoC260StrangerBinarySensor(TapoC260Entity, BinarySensorEntity):
    """On when an unknown face is detected; auto-clears after stranger_clear_seconds."""

    _attr_icon = "mdi:account-alert"
    _attr_name = "Phát hiện người lạ (Stranger Detected)"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_stranger_detected"

    @property
    def is_on(self) -> bool:
        return self.coordinator.stranger_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "clear_after_seconds": self.coordinator.stranger_clear_seconds,
            **self.coordinator.current,
        }


class TapoC260ConnectionBinarySensor(TapoC260HealthEntity, BinarySensorEntity):
    """On when recent camera polling succeeded; Off when disconnected."""

    _attr_name = "Kết nối Camera (Camera Connection)"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_connection"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.health()["connected"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        health = self.coordinator.health()
        return {
            "status": health["status"],
            "last_error": health["last_error"],
            "consecutive_failures": health["consecutive_failures"],
        }
