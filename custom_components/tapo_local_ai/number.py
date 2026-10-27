"""Number platform for Tapo Camera Local AI (PTZ Movement Angle step in degrees)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, EntityCategory
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
    """Set up PTZ Movement Angle number entity if camera supports PTZ."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.supports_ptz:
        return

    async_add_entities([TapoPTZMovementAngleNumber(coordinator)])


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
