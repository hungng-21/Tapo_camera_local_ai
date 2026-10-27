"""Camera platform for Tapo Camera Local AI (Local RTSP HD/SD streams & PTZ services)."""
from __future__ import annotations

import logging
from urllib.parse import quote

import voluptuous as vol

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TapoLocalAICoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_PTZ_MOVE = "ptz_move"
SERVICE_PTZ_PRESET = "ptz_goto_preset"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tapo Local RTSP cameras (HD stream1 and SD stream2)."""
    coordinator: TapoLocalAICoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TapoLocalRTSPCamera(coordinator, stream_id="stream1", label="HD Stream"),
            TapoLocalRTSPCamera(coordinator, stream_id="stream2", label="SD Stream"),
        ]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PTZ_MOVE,
        {
            vol.Required("pan", default=0): vol.All(vol.Coerce(int), vol.Range(min=-360, max=360)),
            vol.Required("tilt", default=0): vol.All(vol.Coerce(int), vol.Range(min=-90, max=90)),
        },
        "async_ptz_move",
    )
    platform.async_register_entity_service(
        SERVICE_PTZ_PRESET,
        {
            vol.Required("preset_id"): cv.string,
        },
        "async_ptz_goto_preset",
    )


class TapoLocalRTSPCamera(CoordinatorEntity[TapoLocalAICoordinator], Camera):
    """Local RTSP Camera entity for TP-Link Tapo camera."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: TapoLocalAICoordinator,
        stream_id: str,
        label: str,
    ) -> None:
        """Initialize the camera entity."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._stream_id = stream_id
        self._attr_unique_id = f"{coordinator.serial_number}_{stream_id}"
        self._attr_name = label
        self._attr_device_info = coordinator.device_info

    def _build_rtsp_url(self) -> str:
        """Construct authenticated local RTSP stream URL."""
        user_enc = quote(self.coordinator.username, safe="")
        pass_enc = quote(self.coordinator.password, safe="")
        return (
            f"rtsp://{user_enc}:{pass_enc}@"
            f"{self.coordinator.host}:{self.coordinator.rtsp_port}/{self._stream_id}"
        )

    async def stream_source(self) -> str | None:
        """Return the RTSP stream source for Home Assistant stream component."""
        return self._build_rtsp_url()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image frame extracted from the local RTSP stream via FFmpeg."""
        return await ffmpeg.async_get_image(
            self.hass,
            self._build_rtsp_url(),
            width=width,
            height=height,
        )

    async def async_ptz_move(self, pan: int, tilt: int) -> None:
        """Move camera motor by relative pan/tilt degrees."""
        await self.coordinator.async_ptz_move(pan, tilt)

    async def async_ptz_goto_preset(self, preset_id: str) -> None:
        """Move camera to a saved PTZ preset."""
        await self.coordinator.async_goto_preset(preset_id)
