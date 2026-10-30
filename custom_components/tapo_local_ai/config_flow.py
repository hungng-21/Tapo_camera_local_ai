"""Config flow and Options flow for Tapo Camera Local AI integration (v2.0.0 Ultimate Edition)."""
from __future__ import annotations

from collections.abc import Mapping
import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TapoC260Api
from .const import (
    CONF_CLOUD_PASSWORD,
    CONF_CONTROL_PORT,
    CONF_DEDUP_SECONDS,
    CONF_ENABLE_ONVIF,
    CONF_FACES,
    CONF_HISTORY_SECONDS,
    CONF_HOLD_SECONDS,
    CONF_MAX_UNKNOWN_FACES,
    CONF_ONVIF_PORT,
    CONF_POLL_INTERVAL,
    CONF_RETENTION_DAYS,
    CONF_RTSP_PORT,
    CONF_SHOW_SIDEBAR,
    CONF_SIDEBAR_TITLE,
    CONF_STRANGER_CLEAR_SECONDS,
    DEFAULT_CONTROL_PORT,
    DEFAULT_DEDUP_SECONDS,
    DEFAULT_ENABLE_ONVIF,
    DEFAULT_HISTORY_SECONDS,
    DEFAULT_HOLD_SECONDS,
    DEFAULT_MAX_UNKNOWN_FACES,
    DEFAULT_ONVIF_PORT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_RTSP_PORT,
    DEFAULT_SHOW_SIDEBAR,
    DEFAULT_STRANGER_CLEAR_SECONDS,
    DOMAIN,
    MAX_MAX_UNKNOWN_FACES,
    MAX_RETENTION_DAYS,
    MAX_SIDEBAR_TITLE_LEN,
    MAX_STRANGER_CLEAR_SECONDS,
    MIN_MAX_UNKNOWN_FACES,
    MIN_RETENTION_DAYS,
    MIN_STRANGER_CLEAR_SECONDS,
)
from .coordinator import (
    check_tcp_port,
    connect_tapo_multi_auth,
    parse_tapo_basic_info,
)
from .panel import entry_supports_face

_LOGGER = logging.getLogger(__name__)


def _try_pytapo_sync(data: dict[str, Any]) -> dict[str, Any]:
    """Try validating camera via pytapo multi-auth on port 443."""
    host = data[CONF_HOST].strip()
    username = data[CONF_USERNAME].strip()
    password = data.get(CONF_PASSWORD, "")
    cloud_password = data.get(CONF_CLOUD_PASSWORD, "").strip()
    control_port = int(data.get(CONF_CONTROL_PORT, DEFAULT_CONTROL_PORT))

    _, basic = connect_tapo_multi_auth(
        host, username, password, cloud_password, control_port
    )
    meta = parse_tapo_basic_info(basic, host)
    return {
        "serial": meta["serial"],
        "title": meta["alias"],
        "model": meta["model"],
        "mode": "full_local_api",
    }


def _check_ports_sync(data: dict[str, Any]) -> tuple[bool, bool]:
    """Check if ONVIF or RTSP TCP ports are open."""
    host = data[CONF_HOST].strip()
    onvif_port = int(data.get(CONF_ONVIF_PORT, DEFAULT_ONVIF_PORT))
    rtsp_port = int(data.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT))
    return (
        check_tcp_port(host, onvif_port, timeout=3.0),
        check_tcp_port(host, rtsp_port, timeout=3.0),
    )


