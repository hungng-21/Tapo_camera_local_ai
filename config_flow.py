"""Config flow and Options flow for Tapo Camera Local AI integration."""
from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CLOUD_PASSWORD,
    CONF_CONTROL_PORT,
    CONF_ENABLE_ONVIF,
    CONF_HOLD_SECONDS,
    CONF_ONVIF_PORT,
    CONF_POLL_INTERVAL,
    CONF_RTSP_PORT,
    DEFAULT_CONTROL_PORT,
    DEFAULT_ENABLE_ONVIF,
    DEFAULT_HOLD_SECONDS,
    DEFAULT_ONVIF_PORT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RTSP_PORT,
    DOMAIN,
)
from .coordinator import (
    check_tcp_port,
    connect_tapo_multi_auth,
    parse_tapo_basic_info,
)

_LOGGER = logging.getLogger(__name__)


def _validate_tapo_or_ports_sync(data: dict[str, Any]) -> dict[str, Any]:
    """Validate camera via pytapo multi-auth, or fall back to checking RTSP/ONVIF TCP ports."""
    host = data[CONF_HOST].strip()
    username = data[CONF_USERNAME].strip()
    password = data[CONF_PASSWORD]
    cloud_password = data.get(CONF_CLOUD_PASSWORD, "").strip()
    control_port = int(data.get(CONF_CONTROL_PORT, DEFAULT_CONTROL_PORT))
    onvif_port = int(data.get(CONF_ONVIF_PORT, DEFAULT_ONVIF_PORT))
    rtsp_port = int(data.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT))

    try:
        _, basic = connect_tapo_multi_auth(
            host, username, password, cloud_password, control_port
        )
        meta = parse_tapo_basic_info(basic, host)
        return {
            "serial": meta["serial"],
            "title": meta["alias"],
            "mode": "full_local_api",
        }
    except Exception as tapo_err:
        _LOGGER.warning(
            "Kết nối pytapo cổng %s tới %s chưa thành công (%s); kiểm tra cổng ONVIF (%s) / RTSP (%s)...",
            control_port,
            host,
            tapo_err,
            onvif_port,
            rtsp_port,
        )

    onvif_open = check_tcp_port(host, onvif_port, timeout=3.0)
    rtsp_open = check_tcp_port(host, rtsp_port, timeout=3.0)
    if onvif_open or rtsp_open:
        fallback_serial = f"tapo_{host.replace('.', '_')}"
        fallback_title = f"Tapo {username} ({host})"
        return {
            "serial": fallback_serial,
            "title": fallback_title,
            "mode": "onvif_rtsp_fallback",
            "onvif_open": onvif_open,
        }

    raise ConnectionError(
        f"Không thể kết nối tới {host} trên cả cổng {control_port}, {onvif_port} và {rtsp_port}."
    )


async def _async_validate_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate camera connection using executor + optional ONVIF device info lookup."""
    info = await hass.async_add_executor_job(_validate_tapo_or_ports_sync, data)

    if info.get("mode") == "onvif_rtsp_fallback" and info.get("onvif_open"):
        try:
            import onvif
            from onvif import ONVIFCamera

            host = data[CONF_HOST].strip()
            onvif_port = int(data.get(CONF_ONVIF_PORT, DEFAULT_ONVIF_PORT))
            wsdl_dir = f"{os.path.dirname(onvif.__file__)}/wsdl/"
            cam = ONVIFCamera(
                host,
                onvif_port,
                data[CONF_USERNAME].strip(),
                data[CONF_PASSWORD],
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
            await cam.close()
        except Exception as onvif_err:
            _LOGGER.debug("Không đọc được GetDeviceInformation qua ONVIF: %s", onvif_err)

    return info


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
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
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
                return self.async_create_entry(title=info["title"], data=user_input)

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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow (compatible with Home Assistant 2025/2026+)."""
        return TapoLocalAIOptionsFlowHandler()


class TapoLocalAIOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Tapo Camera Local AI without overriding read-only config_entry property."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the integration options and connection settings."""
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
                # Update entry.data with connection credentials and entry.options with runtime tuning
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, **user_input},
                )
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                        CONF_HOLD_SECONDS: user_input[CONF_HOLD_SECONDS],
                        CONF_ENABLE_ONVIF: user_input[CONF_ENABLE_ONVIF],
                    },
                )

        current = {**entry.data, **entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_build_full_schema(current),
            errors=errors,
        )
