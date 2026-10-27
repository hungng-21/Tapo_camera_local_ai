"""The Tapo Camera Local AI integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import TapoLocalAICoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.BINARY_SENSOR,
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


def _async_cleanup_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove redundant sensitivity entities from the entity registry automatically."""
    ent_reg = er.async_get(hass)
    for ent_entry in list(er.async_entries_for_config_entry(ent_reg, entry.entry_id)):
        uid = ent_entry.unique_id or ""
        if ent_entry.domain == "number" and uid.endswith(OBSOLETE_NUMBER_SUFFIXES):
            _LOGGER.info("Tự động dọn thực thể dư thừa: %s", ent_entry.entity_id)
            ent_reg.async_remove(ent_entry.entity_id)
        elif ent_entry.domain == "select" and uid.endswith(OBSOLETE_SELECT_SUFFIXES):
            _LOGGER.info("Tự động dọn thực thể dư thừa: %s", ent_entry.entity_id)
            ent_reg.async_remove(ent_entry.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tapo Camera Local AI from a config entry."""
    coordinator = TapoLocalAICoordinator(hass, entry)

    try:
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await coordinator.async_shutdown()
        raise ConfigEntryNotReady(
            f"Không thể kết nối tới camera Tapo tại {entry.data.get('host')}: {err}"
        ) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    _async_cleanup_obsolete_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: TapoLocalAICoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
