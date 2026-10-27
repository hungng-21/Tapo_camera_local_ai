"""Switch platform to toggle Tapo Camera AI detections (Baby Cry, Bark, Person, Privacy, LED, etc.)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AI_DETECTION_SWITCHES, DOMAIN, TapoAISwitchSpec
from .coordinator import TapoLocalAICoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo AI configuration switches supported by the camera."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TapoAIDetectionSwitch(coordinator, spec)
        for spec in AI_DETECTION_SWITCHES
        if (not spec.ptz_only) or coordinator.supports_ptz
    ]
    async_add_entities(entities)


class TapoAIDetectionSwitch(CoordinatorEntity[TapoLocalAICoordinator], SwitchEntity):
    """Switch entity to enable/disable on-device AI detections and controls on Tapo camera."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: TapoLocalAICoordinator,
        spec: TapoAISwitchSpec,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.spec = spec
        self._attr_unique_id = f"{coordinator.serial_number}_{spec.key}"
        self._attr_name = spec.name_vi
        self._attr_icon = spec.icon
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return True if the AI detection setting is enabled on the camera."""
        if not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get("switches", {}).get(self.spec.key, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable this AI detection on the camera."""
        await self.coordinator.async_set_ai_switch(self.spec, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable this AI detection on the camera."""
        await self.coordinator.async_set_ai_switch(self.spec, False)
