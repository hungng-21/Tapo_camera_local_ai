"""Button platform for Tapo Camera Local AI (PTZ Move Up/Down/Left/Right, Calibrate, Alarm, Reboot)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Coroutine, Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TapoLocalAICoordinator


@dataclass(frozen=True)
class TapoButtonSpec:
    """Specification for a Tapo control button."""

    key: str
    name: str
    icon: str
    ptz_only: bool
    action_fn: Callable[[TapoLocalAICoordinator], Coroutine[Any, Any, None]]


BUTTON_SPECS: tuple[TapoButtonSpec, ...] = (
    TapoButtonSpec(
        key="ptz_move_up",
        name="Move Up (Quay lên)",
        icon="mdi:arrow-up",
        ptz_only=True,
        action_fn=lambda coord: coord.async_ptz_step_direction("UP"),
    ),
    TapoButtonSpec(
        key="ptz_move_down",
        name="Move Down (Quay xuống)",
        icon="mdi:arrow-down",
        ptz_only=True,
        action_fn=lambda coord: coord.async_ptz_step_direction("DOWN"),
    ),
    TapoButtonSpec(
        key="ptz_move_left",
        name="Move Left (Quay trái)",
        icon="mdi:arrow-left",
        ptz_only=True,
        action_fn=lambda coord: coord.async_ptz_step_direction("LEFT"),
    ),
    TapoButtonSpec(
        key="ptz_move_right",
        name="Move Right (Quay phải)",
        icon="mdi:arrow-right",
        ptz_only=True,
        action_fn=lambda coord: coord.async_ptz_step_direction("RIGHT"),
    ),
    TapoButtonSpec(
        key="ptz_calibrate",
        name="Calibrate (Hiệu chuẩn xoay)",
        icon="mdi:gesture-tap-button",
        ptz_only=True,
        action_fn=lambda coord: coord.async_calibrate_motor(),
    ),
    TapoButtonSpec(
        key="manual_alarm_start",
        name="Manual Alarm Start (Bật còi hú)",
        icon="mdi:alarm-light-outline",
        ptz_only=False,
        action_fn=lambda coord: coord.async_set_manual_alarm(True),
    ),
    TapoButtonSpec(
        key="manual_alarm_stop",
        name="Manual Alarm Stop (Tắt còi hú)",
        icon="mdi:alarm-light-off-outline",
        ptz_only=False,
        action_fn=lambda coord: coord.async_set_manual_alarm(False),
    ),
    TapoButtonSpec(
        key="reboot_camera",
        name="Reboot (Khởi động lại Camera)",
        icon="mdi:restart",
        ptz_only=False,
        action_fn=lambda coord: coord.async_reboot_camera(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo PTZ and control buttons from a config entry."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        TapoControlButton(coordinator, spec)
        for spec in BUTTON_SPECS
        if (not spec.ptz_only) or coordinator.supports_ptz
    ]
    async_add_entities(entities)


class TapoControlButton(CoordinatorEntity[TapoLocalAICoordinator], ButtonEntity):
    """Button entity for PTZ movement, calibration, manual alarm, and reboot."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TapoLocalAICoordinator,
        spec: TapoButtonSpec,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        self.spec = spec
        self._attr_unique_id = f"{coordinator.serial_number}_{spec.key}"
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Execute the button action."""
        await self.spec.action_fn(self.coordinator)