async def _async_validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate camera connection using pytapo multi-auth -> C260 Secure Channel -> ONVIF/RTSP fallback."""
    host = data[CONF_HOST].strip()
    username = data[CONF_USERNAME].strip()
    password = data.get(CONF_PASSWORD, "")
    cloud_password = data.get(CONF_CLOUD_PASSWORD, "").strip()
    control_port = int(data.get(CONF_CONTROL_PORT, DEFAULT_CONTROL_PORT))
    onvif_port = int(data.get(CONF_ONVIF_PORT, DEFAULT_ONVIF_PORT))
    rtsp_port = int(data.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT))

    # 1. Primary: pytapo multi-auth
    try:
        return await hass.async_add_executor_job(_try_pytapo_sync, data)
    except Exception as tapo_err:
        _LOGGER.debug(
            "Kết nối pytapo cổng %s tới %s chưa thành công (%s); thử C260 Secure Channel / ONVIF / RTSP...",
            control_port,
            host,
            tapo_err,
        )

    # 2. Secondary: TapoC260Api direct challenge/login (encrypt_type 3)
    c260_secret = cloud_password or password
    if c260_secret:
        try:
            session = async_get_clientsession(hass)
            c260_api = TapoC260Api(session, host, username, c260_secret, hass=hass)
            await c260_api.async_login()
            title = f"Tapo C260 ({host})"
            serial = f"tapo_c260_{host.replace('.', '_')}"
            try:
                dev_resp = await c260_api.async_secure_request(
                    {
                        "method": "multipleRequest",
                        "params": {
                            "requests": [
                                {
                                    "method": "getDeviceInfo",
                                    "params": {"device_info": {"name": ["basic_info"]}},
                                }
                            ]
                        },
                    }
                )
                basic_raw = (
                    dev_resp.get("result", {})
                    .get("responses", [{}])[0]
                    .get("result", {})
                )
                if isinstance(basic_raw, dict) and basic_raw:
                    meta = parse_tapo_basic_info(basic_raw, host)
                    serial = meta["serial"]
                    title = meta["alias"]
            except Exception:
                pass
            return {
                "serial": serial,
                "title": title,
                "model": "Tapo C260",
                "mode": "c260_secure_api",
            }
        except Exception as c260_err:
            _LOGGER.debug("C260 Secure Channel tới %s thất bại: %s", host, c260_err)

    # 3. Tertiary: ONVIF / RTSP port fallback
    onvif_open, rtsp_open = await hass.async_add_executor_job(_check_ports_sync, data)
    if onvif_open or rtsp_open:
        info: dict[str, Any] = {
            "serial": f"tapo_{host.replace('.', '_')}",
            "title": f"Tapo {username} ({host})",
            "mode": "onvif_rtsp_fallback",
            "onvif_open": onvif_open,
        }
        if onvif_open:
            try:
                import onvif
                from onvif import ONVIFCamera

                wsdl_dir = f"{os.path.dirname(onvif.__file__)}/wsdl/"
                cam = ONVIFCamera(
                    host,
                    onvif_port,
                    username,
                    password or cloud_password,
                    wsdl_dir,
                    no_cache=True,
                )
                await cam.update_xaddrs()
                dev_mgmt = await cam.create_devicemgmt_service()
                dev_info = await dev_mgmt.GetDeviceInformation()
                serial = getattr(dev_info, "SerialNumber", None)
                model = getattr(dev_info, "Model", None)
                if serial:
                    info["serial"] = str(serial)
                if model:
                    info["title"] = f"{model} ({host})"
                    info["model"] = str(model)
                await cam.close()
            except Exception as onvif_err:
                _LOGGER.debug(
                    "Không đọc được GetDeviceInformation qua ONVIF: %s", onvif_err
                )
        return info

    raise ConnectionError(
        f"Không thể kết nối tới {host} trên cả cổng {control_port}, {onvif_port} và {rtsp_port}."
    )


def _build_full_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the configuration schema pre-filled with existing or default values."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Optional(
                CONF_CLOUD_PASSWORD, default=defaults.get(CONF_CLOUD_PASSWORD, "")
            ): str,
            vol.Optional(
                CONF_CONTROL_PORT,
                default=defaults.get(CONF_CONTROL_PORT, DEFAULT_CONTROL_PORT),
            ): int,
            vol.Optional(
                CONF_ONVIF_PORT,
                default=defaults.get(CONF_ONVIF_PORT, DEFAULT_ONVIF_PORT),
            ): int,
            vol.Optional(
                CONF_RTSP_PORT,
                default=defaults.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT),
            ): int,
            vol.Optional(
                CONF_POLL_INTERVAL,
                default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
            vol.Optional(
                CONF_HOLD_SECONDS,
                default=defaults.get(CONF_HOLD_SECONDS, DEFAULT_HOLD_SECONDS),
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=300)),
            vol.Optional(
                CONF_ENABLE_ONVIF,
                default=defaults.get(CONF_ENABLE_ONVIF, DEFAULT_ENABLE_ONVIF),
            ): bool,
        }
    )


class TapoLocalAIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tapo Camera Local AI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step configured by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _async_validate_connection(self.hass, user_input)
            except Exception as err:
                _LOGGER.error(
                    "Không thể kết nối camera Tapo %s: %s",
                    user_input.get(CONF_HOST),
                    err,
                )
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["serial"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    options={
                        CONF_POLL_INTERVAL: user_input.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                        CONF_HOLD_SECONDS: user_input.get(
                            CONF_HOLD_SECONDS, DEFAULT_HOLD_SECONDS
                        ),
                        CONF_ENABLE_ONVIF: user_input.get(
                            CONF_ENABLE_ONVIF, DEFAULT_ENABLE_ONVIF
                        ),
                        CONF_HISTORY_SECONDS: DEFAULT_HISTORY_SECONDS,
                        CONF_DEDUP_SECONDS: DEFAULT_DEDUP_SECONDS,
                        CONF_STRANGER_CLEAR_SECONDS: DEFAULT_STRANGER_CLEAR_SECONDS,
                        CONF_RETENTION_DAYS: DEFAULT_RETENTION_DAYS,
                        CONF_MAX_UNKNOWN_FACES: DEFAULT_MAX_UNKNOWN_FACES,
                        CONF_SHOW_SIDEBAR: DEFAULT_SHOW_SIDEBAR,
                        CONF_FACES: {},
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_full_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of an existing camera entry."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _async_validate_connection(self.hass, user_input)
            except Exception as err:
                _LOGGER.error(
                    "Lỗi khi cấu hình lại camera Tapo %s: %s",
                    user_input.get(CONF_HOST),
                    err,
                )
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **user_input},
                    options={
                        **entry.options,
                        CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                        CONF_HOLD_SECONDS: user_input[CONF_HOLD_SECONDS],
                        CONF_ENABLE_ONVIF: user_input[CONF_ENABLE_ONVIF],
                    },
                    reason="reconfigure_successful",
                )

        current = {**entry.data, **entry.options}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_full_schema(current),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Handle reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauthentication credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            merged = {**entry.data, **user_input}
            try:
                await _async_validate_connection(self.hass, merged)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(
                            CONF_USERNAME, entry.data.get(CONF_USERNAME, "")
                        ),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=(user_input or {}).get(
                            CONF_PASSWORD, entry.data.get(CONF_PASSWORD, "")
                        ),
                    ): str,
                    vol.Optional(
                        CONF_CLOUD_PASSWORD,
                        default=(user_input or {}).get(
                            CONF_CLOUD_PASSWORD, entry.data.get(CONF_CLOUD_PASSWORD, "")
                        ),
                    ): str,
                }
            ),
            description_placeholders={"host": entry.data.get(CONF_HOST, "")},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow (compatible with Home Assistant 2025/2026+)."""
        return TapoLocalAIOptionsFlowHandler()


