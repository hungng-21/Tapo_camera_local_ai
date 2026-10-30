"""The Tapo Camera Local AI integration (v2.0.0 Ultimate Edition with C260 Face Recognition)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import TapoLocalAICoordinator
from .panel import async_sync_panel, async_unregister_panel, has_active_entries
from .websocket import async_setup as async_setup_websocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.EVENT,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SIREN,
]

# Obsolete unique_id suffixes from earlier test builds to auto-remove from Entity Registry
OBSOLETE_NUMBER_SUFFIXES = (
    "_baby_cry_sensitivity",
    "_bark_sensitivity",
    "_meow_sensitivity",
    "_glass_break_sensitivity",
    "_tamper_sensitivity",
    "_siren_volume",
)
OBSOLETE_SELECT_SUFFIXES = (
    "_motion_sensitivity_level",
    "_baby_cry_sensitivity_level",
    "_tamper_sensitivity_level",
)
OBSOLETE_FACE_SUFFIXES = (
    "_face_name",
    "_face_id",
    "_last_seen",
    "_known_faces",
    "_unknown_faces",
    "_unknown_today",
    "_last_unknown_seen",
    "_dedup_skipped",
    "_face_recognized",
    "_stranger_detected",
    "_face_event",
)


def _async_cleanup_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove redundant sensitivity entities and face entities on non-face cameras automatically."""
    ent_reg = er.async_get(hass)
    coordinator: TapoLocalAICoordinator | None = getattr(
        entry, "runtime_data", None
    ) or hass.data.get(DOMAIN, {}).get(entry.entry_id)
    supports_face = (
        getattr(coordinator, "supports_face", False) if coordinator else False
    )

    for ent_entry in list(er.async_entries_for_config_entry(ent_reg, entry.entry_id)):
        uid = ent_entry.unique_id or ""
        if ent_entry.domain == "number" and uid.endswith(OBSOLETE_NUMBER_SUFFIXES):
            _LOGGER.info("Tự động dọn thực thể dư thừa: %s", ent_entry.entity_id)
            ent_reg.async_remove(ent_entry.entity_id)
        elif ent_entry.domain == "select" and uid.endswith(OBSOLETE_SELECT_SUFFIXES):
            _LOGGER.info("Tự động dọn thực thể dư thừa: %s", ent_entry.entity_id)
            ent_reg.async_remove(ent_entry.entity_id)
        elif not supports_face and uid.endswith(OBSOLETE_FACE_SUFFIXES):
            _LOGGER.info(
                "Tự động dọn thực thể khuôn mặt không áp dụng cho camera này: %s",
                ent_entry.entity_id,
            )
            ent_reg.async_remove(ent_entry.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tapo Camera Local AI from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("websocket_registered"):
        async_setup_websocket(hass)
        domain_data["websocket_registered"] = True

    coordinator = TapoLocalAICoordinator(hass, entry)
    entry.runtime_data = coordinator
    domain_data[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    try:
        await coordinator.async_setup()
        # Synchronize sidebar panel AFTER coordinator.async_setup() has detected camera model & supports_face
        await async_sync_panel(hass)
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await coordinator.async_shutdown()
        raise ConfigEntryNotReady(
            f"Không thể kết nối tới camera Tapo tại {entry.data.get('host')}: {err}"
        ) from err

    _async_cleanup_obsolete_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply changed options (Face mappings, polling, sidebar, etc.) live without interrupting streams."""
    if entry.state is not ConfigEntryState.LOADED:
        await async_sync_panel(hass)
        return
    coordinator: TapoLocalAICoordinator | None = getattr(
        entry, "runtime_data", None
    ) or hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None:
        await coordinator.async_apply_options()
    await async_sync_panel(hass)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: TapoLocalAICoordinator | None = getattr(
        entry, "runtime_data", None
    ) or hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None:
        coordinator.async_cancel_timers()
        await coordinator.async_flush()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if coordinator is not None:
            await coordinator.async_shutdown()
        if has_active_entries(hass, exclude_entry_id=entry.entry_id):
            await async_sync_panel(hass, exclude_entry_id=entry.entry_id)
        else:
            async_unregister_panel(hass)
    return unload_ok
