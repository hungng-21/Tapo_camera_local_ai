"""Base entity classes for Tapo Camera Local AI & Face Recognition."""
from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TapoLocalAICoordinator


class TapoC260Entity(CoordinatorEntity[TapoLocalAICoordinator]):
    """Base entity attached to the unified Tapo Camera Local AI device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TapoLocalAICoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info


class TapoC260HealthEntity(TapoC260Entity):
    """Diagnostic health entity: always available even during polling errors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return True