class TapoLocalAIOptionsFlowHandler(config_entries.OptionsFlow):
    """Unified Options Flow: opens Connection settings directly on standard cameras, or full Face Management menu on Face AI cameras."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show management menu for Face AI cameras, or go straight to connection form for standard cameras."""
        if not entry_supports_face(self.hass, self.config_entry):
            return await self.async_step_connection(user_input)

        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "connection",
                "faces",
                "unknown_faces",
                "add_face",
                "add_unknown",
                "edit_face",
                "delete_face",
                "polling",
                "retention",
                "sidebar",
            ],
        )

    def _get_coordinator(self):
        return getattr(self.config_entry, "runtime_data", None) or self.hass.data.get(
            DOMAIN, {}
        ).get(self.config_entry.entry_id)

    def _faces(self) -> dict[str, str]:
        faces = self.config_entry.options.get(CONF_FACES, {})
        return (
            {str(k): str(v) for k, v in faces.items()}
            if isinstance(faces, dict)
            else {}
        )

    def _unknown_faces(self) -> dict[str, dict[str, Any]]:
        coordinator = self._get_coordinator()
        if coordinator is None:
            return {}
        return dict(getattr(coordinator, "unknown_faces", {}))

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage camera connection credentials, ports, and ONVIF settings."""
        errors: dict[str, str] = {}
        entry = self.config_entry

        if user_input is not None:
            try:
                await _async_validate_connection(self.hass, user_input)
            except Exception as err:
                _LOGGER.error(
                    "Lỗi kết nối khi lưu cấu hình camera Tapo %s: %s",
                    user_input.get(CONF_HOST),
                    err,
                )
                errors["base"] = "cannot_connect"
            else:
                creds_changed = any(
                    entry.data.get(k) != user_input.get(k)
                    for k in (
                        CONF_HOST,
                        CONF_USERNAME,
                        CONF_PASSWORD,
                        CONF_CLOUD_PASSWORD,
                        CONF_CONTROL_PORT,
                        CONF_ONVIF_PORT,
                        CONF_RTSP_PORT,
                    )
                )
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, **user_input},
                )
                new_options = {
                    **entry.options,
                    CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                    CONF_HOLD_SECONDS: user_input[CONF_HOLD_SECONDS],
                    CONF_ENABLE_ONVIF: user_input[CONF_ENABLE_ONVIF],
                }
                result = self.async_create_entry(title="", data=new_options)
                if creds_changed:
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                return result

        current = {**entry.data, **entry.options}
        return self.async_show_form(
            step_id="connection",
            data_schema=_build_full_schema(current),
            errors=errors,
        )

    async def async_step_faces(self, user_input=None) -> FlowResult:
        """Show configured faces."""
        faces = self._faces()
        lines = [f"{face_id} → {name}" for face_id, name in sorted(faces.items())]
        return self.async_show_form(
            step_id="faces",
            data_schema=vol.Schema({}),
            description_placeholders={
                "faces": "\n".join(lines) if lines else "Chưa có Face ID nào.",
            },
        )

    async def async_step_unknown_faces(self, user_input=None) -> FlowResult:
        """Show Face IDs discovered but not yet named."""
        unknown = self._unknown_faces()
        lines = []
        for face_id, item in sorted(
            unknown.items(),
            key=lambda x: x[1].get("last_seen", ""),
            reverse=True,
        ):
            lines.append(
                f"{face_id} — lần cuối: {item.get('last_seen', '?')} — "
                f"{item.get('count', 0)} lần"
            )
        return self.async_show_form(
            step_id="unknown_faces",
            data_schema=vol.Schema({}),
            description_placeholders={
                "unknown_faces": (
                    "\n".join(lines) if lines else "Chưa phát hiện Face ID lạ."
                ),
            },
        )

    async def async_step_add_face(self, user_input=None) -> FlowResult:
        """Add a Face ID/name mapping."""
        errors = {}
        faces = self._faces()
        if user_input is not None:
            face_id = str(user_input["face_id"]).strip()
            name = str(user_input["name"]).strip()
            if not face_id.isdigit():
                errors["face_id"] = "invalid_face_id"
            elif not name:
                errors["name"] = "invalid_name"
            elif face_id in faces:
                errors["face_id"] = "face_id_exists"
            else:
                faces[face_id] = name
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.options, CONF_FACES: faces},
                )
        return self.async_show_form(
            step_id="add_face",
            data_schema=vol.Schema(
                {
                    vol.Required("face_id"): str,
                    vol.Required("name"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_add_unknown(self, user_input=None) -> FlowResult:
        """Add a discovered unknown Face ID directly to known faces."""
        unknown = self._unknown_faces()
        faces = self._faces()
        if not unknown:
            return self.async_abort(reason="no_unknown_faces")

        errors = {}
        if user_input is not None:
            face_id = str(user_input["face_id"])
            name = str(user_input["name"]).strip()
            if face_id in faces:
                errors["face_id"] = "face_id_exists"
            elif not name:
                errors["name"] = "invalid_name"
            else:
                faces[face_id] = name
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.options, CONF_FACES: faces},
                )

        options = [
            {"value": face_id, "label": face_id} for face_id in sorted(unknown)
        ]
        first_id = next(iter(sorted(unknown)))
        return self.async_show_form(
            step_id="add_unknown",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "face_id", default=first_id
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("name"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_edit_face(self, user_input=None) -> FlowResult:
        """Edit an existing mapping."""
        faces = self._faces()
        if not faces:
            return self.async_abort(reason="no_faces")
        errors = {}
        first_id = next(iter(faces))
        if user_input is not None:
            old_id = str(user_input["old_face_id"])
            new_id = str(user_input["new_face_id"]).strip()
            name = str(user_input["name"]).strip()
            if not new_id.isdigit():
                errors["new_face_id"] = "invalid_face_id"
            elif not name:
                errors["name"] = "invalid_name"
            elif new_id != old_id and new_id in faces:
                errors["new_face_id"] = "face_id_exists"
            else:
                if new_id != old_id:
                    coordinator = self._get_coordinator()
                    if coordinator is not None:
                        await coordinator.async_merge_face_history(old_id, new_id)
                faces.pop(old_id, None)
                faces[new_id] = name
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.options, CONF_FACES: faces},
                )
        return self.async_show_form(
            step_id="edit_face",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "old_face_id", default=first_id
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(faces),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("new_face_id", default=first_id): str,
                    vol.Required("name", default=faces[first_id]): str,
                }
            ),
            errors=errors,
        )

    async def async_step_delete_face(self, user_input=None) -> FlowResult:
        """Delete a mapping."""
        faces = self._faces()
        if not faces:
            return self.async_abort(reason="no_faces")
        if user_input is not None:
            face_id = str(user_input["face_id"])
            faces.pop(face_id, None)
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_FACES: faces},
            )
        return self.async_show_form(
            step_id="delete_face",
            data_schema=vol.Schema(
                {
                    vol.Required("face_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(faces),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_sidebar(self, user_input=None) -> FlowResult:
        """Toggle Face Manager sidebar visibility and title."""
        current = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **current,
                    CONF_SHOW_SIDEBAR: bool(user_input[CONF_SHOW_SIDEBAR]),
                    CONF_SIDEBAR_TITLE: str(
                        user_input.get(CONF_SIDEBAR_TITLE, "")
                    ).strip(),
                },
            )
        return self.async_show_form(
            step_id="sidebar",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SHOW_SIDEBAR,
                        default=current.get(CONF_SHOW_SIDEBAR, DEFAULT_SHOW_SIDEBAR),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_SIDEBAR_TITLE,
                        description={
                            "suggested_value": current.get(CONF_SIDEBAR_TITLE, "")
                        },
                    ): vol.All(str, vol.Length(max=MAX_SIDEBAR_TITLE_LEN)),
                }
            ),
        )

    async def async_step_retention(self, user_input=None) -> FlowResult:
        """Configure storage retention days and max unknown faces."""
        current = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **current,
                    CONF_RETENTION_DAYS: int(user_input[CONF_RETENTION_DAYS]),
                    CONF_MAX_UNKNOWN_FACES: int(user_input[CONF_MAX_UNKNOWN_FACES]),
                },
            )
        return self.async_show_form(
            step_id="retention",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RETENTION_DAYS,
                        default=current.get(
                            CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_RETENTION_DAYS, max=MAX_RETENTION_DAYS),
                    ),
                    vol.Required(
                        CONF_MAX_UNKNOWN_FACES,
                        default=current.get(
                            CONF_MAX_UNKNOWN_FACES, DEFAULT_MAX_UNKNOWN_FACES
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_MAX_UNKNOWN_FACES, max=MAX_MAX_UNKNOWN_FACES
                        ),
                    ),
                }
            ),
        )

    async def async_step_polling(self, user_input=None) -> FlowResult:
        """Configure polling, history window, face dedup cooldown, and stranger clear timeout."""
        current = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **current,
                    CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),
                    CONF_HOLD_SECONDS: int(user_input[CONF_HOLD_SECONDS]),
                    CONF_HISTORY_SECONDS: int(user_input[CONF_HISTORY_SECONDS]),
                    CONF_DEDUP_SECONDS: int(user_input[CONF_DEDUP_SECONDS]),
                    CONF_STRANGER_CLEAR_SECONDS: int(
                        user_input[CONF_STRANGER_CLEAR_SECONDS]
                    ),
                },
            )
        return self.async_show_form(
            step_id="polling",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=current.get(
                            CONF_POLL_INTERVAL,
                            self.config_entry.data.get(
                                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                            ),
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
                    vol.Required(
                        CONF_HOLD_SECONDS,
                        default=current.get(
                            CONF_HOLD_SECONDS,
                            self.config_entry.data.get(
                                CONF_HOLD_SECONDS, DEFAULT_HOLD_SECONDS
                            ),
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=3, max=300)),
                    vol.Required(
                        CONF_HISTORY_SECONDS,
                        default=current.get(
                            CONF_HISTORY_SECONDS, DEFAULT_HISTORY_SECONDS
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
                    vol.Required(
                        CONF_DEDUP_SECONDS,
                        default=current.get(
                            CONF_DEDUP_SECONDS, DEFAULT_DEDUP_SECONDS
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
                    vol.Required(
                        CONF_STRANGER_CLEAR_SECONDS,
                        default=current.get(
                            CONF_STRANGER_CLEAR_SECONDS,
                            DEFAULT_STRANGER_CLEAR_SECONDS,
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_STRANGER_CLEAR_SECONDS,
                            max=MAX_STRANGER_CLEAR_SECONDS,
                        ),
                    ),
                }
            ),
        )
