"""Number platform for Tapo Camera Local AI (Visual/Motion Sensitivities 1-10, Siren Duration, Speaker/Mic Volume, PTZ Step Angle)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AI_SENSITIVITY_SPECS, DOMAIN, TapoSensitivitySpec
from .coordinator import TapoLocalAICoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo Number entities for 10-level visual/motion sensitivity, Siren duration, Audio volumes, and PTZ step angle."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = [
        TapoSirenDurationNumber(coordinator),
        TapoSpeakerVolumeNumber(coordinator),
        TapoMicrophoneVolumeNumber(coordinator),
    ]

    # Add 1-10 sliders ONLY for 10-level visual/motion detections (Motion, Person, Pet, Vehicle)
    for spec in AI_SENSITIVITY_SPECS:
        if spec.control_type == "number_10":
            entities.append(TapoAISensitivityNumber(coordinator, spec))

    if coordinator.supports_ptz:
        entities.append(TapoPTZMovementAngleNumber(coordinator))

    async_add_entities(entities)


class TapoAISensitivityNumber(CoordinatorEntity[TapoLocalAICoordinator], NumberEntity):
    """Number entity (1-10 slider) to adjust visual AI (Person, Pet, Vehicle) and Motion detection sensitivity."""

    _attr_has_entity_name = True
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: TapoLocalAICoordinator,
        spec: TapoSensitivitySpec,
    ) -> None:
        """Initialize the AI sensitivity slider entity."""
        super().__init__(coordinator)
        self.spec = spec
        self._attr_unique_id = f"{coordinator.serial_number}_{spec.key}"
        self._attr_translation_key = spec.key
        self._attr_name = spec.name_vi
        self._attr_icon = spec.icon
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float:
        """Return current sensitivity level on 1-10 scale."""
        if not self.coordinator.data:
            return 5.0
        val = self.coordinator.data.get("sensitivity_10", {}).get(self.spec.key, 5)
        return float(val)

    async def async_set_native_value(self, value: float) -> None:
        """Set sensitivity level (1-10) on the camera."""
        await self.coordinator.async_set_sensitivity_10(self.spec, int(value))


class TapoSirenDurationNumber(CoordinatorEntity[TapoLocalAICoordinator], NumberEntity):
    """Number entity (0-300s) to configure Siren Alarm Duration in seconds."""

    _attr_has_entity_name = True
    _attr_translation_key = "siren_duration"
    _attr_name = "Siren Duration (Thời gian hú còi)"
    _attr_icon = "mdi:timer-alert-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Siren Duration number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_siren_duration"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float:
        """Return current siren duration in seconds."""
        return float(self.coordinator.siren_duration)

    async def async_set_native_value(self, value: float) -> None:
        """Update siren duration in seconds."""
        await self.coordinator.async_set_siren_duration(int(value))


class TapoSpeakerVolumeNumber(CoordinatorEntity[TapoLocalAICoordinator], NumberEntity):
    """Number entity (0-100%) to configure Camera Speaker Volume."""

    _attr_has_entity_name = True
    _attr_translation_key = "speaker_volume"
    _attr_name = "Speaker Volume (Âm lượng loa camera)"
    _attr_icon = "mdi:volume-source"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Speaker Volume number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_speaker_volume"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float:
        """Return current speaker volume (0-100%)."""
        return float(self.coordinator.speaker_volume)

    async def async_set_native_value(self, value: float) -> None:
        """Update speaker volume on the camera."""
        await self.coordinator.async_set_speaker_volume(int(value))


class TapoMicrophoneVolumeNumber(CoordinatorEntity[TapoLocalAICoordinator], NumberEntity):
    """Number entity (0-100%) to configure Camera Microphone Volume."""

    _attr_has_entity_name = True
    _attr_translation_key = "microphone_volume"
    _attr_name = "Microphone Volume (Âm lượng thu Micro)"
    _attr_icon = "mdi:microphone-settings"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Microphone Volume number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_microphone_volume"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float:
        """Return current microphone volume (0-100%)."""
        return float(self.coordinator.microphone_volume)

    async def async_set_native_value(self, value: float) -> None:
        """Update microphone volume on the camera."""
        await self.coordinator.async_set_microphone_volume(int(value))


class TapoPTZMovementAngleNumber(CoordinatorEntity[TapoLocalAICoordinator], NumberEntity):
    """Number entity to configure the step angle (degrees) for PTZ Move Up/Down/Left/Right buttons."""

    _attr_has_entity_name = True
    _attr_name = "Movement Angle (Góc xoay mỗi bước)"
    _attr_icon = "mdi:angle-acute"
    _attr_native_min_value = 5
    _attr_native_max_value = 360
    _attr_native_step = 5
    _attr_native_unit_of_measurement = DEGREE
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Movement Angle number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_movement_angle"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float:
        """Return current step angle in degrees."""
        return float(self.coordinator.ptz_step_angle)

    async def async_set_native_value(self, value: float) -> None:
        """Update the step angle used by PTZ Move buttons."""
        self.coordinator.ptz_step_angle = int(value)
        self.async_write_ha_state()
