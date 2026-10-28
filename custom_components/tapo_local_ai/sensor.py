"""Sensors for Tapo Camera Local AI Face Recognition & Health Diagnostics."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ALARM_TYPE,
    ATTR_CAMERA,
    ATTR_END_TIME,
    ATTR_EVENT_TIME,
    ATTR_EVENTS_1,
    ATTR_FACE_ID,
    ATTR_NAME,
    ATTR_RECOGNIZED,
    ATTR_START_TIME,
    DEFAULT_FACE_NAME,
    DOMAIN,
)
from .coordinator import TapoLocalAICoordinator
from .entity import TapoC260Entity, TapoC260HealthEntity


class TapoC260FaceNameSensor(TapoC260Entity, SensorEntity):
    """Current detected face name."""

    _attr_icon = "mdi:face-recognition"
    _attr_name = "Tên khuôn mặt (Face Name)"

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_face_name"

    @property
    def native_value(self) -> str:
        return str(self.coordinator.current.get(ATTR_NAME, DEFAULT_FACE_NAME))

    @property
    def extra_state_attributes(self) -> dict:
        return dict(self.coordinator.current)


class TapoC260FaceIdSensor(TapoC260Entity, SensorEntity):
    """Current detected Face ID."""

    _attr_icon = "mdi:identifier"
    _attr_name = "Mã khuôn mặt (Face ID)"

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_face_id"

    @property
    def native_value(self) -> str | None:
        value = self.coordinator.current.get(ATTR_FACE_ID)
        return None if value is None else str(value)

    @property
    def extra_state_attributes(self) -> dict:
        return dict(self.coordinator.current)


class TapoC260LastSeenSensor(TapoC260Entity, SensorEntity):
    """ISO timestamp of the last processed face event."""

    _attr_icon = "mdi:clock-outline"
    _attr_name = "Lần nhận diện khuôn mặt gần nhất (Last Seen)"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_last_seen"

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.current.get(ATTR_EVENT_TIME)
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "face_id": self.coordinator.current.get(ATTR_FACE_ID),
            "name": self.coordinator.current.get(ATTR_NAME),
            "recognized": self.coordinator.current.get(ATTR_RECOGNIZED),
            "start_time": self.coordinator.current.get(ATTR_START_TIME),
            "end_time": self.coordinator.current.get(ATTR_END_TIME),
            "alarm_type": self.coordinator.current.get(ATTR_ALARM_TYPE),
            "events_1": self.coordinator.current.get(ATTR_EVENTS_1),
            "camera": self.coordinator.current.get(ATTR_CAMERA),
        }


class TapoC260KnownFacesSensor(TapoC260Entity, SensorEntity):
    """Number of configured known faces."""

    _attr_icon = "mdi:account-check"
    _attr_name = "Số khuôn mặt người quen (Known Faces)"

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_known_faces"

    @property
    def native_value(self) -> int:
        return self.coordinator.known_face_count

    @property
    def extra_state_attributes(self) -> dict:
        return {"faces": dict(self.coordinator.faces)}


class TapoC260UnknownFacesSensor(TapoC260Entity, SensorEntity):
    """Number of discovered unknown faces."""

    _attr_icon = "mdi:account-question"
    _attr_name = "Số khuôn mặt người lạ (Unknown Faces)"

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_unknown_faces"

    @property
    def native_value(self) -> int:
        return (
            coordinator.unknown_face_count
            if (coordinator := self.coordinator)
            else 0
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {"faces": dict(self.coordinator.unknown_faces)}


class TapoC260UnknownTodaySensor(TapoC260Entity, SensorEntity):
    """Number of stranger detections today (local time)."""

    _attr_icon = "mdi:account-clock"
    _attr_name = "Số lần người lạ hôm nay (Unknown Today)"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_unknown_today"

    @property
    def native_value(self) -> int:
        return self.coordinator.unknown_today


class TapoC260LastUnknownSeenSensor(TapoC260Entity, SensorEntity):
    """Last time the camera detected an unknown face."""

    _attr_icon = "mdi:clock-alert-outline"
    _attr_name = "Lần gặp người lạ gần nhất (Last Unknown Seen)"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_last_unknown_seen"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_unknown_seen


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class TapoC260LastPollSensor(TapoC260HealthEntity, SensorEntity):
    """Last successful poll timestamp."""

    _attr_icon = "mdi:check-network-outline"
    _attr_name = "Lần quét thành công gần nhất (Last Successful Poll)"
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_last_poll"

    @property
    def native_value(self) -> datetime | None:
        return _parse(self.coordinator.health()["last_success"])

    @property
    def extra_state_attributes(self) -> dict:
        return {"last_attempt": self.coordinator.health()["last_attempt"]}


class TapoC260ResponseTimeSensor(TapoC260HealthEntity, SensorEntity):
    """Response time in ms of the latest camera poll."""

    _attr_icon = "mdi:timer-outline"
    _attr_name = "Thời gian phản hồi Camera (Response Time)"
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_response_time"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.health()["response_ms"]


class TapoC260PollErrorsSensor(TapoC260HealthEntity, SensorEntity):
    """Number of consecutive polling errors (0 = healthy)."""

    _attr_icon = "mdi:alert-circle-outline"
    _attr_name = "Số lỗi quét liên tiếp (Polling Errors)"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_poll_errors"

    @property
    def native_value(self) -> int:
        return self.coordinator.health()["consecutive_failures"]

    @property
    def extra_state_attributes(self) -> dict:
        health = self.coordinator.health()
        return {
            "total_failures": health["total_failures"],
            "last_error": health["last_error"],
            "last_error_time": health["last_error_time"],
        }


class TapoC260ModeSensor(TapoC260HealthEntity, SensorEntity):
    """Current camera session mode."""

    _attr_icon = "mdi:link-variant"
    _attr_name = "Chế độ phiên kết nối (Connection Mode)"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["shared", "standalone", "wait", "starting"]

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_mode"

    @property
    def native_value(self) -> str:
        mode = self.coordinator.health()["mode"]
        return mode if mode in self._attr_options else "starting"


class TapoC260DedupSkippedSensor(TapoC260HealthEntity, SensorEntity):
    """Number of known-face events skipped due to dedup cooldown."""

    _attr_icon = "mdi:filter-remove-outline"
    _attr_name = "Số lần bỏ qua lặp khuôn mặt (Dedup Skipped)"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_dedup_skipped"

    @property
    def native_value(self) -> int:
        return self.coordinator.health()["dedup_skipped"]

    @property
    def extra_state_attributes(self) -> dict:
        return {"events_processed": self.coordinator.health()["events_processed"]}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo Face Recognition & Health sensors."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    diag_sensors = [
        TapoC260LastPollSensor(coordinator),
        TapoC260ResponseTimeSensor(coordinator),
        TapoC260PollErrorsSensor(coordinator),
        TapoC260ModeSensor(coordinator),
    ]
    if coordinator.supports_face:
        diag_sensors.extend(
            [
                TapoC260FaceNameSensor(coordinator),
                TapoC260FaceIdSensor(coordinator),
                TapoC260LastSeenSensor(coordinator),
                TapoC260KnownFacesSensor(coordinator),
                TapoC260UnknownFacesSensor(coordinator),
                TapoC260UnknownTodaySensor(coordinator),
                TapoC260LastUnknownSeenSensor(coordinator),
                TapoC260DedupSkippedSensor(coordinator),
            ]
        )
    async_add_entities(diag_sensors)
