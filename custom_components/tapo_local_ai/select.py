"""Select platform for Tapo Camera Local AI (Sound/Tamper 3-Level Sensitivity, Night Vision, Light Frequency, Alarm Mode, Siren Volume, PTZ)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AI_SENSITIVITY_SPECS,
    ALARM_MODE_OPTIONS,
    DOMAIN,
    LIGHT_FREQUENCY_OPTIONS,
    NIGHT_VISION_OPTIONS,
    SENSITIVITY_3LEVEL_OPTIONS,
    SIREN_VOLUME_LEVEL_OPTIONS,
    TapoSensitivitySpec,
)
from .coordinator import TapoLocalAICoordinator

PATROL_OPTIONS = ["Off", "Horizontal", "Vertical"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo Select entities for image processing, alarm, 3-level sound/tamper sensitivity, and PTZ."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SelectEntity] = [
        TapoNightVisionModeSelect(coordinator),
        TapoLightFrequencySelect(coordinator),
        TapoAlarmModeSelect(coordinator),
        TapoSirenVolumeLevelSelect(coordinator),
    ]

    # Add 3-level sensitivity selects ONLY for 3-level modules (Baby Cry, Bark, Meow, Glass Break, Tamper)
    for spec in AI_SENSITIVITY_SPECS:
        if spec.control_type == "select_3":
            entities.append(TapoSensitivity3LevelSelect(coordinator, spec))

    # Add PTZ selects only if camera supports PTZ motor
    if coordinator.supports_ptz:
        entities.extend(
            [
                TapoPresetSelect(coordinator),
                TapoPatrolModeSelect(coordinator),
            ]
        )

    async_add_entities(entities)


class TapoNightVisionModeSelect(CoordinatorEntity[TapoLocalAICoordinator], SelectEntity):
    """Select entity to switch Night Vision Mode (Infrared / Full-Color / Smart)."""

    _attr_has_entity_name = True
    _attr_translation_key = "night_vision_mode"
    _attr_name = "Night Vision Mode (Chế độ nhìn đêm)"
    _attr_icon = "mdi:weather-night"
    _attr_options = NIGHT_VISION_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Night Vision Mode select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_night_vision_mode"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str:
        """Return the active night vision mode."""
        return self.coordinator.night_vision_mode

    async def async_select_option(self, option: str) -> None:
        """Change the active night vision mode."""
        await self.coordinator.async_set_night_vision_mode(option)


class TapoLightFrequencySelect(CoordinatorEntity[TapoLocalAICoordinator], SelectEntity):
    """Select entity to configure Light Frequency anti-flicker (Auto / 50Hz / 60Hz)."""

    _attr_has_entity_name = True
    _attr_translation_key = "light_frequency"
    _attr_name = "Light Frequency (Tần số chống nháy đèn)"
    _attr_icon = "mdi:sine-wave"
    _attr_options = LIGHT_FREQUENCY_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Light Frequency select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_light_frequency"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str:
        """Return the active light frequency setting."""
        return self.coordinator.light_frequency

    async def async_select_option(self, option: str) -> None:
        """Change the active light frequency setting."""
        await self.coordinator.async_set_light_frequency(option)


class TapoAlarmModeSelect(CoordinatorEntity[TapoLocalAICoordinator], SelectEntity):
    """Select entity to configure Siren Alarm Mode (sound / light / both)."""

    _attr_has_entity_name = True
    _attr_translation_key = "alarm_mode"
    _attr_name = "Alarm Mode (Kiểu báo động Còi/Đèn)"
    _attr_icon = "mdi:alarm-light"
    _attr_options = ALARM_MODE_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Alarm Mode select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_alarm_mode"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str:
        """Return the active alarm mode."""
        return self.coordinator.alarm_mode

    async def async_select_option(self, option: str) -> None:
        """Change the active alarm mode."""
        await self.coordinator.async_set_alarm_mode(option)


class TapoSirenVolumeLevelSelect(CoordinatorEntity[TapoLocalAICoordinator], SelectEntity):
    """Select entity to configure Siren Volume Level (low / normal / high)."""

    _attr_has_entity_name = True
    _attr_translation_key = "siren_volume_level"
    _attr_name = "Siren Volume Level (Mức âm lượng còi)"
    _attr_icon = "mdi:bullhorn"
    _attr_options = SIREN_VOLUME_LEVEL_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Siren Volume Level select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_siren_volume_level"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str:
        """Return the active siren volume level."""
        return self.coordinator.siren_volume_level

    async def async_select_option(self, option: str) -> None:
        """Change the active siren volume level."""
        await self.coordinator.async_set_siren_volume_level(option)


class TapoSensitivity3LevelSelect(CoordinatorEntity[TapoLocalAICoordinator], SelectEntity):
    """Select entity to configure 3-level sensitivity (low / normal / high) for Sound AI & Tamper detections."""

    _attr_has_entity_name = True
    _attr_options = SENSITIVITY_3LEVEL_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: TapoLocalAICoordinator,
        spec: TapoSensitivitySpec,
    ) -> None:
        """Initialize the 3-level sensitivity select entity."""
        super().__init__(coordinator)
        self.spec = spec
        self._attr_unique_id = f"{coordinator.serial_number}_{spec.key}"
        self._attr_translation_key = spec.key
        self._attr_name = spec.name_vi
        self._attr_icon = spec.icon
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str:
        """Return current 3-level sensitivity ('low', 'normal', 'high')."""
        if not self.coordinator.data:
            return "normal"
        return str(
            self.coordinator.data.get("sensitivity_3", {}).get(self.spec.key, "normal")
        )

    async def async_select_option(self, option: str) -> None:
        """Update 3-level sensitivity on the camera."""
        await self.coordinator.async_set_sensitivity_3(self.spec, option)


class TapoPresetSelect(CoordinatorEntity[TapoLocalAICoordinator], SelectEntity):
    """Select entity to move a PTZ Tapo camera to a saved preset."""

    _attr_has_entity_name = True
    _attr_name = "Move to Preset (Điểm nhớ góc quay)"
    _attr_icon = "mdi:arrow-decision"

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Move to Preset select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_move_to_preset"
        self._attr_device_info = coordinator.device_info
        self._last_selected: str | None = None

    @property
    def available(self) -> bool:
        """Return True if at least one preset is configured on the camera."""
        return bool(self.coordinator.presets)

    @property
    def options(self) -> list[str]:
        """Return list of saved preset names."""
        if not self.coordinator.presets:
            return []
        return list(self.coordinator.presets.values())

    @property
    def current_option(self) -> str | None:
        """Return the most recently selected preset."""
        opts = self.options
        if self._last_selected in opts:
            return self._last_selected
        return opts[0] if opts else None

    async def async_select_option(self, option: str) -> None:
        """Move camera to the chosen preset."""
        self._last_selected = option
        await self.coordinator.async_goto_preset(option)
        self.async_write_ha_state()


class TapoPatrolModeSelect(CoordinatorEntity[TapoLocalAICoordinator], SelectEntity):
    """Select entity to control PTZ Patrol Mode (Horizontal / Vertical / Off)."""

    _attr_has_entity_name = True
    _attr_name = "Patrol Mode (Chế độ tuần tra)"
    _attr_icon = "mdi:swap-horizontal"
    _attr_options = PATROL_OPTIONS

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        """Initialize the Patrol Mode select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_patrol_mode"
        self._attr_device_info = coordinator.device_info

    @property
    def current_option(self) -> str:
        """Return the active patrol mode."""
        return self.coordinator.patrol_mode

    async def async_select_option(self, option: str) -> None:
        """Change the active patrol mode."""
        await self.coordinator.async_set_patrol_mode(option)
