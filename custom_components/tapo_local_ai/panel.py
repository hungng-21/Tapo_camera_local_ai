"""Sidebar panel registration for the Tapo Face Manager."""
from __future__ import annotations

import asyncio
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import (
    CONF_FACES,
    CONF_SHOW_SIDEBAR,
    CONF_SIDEBAR_TITLE,
    DEFAULT_SHOW_SIDEBAR,
    DEFAULT_SIDEBAR_TITLE,
    DOMAIN,
    FACE_MODEL_KEYWORDS,
)

PANEL_PATH = f"/{DOMAIN}_manager"
PANEL_URL = DOMAIN
PANEL_NAME = "tapo-local-ai-face-manager"
PANEL_TITLE = DEFAULT_SIDEBAR_TITLE
PANEL_ICON = "mdi:face-recognition"


def _asset_version(path: Path) -> str:
    """Cache-bust token: changes whenever JS file mtime changes."""
    try:
        return str(int(path.stat().st_mtime))
    except OSError:
        return "200"


_ACTIVE_STATES = (
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_IN_PROGRESS,
    ConfigEntryState.SETUP_RETRY,
)


def entry_supports_face(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Return True if the config entry belongs to a camera that supports Face Recognition."""
    coord = getattr(entry, "runtime_data", None) or hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coord is not None and hasattr(coord, "supports_face"):
        return bool(coord.supports_face)
    if entry.options.get(CONF_FACES):
        return True
    title_up = (entry.title or "").upper()
    return any(kw in title_up for kw in FACE_MODEL_KEYWORDS)


def has_active_entries(hass: HomeAssistant, exclude_entry_id: str | None = None) -> bool:
    """Return True if any camera entry (other than exclude_entry_id) is active."""
    return any(
        entry.entry_id != exclude_entry_id and entry.state in _ACTIVE_STATES
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


def _sidebar_wanted(hass: HomeAssistant, exclude_entry_id: str | None = None) -> bool:
    """Show panel in sidebar ONLY if at least one active camera supports Face AI and has show_sidebar enabled."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id or entry.state not in _ACTIVE_STATES:
            continue
        if not entry.options.get(CONF_SHOW_SIDEBAR, DEFAULT_SHOW_SIDEBAR):
            continue
        if entry_supports_face(hass, entry):
            return True
    return False


def _sidebar_title(hass: HomeAssistant, exclude_entry_id: str | None = None) -> str:
    """Sidebar title: taken from the first active face-capable camera (by title) with custom title set."""
    entries = sorted(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id != exclude_entry_id
            and entry.state in _ACTIVE_STATES
            and entry_supports_face(hass, entry)
        ),
        key=lambda entry: (entry.title, entry.entry_id),
    )
    for entry in entries:
        if not entry.options.get(CONF_SHOW_SIDEBAR, DEFAULT_SHOW_SIDEBAR):
            continue
        title = str(entry.options.get(CONF_SIDEBAR_TITLE) or "").strip()
        if title:
            return title
    return PANEL_TITLE


async def async_sync_panel(
    hass: HomeAssistant, exclude_entry_id: str | None = None
) -> None:
    """Synchronize the Face Manager custom sidebar panel across all configured cameras."""
    data = hass.data.setdefault(DOMAIN, {})
    lock = data.setdefault("panel_lock", asyncio.Lock())
    async with lock:
        await _async_sync_panel_locked(hass, exclude_entry_id)


async def _async_sync_panel_locked(
    hass: HomeAssistant, exclude_entry_id: str | None = None
) -> None:
    """Register static path and sync sidebar visibility."""
    data = hass.data.setdefault(DOMAIN, {})
    show = _sidebar_wanted(hass, exclude_entry_id)
    title = _sidebar_title(hass, exclude_entry_id)

    # If no camera wants the panel and it was never registered, do nothing
    if not show and not data.get("panel_registered"):
        return

    if (
        data.get("panel_registered")
        and data.get("panel_sidebar") == show
        and data.get("panel_title") == title
    ):
        return

    www_path = Path(__file__).parent / "frontend"
    if not data.get("static_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_PATH, str(www_path), cache_headers=False)]
        )
        data["static_registered"] = True

    js_version = await hass.async_add_executor_job(
        _asset_version, www_path / "face-manager.js"
    )

    if data.get("panel_registered"):
        frontend.async_remove_panel(hass, PANEL_URL)
        data["panel_registered"] = False

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_NAME,
        frontend_url_path=PANEL_URL,
        module_url=f"{PANEL_PATH}/face-manager.js?v={js_version}",
        sidebar_title=title if show else None,
        sidebar_icon=PANEL_ICON if show else None,
        require_admin=True,
        embed_iframe=False,
        config={},
    )
    data["panel_registered"] = True
    data["panel_sidebar"] = show
    data["panel_title"] = title


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the Face Manager sidebar panel."""
    data = hass.data.get(DOMAIN, {})
    if data.get("panel_registered"):
        frontend.async_remove_panel(hass, PANEL_URL)
        data["panel_registered"] = False
        data["panel_sidebar"] = None
