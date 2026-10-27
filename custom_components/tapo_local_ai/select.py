"""Select platform for Tapo Camera Local AI (Move to Preset & Patrol Mode for PTZ cameras)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TapoLocalAICoordinator

PATROL_OPTIONS = ["Off", "Horizontal", "Vertical"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PTZ Select entities (Move to Preset & Patrol Mode) if camera supports PTZ."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.supports_ptz:
        return

    async_add_entities(
        [
            TapoPresetSelect(coordinator),
            TapoPatrolModeSelect(coordinator),
        ]
    )


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
