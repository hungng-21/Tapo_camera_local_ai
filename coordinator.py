"""DataUpdateCoordinator and ONVIF PullPoint listener for Tapo Camera Local AI."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import os
import socket
import time
from typing import Any

from pytapo import Tapo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    AI_BINARY_SENSORS,
    AI_DETECTION_SWITCHES,
    AI_SENSITIVITY_SPECS,
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
    DEFAULT_MICROPHONE_VOLUME,
    DEFAULT_ONVIF_PORT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PTZ_STEP_ANGLE,
    DEFAULT_RTSP_PORT,
    DEFAULT_SIREN_DURATION,
    DEFAULT_SIREN_VOLUME,
    DEFAULT_SPEAKER_VOLUME,
    DOMAIN,
    EVENT_TAPO_AI_DETECTED,
    FIXED_MODEL_KEYWORDS,
    LIGHT_FREQUENCY_FROM_API,
    LIGHT_FREQUENCY_TO_API,
    NIGHT_VISION_FROM_API,
    NIGHT_VISION_TO_API,
    NIGHT_VISION_TO_DAYNIGHT,
    PTZ_MODEL_KEYWORDS,
    TapoAISwitchSpec,
    TapoSensitivitySpec,
)

_LOGGER = logging.getLogger(__name__)

PULLPOINT_NS = "http://www.onvif.org/ver10/events/wsdl/PullPointSubscription"


def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """Return True if a TCP port on host is reachable."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def connect_tapo_multi_auth(
    host: str,
    username: str,
    password: str,
    cloud_password: str = "",
    control_port: int = DEFAULT_CONTROL_PORT,
) -> tuple[Tapo, dict[str, Any]]:
    """Try connecting to Tapo control API (port 443) using all valid credential combinations."""
    candidates: list[tuple[str, str, str, str]] = []

    clean_user = (username or "").strip()
    clean_pass = password or ""
    clean_cloud = (cloud_password or "").strip()

    if clean_cloud:
        candidates.append(("admin + cloud_password", "admin", clean_cloud, clean_cloud))

    if clean_user:
        candidates.append(("camera_account_only", clean_user, clean_pass, ""))

    candidates.append(("admin + camera_password", "admin", clean_pass, clean_cloud or clean_pass))

    if clean_cloud and clean_user and clean_user.lower() != "admin":
        candidates.append(("camera_account + cloud_password", clean_user, clean_pass, clean_cloud))

    last_err: Exception | None = None
    seen: set[tuple[str, str, str]] = set()

    for label, u, p, cp in candidates:
        cred_key = (u, p, cp)
        if cred_key in seen or not p:
            continue
        seen.add(cred_key)
        try:
            tapo = Tapo(
                host,
                u,
                p,
                cloudPassword=cp,
                controlPort=control_port,
                reuseSession=True,
                printWarnInformation=False,
            )
            basic_info = getattr(tapo, "basicInfo", None) or tapo.getBasicInfo()
            _LOGGER.info(
                "Đã xác thực thành công API điều khiển Tapo %s:%s bằng phương thức [%s]",
                host,
                control_port,
                label,
            )
            return tapo, basic_info if isinstance(basic_info, dict) else {}
        except Exception as err:
            last_err = err
            _LOGGER.debug(
                "Thử nghiệm xác thực [%s] tới %s:%s thất bại: %s",
                label,
                host,
                control_port,
                err,
            )
            err_str = str(err).lower()
            if "suspension" in err_str or "-40404" in err_str:
                break

    raise RuntimeError(
        f"Không thể xác thực API điều khiển cổng {control_port} trên {host}: {last_err}"
    )


def parse_tapo_basic_info(basic_raw: dict[str, Any], host: str) -> dict[str, str]:
    """Extract normalized device metadata from pytapo basicInfo response."""
    info = (
        basic_raw.get("device_info", {}).get("basic_info", {})
        if isinstance(basic_raw, dict)
        else {}
    )
    if not info and isinstance(basic_raw, dict):
        info = basic_raw

    model = info.get("device_model") or info.get("model") or "Tapo Camera"
    alias = info.get("device_alias") or info.get("nickname") or f"{model} ({host})"
    mac = info.get("mac") or host.replace(".", "_")
    sw_ver = info.get("sw_version") or info.get("fw_ver") or "Unknown"
    serial = info.get("dev_id") or mac
    return {
        "model": str(model),
        "alias": str(alias),
        "mac": str(mac),
        "sw_version": str(sw_ver),
        "serial": str(serial),
    }


def infer_ptz_from_model_or_user(model: str, username: str, title: str) -> bool | None:
    """Infer PTZ capability from model string or camera account name if API check is inconclusive."""
    combined = f"{model} {username} {title}".upper()
    for kw in FIXED_MODEL_KEYWORDS:
        if kw in combined:
            return False
    for kw in PTZ_MODEL_KEYWORDS:
        if kw in combined:
            return True
    return None


def level10_to_word(level: int, use_medium: bool = True) -> str:
    """Convert 1-10 sensitivity level to 3-level string ('low', 'medium'/'normal', 'high')."""
    if level <= 3:
        return "low"
    if level <= 7:
        return "medium" if use_medium else "normal"
    return "high"


def word_to_level10(word: str) -> int:
    """Convert 3-level sensitivity string ('low', 'medium', 'normal', 'high') to 1-10 scale."""
    w = str(word).strip().lower()
    if w == "low":
        return 2
    if w in ("medium", "normal"):
        return 5
    if w == "high":
        return 8
    return 5


class TapoLocalAICoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator managing local pytapo polling, ONVIF PullPoint push, PTZ, Siren, and AI settings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.host: str = entry.data[CONF_HOST].strip()
        self.username: str = entry.data[CONF_USERNAME].strip()
        self.password: str = entry.data[CONF_PASSWORD]
        self.cloud_password: str = entry.data.get(CONF_CLOUD_PASSWORD, "").strip()
        self.control_port: int = int(
            entry.data.get(CONF_CONTROL_PORT, DEFAULT_CONTROL_PORT)
        )
        self.onvif_port: int = int(
            entry.data.get(CONF_ONVIF_PORT, DEFAULT_ONVIF_PORT)
        )
        self.rtsp_port: int = int(
            entry.data.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)
        )

        self.poll_interval: int = int(
            entry.options.get(
                CONF_POLL_INTERVAL,
                entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
            )
        )
        self.hold_seconds: int = int(
            entry.options.get(
                CONF_HOLD_SECONDS,
                entry.data.get(CONF_HOLD_SECONDS, DEFAULT_HOLD_SECONDS),
            )
        )
        self.enable_onvif: bool = bool(
            entry.options.get(
                CONF_ENABLE_ONVIF,
                entry.data.get(CONF_ENABLE_ONVIF, DEFAULT_ENABLE_ONVIF),
            )
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.host}",
            update_interval=timedelta(seconds=self.poll_interval),
        )

        self.tapo: Tapo | None = None
        self.device_model: str = "Tapo Camera"
        self.device_name: str = entry.title or f"Tapo ({self.host})"
        self.device_mac: str = self.host.replace(".", "_")
        self.firmware_version: str = "Unknown"
        self.serial_number: str = entry.unique_id or f"tapo_{self.host.replace('.', '_')}"

        # PTZ capability & state
        self.supports_ptz: bool = False
        self.ptz_step_angle: int = DEFAULT_PTZ_STEP_ANGLE
        self.presets: dict[str, str] = {}
        self.patrol_mode: str = "Off"

        # Image, Audio & Siren states
        self.night_vision_mode: str = "Infrared"
        self.light_frequency: str = "Auto"
        self.speaker_volume: int = DEFAULT_SPEAKER_VOLUME
        self.microphone_volume: int = DEFAULT_MICROPHONE_VOLUME
        self.siren_is_on: bool = False
        self.alarm_mode: str = "sound"
        self.siren_volume: int = DEFAULT_SIREN_VOLUME
        self.siren_volume_level: str = "high"
        self.siren_duration: int = DEFAULT_SIREN_DURATION
        self._user_custom_siren_duration: bool = False
        self._siren_auto_off_task: asyncio.Task | None = None

        # Sensitivity states (both 1-10 numeric and 3-level word)
        self._sensitivity_10: dict[str, int] = {
            spec.key: 5 for spec in AI_SENSITIVITY_SPECS
        }
        self._sensitivity_3: dict[str, str] = {
            spec.key: "normal" for spec in AI_SENSITIVITY_SPECS
        }
        self._sensitivity_format: dict[str, str] = {
            spec.key: spec.default_format for spec in AI_SENSITIVITY_SPECS
        }

        # Raw section cache for safe read-modify-write operations
        self._raw_sections: dict[tuple[str, str], dict[str, Any]] = {}
        self._unsupported_batch_methods: set[str] = set()

        # Track active sensor state and last trigger timestamps
        self._last_triggered_ts: dict[str, float] = {
            spec.key: 0.0 for spec in AI_BINARY_SENSORS
        }
        self._onvif_active_state: dict[str, bool] = {
            spec.key: False for spec in AI_BINARY_SENSORS
        }
        self._last_event_meta: dict[str, dict[str, Any]] = {
            spec.key: {} for spec in AI_BINARY_SENSORS
        }
        self._seen_event_signatures: set[tuple[int, int, int]] = set()
        self._switch_states: dict[str, bool] = {}
        self._supported_switch_specs: list[TapoAISwitchSpec] | None = None
        self._poll_counter: int = 0

        # Backoff tracking for port 443 control API
        self._last_connect_attempt_ts: float = 0.0
        self._connect_retry_cooldown: float = 60.0

        # ONVIF background task handle
        self._onvif_task: asyncio.Task | None = None
        self._stop_onvif = asyncio.Event()
        self._api_lock = asyncio.Lock()

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant DeviceInfo for this Tapo camera."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            name=self.device_name,
            manufacturer="TP-Link Tapo",
            model=self.device_model,
            sw_version=self.firmware_version,
            configuration_url=f"https://{self.host}:{self.control_port}",
        )

    def _connect_tapo_sync(self) -> dict[str, Any]:
        """Connect to Tapo camera synchronously in executor using multi-auth fallback."""
        self._last_connect_attempt_ts = time.monotonic()
        tapo, basic_info = connect_tapo_multi_auth(
            self.host,
            self.username,
            self.password,
            self.cloud_password,
            self.control_port,
        )
        self.tapo = tapo
        return basic_info

    def _detect_ptz_and_presets_sync(self) -> tuple[bool, dict[str, str]]:
        """Detect whether the camera supports PTZ motor control and load saved presets."""
        inferred = infer_ptz_from_model_or_user(
            self.device_model, self.username, self.device_name
        )

        if self.tapo is None:
            return bool(inferred), {}

        raw_presets = getattr(self.tapo, "presets", None)
        if raw_presets is None or raw_presets == {}:
            try:
                raw_presets = self.tapo.isSupportingPresets()
            except Exception:
                raw_presets = False

        if raw_presets is not False and isinstance(raw_presets, dict):
            parsed_presets = {str(k): str(v) for k, v in raw_presets.items()}
            if inferred is False and not parsed_presets:
                return False, {}
            return True, parsed_presets

        try:
            cap = self.tapo.getMotorCapability()
            if cap:
                return True, {}
        except Exception:
            pass

        return bool(inferred), {}

    async def async_setup(self) -> None:
        """Initialize local connection to Tapo camera, detect PTZ capability, and start ONVIF listener."""
        try:
            basic_raw = await self.hass.async_add_executor_job(self._connect_tapo_sync)
            meta = parse_tapo_basic_info(basic_raw, self.host)
            self.device_model = meta["model"]
            self.device_name = meta["alias"]
            self.device_mac = meta["mac"]
            self.firmware_version = meta["sw_version"]
            self.serial_number = meta["serial"]
        except Exception as err:
            _LOGGER.warning(
                "API điều khiển cổng %s trên %s chưa phản hồi (%s). "
                "Integration vẫn khởi chạy bình thường với luồng RTSP (cổng %s) & ONVIF (cổng %s).",
                self.control_port,
                self.host,
                err,
                self.rtsp_port,
                self.onvif_port,
            )

        # Detect PTZ capability & presets BEFORE querying switches so fixed cameras skip motor queries
        try:
            self.supports_ptz, self.presets = await self.hass.async_add_executor_job(
                self._detect_ptz_and_presets_sync
            )
            _LOGGER.info(
                "Camera %s (%s): hỗ trợ PTZ = %s, số điểm nhớ Preset = %d",
                self.device_name,
                self.device_model,
                self.supports_ptz,
                len(self.presets),
            )
        except Exception as ptz_err:
            _LOGGER.debug("Lỗi kiểm tra PTZ trên %s: %s", self.host, ptz_err)
            self.supports_ptz = bool(
                infer_ptz_from_model_or_user(
                    self.device_model, self.username, self.device_name
                )
            )

        if self.tapo is not None:
            await self.async_refresh_switches()

        if self.enable_onvif:
            self._stop_onvif.clear()
            self._onvif_task = self.entry.async_create_background_task(
                self.hass,
                self._async_onvif_pullpoint_loop(),
                name=f"tapo_local_ai_onvif_{self.host}",
            )

    async def async_shutdown(self) -> None:
        """Clean up ONVIF subscription, siren timer, and close Tapo transport."""
        self._stop_onvif.set()
        if self._siren_auto_off_task and not self._siren_auto_off_task.done():
            self._siren_auto_off_task.cancel()
        if self._onvif_task and not self._onvif_task.done():
            self._onvif_task.cancel()
            try:
                await self._onvif_task
            except asyncio.CancelledError:
                pass

    def _poll_camera_events_sync(self) -> list[dict[str, Any]]:
        """Query local searchDetectionList via pytapo.getEvents()."""
        if self.tapo is None:
            if (time.monotonic() - self._last_connect_attempt_ts) < self._connect_retry_cooldown:
                return []
            self._connect_tapo_sync()
            try:
                self.supports_ptz, self.presets = self._detect_ptz_and_presets_sync()
                self._switch_states.update(self._read_switches_sync())
            except Exception:
                pass

        assert self.tapo is not None
        now_ts = int(time.time())

        try:
            events = self.tapo.getEvents(startTime=now_ts - 90, endTime=now_ts + 15)
            if isinstance(events, list):
                return events
        except Exception as err:
            _LOGGER.debug(
                "getEvents() trên %s trả về lỗi (%s), thử gọi trực tiếp searchDetectionList",
                self.host,
                err,
            )

        time_corr = 0
        try:
            tc = self.tapo.getTimeCorrection()
            if tc is not False and tc is not None:
                time_corr = int(tc)
        except Exception:
            time_corr = 0

        cam_now = now_ts - time_corr
        raw = self.tapo.executeFunction(
            "searchDetectionList",
            {
                "playback": {
                    "search_detection_list": {
                        "start_index": 0,
                        "channel": 0,
                        "start_time": cam_now - 90,
                        "end_time": cam_now + 15,
                        "end_index": 50,
                    }
                }
            },
        )
        det_list = (
            raw.get("playback", {}).get("search_detection_list", [])
            if isinstance(raw, dict)
            else []
        )
        results: list[dict[str, Any]] = []
        if isinstance(det_list, list):
            for ev in det_list:
                ev_copy = dict(ev)
                ev_copy["start_time"] = int(ev_copy.get("start_time", cam_now)) + time_corr
                ev_copy["end_time"] = int(ev_copy.get("end_time", cam_now)) + time_corr
                results.append(ev_copy)
        return results

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest local AI detection events from camera without marking entities unavailable on transient errors."""
        now_ts = time.time()
        events: list[dict[str, Any]] = []

        try:
            async with self._api_lock:
                events = await self.hass.async_add_executor_job(
                    self._poll_camera_state_and_events_sync
                )
        except Exception as err:
            _LOGGER.debug(
                "Bỏ qua lỗi tạm thời khi quét trạng thái & sự kiện trên %s: %s",
                self.host,
                err,
            )

        for ev in events:
            try:
                alarm_type = int(ev.get("alarm_type", 0))
            except (ValueError, TypeError):
                alarm_type = 0

            try:
                events_1 = int(ev.get("events_1", 0))
            except (ValueError, TypeError):
                events_1 = 0

            start_time = int(ev.get("start_time", 0))
            end_time = int(ev.get("end_time", start_time))
            sig = (start_time, alarm_type, events_1)

            age_since_end = now_ts - max(start_time, end_time)
            is_recent = age_since_end <= self.hold_seconds

            for spec in AI_BINARY_SENSORS:
                matched_alarm = alarm_type in spec.alarm_types
                matched_bitmask = any(
                    bool(events_1 & flag) for flag in spec.bitmask_flags
                )
                if matched_alarm or matched_bitmask:
                    if is_recent:
                        was_active = self.is_sensor_active(spec.key, now_ts)
                        self._last_triggered_ts[spec.key] = max(
                            self._last_triggered_ts[spec.key],
                            float(max(start_time, end_time)),
                            now_ts if sig not in self._seen_event_signatures else 0.0,
                        )
                        self._last_event_meta[spec.key] = {
                            "last_event_start": datetime.fromtimestamp(start_time).isoformat(),
                            "last_event_end": datetime.fromtimestamp(end_time).isoformat(),
                            "alarm_type_id": alarm_type,
                            "events_1_bitmask": events_1,
                            "detection_source": "tapo_local_api",
                        }
                        if not was_active and sig not in self._seen_event_signatures:
                            self._fire_ha_event(
                                spec.key,
                                "tapo_local_api",
                                self._last_event_meta[spec.key],
                            )

            self._seen_event_signatures.add(sig)

        if len(self._seen_event_signatures) > 500:
            cutoff = int(now_ts) - 600
            self._seen_event_signatures = {
                s for s in self._seen_event_signatures if s[0] >= cutoff
            }

        return self._build_state_snapshot(now_ts)

    def is_sensor_active(self, key: str, now_ts: float | None = None) -> bool:
        """Return True if the given AI sensor is active via ONVIF or within hold_seconds."""
        if now_ts is None:
            now_ts = time.time()
        if self._onvif_active_state.get(key, False):
            return True
        last_ts = self._last_triggered_ts.get(key, 0.0)
        return (now_ts - last_ts) <= self.hold_seconds

    def _build_state_snapshot(self, now_ts: float | None = None) -> dict[str, Any]:
        """Build state dictionary consumed by entities."""
        if now_ts is None:
            now_ts = time.time()
        sensors: dict[str, dict[str, Any]] = {}
        for spec in AI_BINARY_SENSORS:
            active = self.is_sensor_active(spec.key, now_ts)
            sensors[spec.key] = {
                "is_on": active,
                "last_triggered_ts": self._last_triggered_ts.get(spec.key, 0.0),
                **self._last_event_meta.get(spec.key, {}),
            }
        return {
            "sensors": sensors,
            "switches": dict(self._switch_states),
            "sensitivity_10": dict(self._sensitivity_10),
            "sensitivity_3": dict(self._sensitivity_3),
            "presets": dict(self.presets),
            "patrol_mode": self.patrol_mode,
            "ptz_step_angle": self.ptz_step_angle,
            "night_vision_mode": self.night_vision_mode,
            "light_frequency": self.light_frequency,
            "speaker_volume": self.speaker_volume,
            "microphone_volume": self.microphone_volume,
            "siren_is_on": self.siren_is_on,
            "alarm_mode": self.alarm_mode,
            "siren_volume": self.siren_volume,
            "siren_volume_level": self.siren_volume_level,
            "siren_duration": self.siren_duration,
        }

    @callback
    def _fire_ha_event(self, sensor_key: str, source: str, extra: dict[str, Any]) -> None:
        """Fire a Home Assistant event on the event bus when an AI detection triggers."""
        self.hass.bus.async_fire(
            EVENT_TAPO_AI_DETECTED,
            {
                "device_id": self.serial_number,
                "device_name": self.device_name,
                "host": self.host,
                "event_type": sensor_key,
                "source": source,
                **extra,
            },
        )

    @callback
    def _handle_onvif_data_item(self, item_name: str, item_value: str) -> None:
        """Process a single SimpleItem (Name/Value) from an ONVIF PullPoint message."""
        is_true = str(item_value).lower() in ("true", "1", "on", "yes")
        now_ts = time.time()
        changed = False

        for spec in AI_BINARY_SENSORS:
            if item_name in spec.onvif_data_keys:
                prev = self._onvif_active_state.get(spec.key, False)
                self._onvif_active_state[spec.key] = is_true
                if is_true:
                    self._last_triggered_ts[spec.key] = now_ts
                    self._last_event_meta[spec.key] = {
                        "last_event_start": datetime.fromtimestamp(now_ts).isoformat(),
                        "onvif_field": item_name,
                        "detection_source": "onvif_pullpoint",
                    }
                    if not prev:
                        self._fire_ha_event(
                            spec.key,
                            "onvif_pullpoint",
                            self._last_event_meta[spec.key],
                        )
                if prev != is_true:
                    changed = True

        if changed:
            self.async_set_updated_data(self._build_state_snapshot(now_ts))

    async def _async_onvif_pullpoint_loop(self) -> None:
        """Maintain a persistent local ONVIF PullPoint subscription on port 2020."""
        try:
            import onvif
            from onvif import ONVIFCamera
        except ImportError:
            _LOGGER.warning(
                "Thư viện onvif-zeep-async chưa sẵn sàng; chỉ dùng local API polling cho %s",
                self.host,
            )
            return

        wsdl_dir = f"{os.path.dirname(onvif.__file__)}/wsdl/"

        while not self._stop_onvif.is_set():
            cam = None
            try:
                cam = ONVIFCamera(
                    self.host,
                    self.onvif_port,
                    self.username,
                    self.password,
                    wsdl_dir,
                    no_cache=True,
                )
                await cam.update_xaddrs()

                if self.device_model == "Tapo Camera":
                    try:
                        dev_mgmt = await cam.create_devicemgmt_service()
                        dev_info = await dev_mgmt.GetDeviceInformation()
                        if getattr(dev_info, "Model", None):
                            self.device_model = str(dev_info.Model)
                        if getattr(dev_info, "FirmwareVersion", None):
                            self.firmware_version = str(dev_info.FirmwareVersion)
                    except Exception:
                        pass

                try:
                    await cam.create_pullpoint_subscription(
                        {"InitialTerminationTime": "PT10M"}
                    )
                except Exception:
                    events_service = await cam.create_events_service()
                    sub = await events_service.CreatePullPointSubscription(
                        {"InitialTerminationTime": "PT10M"}
                    )
                    cam.xaddrs[PULLPOINT_NS] = sub.SubscriptionReference.Address._value_1

                pullpoint = await cam.create_pullpoint_service()
                if hasattr(pullpoint, "zeep_client") and hasattr(
                    pullpoint.zeep_client, "_settings"
                ):
                    pullpoint.zeep_client._settings.strict = False

                _LOGGER.info(
                    "Đã kết nối luồng sự kiện ONVIF PullPoint local tại %s:%s",
                    self.host,
                    self.onvif_port,
                )

                last_renew = time.monotonic()
                while not self._stop_onvif.is_set():
                    if time.monotonic() - last_renew >= 480:
                        await pullpoint.Renew({"TerminationTime": "PT10M"})
                        last_renew = time.monotonic()

                    resp = await pullpoint.PullMessages(
                        {"Timeout": "PT5S", "MessageLimit": 20}
                    )
                    messages = getattr(resp, "NotificationMessage", None) or []
                    for msg in messages:
                        try:
                            msg_val = msg.Message._value_1
                            data = getattr(msg_val, "Data", None)
                            simple_items = getattr(data, "SimpleItem", None) or []
                            for item in simple_items:
                                name = getattr(item, "Name", None)
                                val = getattr(item, "Value", None)
                                if name is not None and val is not None:
                                    self._handle_onvif_data_item(str(name), str(val))
                        except Exception as parse_err:
                            _LOGGER.debug("Lỗi phân tích gói tin ONVIF: %s", parse_err)

            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.debug(
                    "Kết nối ONVIF PullPoint trên %s:%s tạm gián đoạn (%s), thử lại sau 15s",
                    self.host,
                    self.onvif_port,
                    err,
                )
                try:
                    await asyncio.wait_for(self._stop_onvif.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    pass
            finally:
                if cam is not None:
                    try:
                        await cam.close()
                    except Exception:
                        pass

    # ---------------- PTZ & Camera Control Methods ----------------

    def _ensure_tapo_sync(self) -> Tapo:
        """Ensure self.tapo is connected in executor."""
        if self.tapo is None:
            self._connect_tapo_sync()
        assert self.tapo is not None
        return self.tapo

    def _ptz_move_sync(self, pan: int, tilt: int) -> None:
        """Move camera motor by relative pan/tilt degrees, with fallback to moveMotorStep."""
        tapo = self._ensure_tapo_sync()
        try:
            tapo.moveMotor(pan, tilt)
        except Exception:
            if pan > 0:
                tapo.moveMotorStep(0)
            elif pan < 0:
                tapo.moveMotorStep(180)
            elif tilt > 0:
                tapo.moveMotorStep(90)
            elif tilt < 0:
                tapo.moveMotorStep(270)

    async def async_ptz_move(self, pan: int, tilt: int) -> None:
        """Move camera motor by pan/tilt degrees."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._ptz_move_sync, pan, tilt)

    async def async_ptz_step_direction(self, direction: str) -> None:
        """Move camera in one of UP, DOWN, LEFT, RIGHT by self.ptz_step_angle degrees."""
        step = self.ptz_step_angle
        if direction == "UP":
            await self.async_ptz_move(0, step)
        elif direction == "DOWN":
            await self.async_ptz_move(0, -step)
        elif direction == "LEFT":
            await self.async_ptz_move(-step, 0)
        elif direction == "RIGHT":
            await self.async_ptz_move(step, 0)

    def _calibrate_motor_sync(self) -> None:
        """Calibrate camera motor."""
        tapo = self._ensure_tapo_sync()
        tapo.calibrateMotor()

    async def async_calibrate_motor(self) -> None:
        """Calibrate camera motor position."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._calibrate_motor_sync)

    def _goto_preset_sync(self, preset_id_or_name: str) -> None:
        """Move camera to a saved preset ID or preset name."""
        tapo = self._ensure_tapo_sync()
        target_id = preset_id_or_name
        for pid, pname in self.presets.items():
            if pname == preset_id_or_name or str(pid) == str(preset_id_or_name):
                target_id = pid
                break
        tapo.setPreset(target_id)

    async def async_goto_preset(self, preset_id_or_name: str) -> None:
        """Move camera to preset."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._goto_preset_sync, preset_id_or_name
            )

    def _set_patrol_mode_sync(self, mode: str) -> None:
        """Set PTZ Patrol (Cruise) mode: Off, Horizontal, or Vertical."""
        tapo = self._ensure_tapo_sync()
        if mode == "Horizontal":
            tapo.setCruise(True, "x")
        elif mode == "Vertical":
            tapo.setCruise(True, "y")
        else:
            tapo.setCruise(False)

    async def async_set_patrol_mode(self, mode: str) -> None:
        """Set PTZ Patrol mode and update coordinator state."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._set_patrol_mode_sync, mode)
        self.patrol_mode = mode
        self.async_set_updated_data(self._build_state_snapshot())

    # ---------------- Siren & Manual Alarm Methods ----------------

    def _manual_alarm_sync(self, start: bool) -> None:
        """Start or stop manual siren/alarm on camera."""
        tapo = self._ensure_tapo_sync()
        if start:
            tapo.startManualAlarm()
        else:
            tapo.stopManualAlarm()

    async def async_set_manual_alarm(self, start: bool) -> None:
        """Trigger or stop manual camera alarm (used by buttons and siren)."""
        if start:
            await self.async_turn_on_siren()
        else:
            await self.async_turn_off_siren()

    async def async_turn_on_siren(
        self,
        duration: int | None = None,
        volume_level: float | None = None,
    ) -> None:
        """Turn on camera siren with optional duration (seconds) and volume_level (0.0..1.0)."""
        if volume_level is not None:
            vol_10 = max(1, min(10, round(float(volume_level) * 10)))
            await self.async_set_siren_volume(vol_10)

        async with self._api_lock:
            await self.hass.async_add_executor_job(self._manual_alarm_sync, True)

        self.siren_is_on = True
        self.async_set_updated_data(self._build_state_snapshot())

        eff_duration = duration if duration is not None else self.siren_duration
        if self._siren_auto_off_task and not self._siren_auto_off_task.done():
            self._siren_auto_off_task.cancel()

        if eff_duration and eff_duration > 0:
            self._siren_auto_off_task = self.hass.async_create_task(
                self._async_siren_auto_off(int(eff_duration))
            )

    async def _async_siren_auto_off(self, delay_seconds: int) -> None:
        """Automatically stop manual siren after delay_seconds."""
        try:
            await asyncio.sleep(delay_seconds)
            async with self._api_lock:
                await self.hass.async_add_executor_job(self._manual_alarm_sync, False)
            self.siren_is_on = False
            self.async_set_updated_data(self._build_state_snapshot())
        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.debug("Lỗi tự động tắt còi sau %ds trên %s: %s", delay_seconds, self.host, err)

    async def async_turn_off_siren(self) -> None:
        """Turn off camera siren immediately."""
        if self._siren_auto_off_task and not self._siren_auto_off_task.done():
            self._siren_auto_off_task.cancel()
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._manual_alarm_sync, False)
        self.siren_is_on = False
        self.async_set_updated_data(self._build_state_snapshot())

    def _apply_alarm_config_sync(
        self,
        enabled: bool | None = None,
        alarm_mode: str | None = None,
        volume_level_str: str | None = None,
        duration: int | None = None,
    ) -> None:
        """Apply automatic alarm / siren settings (mode, volume, duration) to the camera."""
        tapo = self._ensure_tapo_sync()
        cur = dict(self._raw_sections.get(("msg_alarm", "chn1_msg_alarm_info"), {}))

        en_bool = (
            enabled
            if enabled is not None
            else self._switch_states.get("auto_alarm_switch", cur.get("enabled") == "on")
        )
        mode_val = alarm_mode or self.alarm_mode
        vol_str = volume_level_str or self.siren_volume_level
        dur_int = duration if duration is not None else self.siren_duration

        mode_list = (
            ["sound", "light"]
            if mode_val == "both"
            else (["light"] if mode_val == "light" else ["sound"])
        )

        payload_info: dict[str, Any] = {
            "enabled": "on" if en_bool else "off",
            "alarm_mode": mode_list,
            "sound_alarm_enabled": "on" if "sound" in mode_list else "off",
            "light_alarm_enabled": "on" if "light" in mode_list else "off",
            "alarm_type": str(cur.get("alarm_type", "0")),
            "light_type": str(cur.get("light_type", "0")),
            "alarm_volume": vol_str,
            "alarm_duration": str(int(dur_int)),
        }

        try:
            tapo.executeFunction(
                "setLastAlarmInfo",
                {"msg_alarm": {"chn1_msg_alarm_info": payload_info}},
            )
            self._raw_sections[("msg_alarm", "chn1_msg_alarm_info")] = payload_info
            return
        except Exception as err1:
            _LOGGER.debug("setLastAlarmInfo thất bại trên %s (%s), thử setAlarm", self.host, err1)

        try:
            tapo.setAlarm(
                bool(en_bool),
                "sound" in mode_list,
                "light" in mode_list,
            )
        except Exception as err2:
            _LOGGER.debug("setAlarm fallback thất bại trên %s: %s", self.host, err2)

    async def async_set_alarm_mode(self, mode: str) -> None:
        """Set alarm mode ('sound', 'light', 'both')."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._apply_alarm_config_sync, None, mode, None, None
            )
        self.alarm_mode = mode
        self.async_set_updated_data(self._build_state_snapshot())

    async def async_set_siren_volume_level(self, level: str) -> None:
        """Set siren volume level ('low', 'normal', 'high')."""
        lvl = level.lower()
        vol_10 = 3 if lvl == "low" else (6 if lvl == "normal" else 10)
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._apply_alarm_config_sync, None, None, lvl, None
            )
        self.siren_volume_level = lvl
        self.siren_volume = vol_10
        self.async_set_updated_data(self._build_state_snapshot())

    async def async_set_siren_volume(self, volume: int) -> None:
        """Set siren volume on 1-10 scale."""
        vol_10 = max(1, min(10, int(volume)))
        lvl = "low" if vol_10 <= 3 else ("normal" if vol_10 <= 7 else "high")
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._apply_alarm_config_sync, None, None, lvl, None
            )
        self.siren_volume = vol_10
        self.siren_volume_level = lvl
        self.async_set_updated_data(self._build_state_snapshot())

    async def async_set_siren_duration(self, duration: int) -> None:
        """Set siren duration in seconds (0..300)."""
        dur = max(0, min(300, int(duration)))
        self._user_custom_siren_duration = True
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._apply_alarm_config_sync, None, None, None, dur
            )
        self.siren_duration = dur
        self.async_set_updated_data(self._build_state_snapshot())

    # ---------------- Speaker & Microphone Volume Methods ----------------

    def _set_speaker_volume_sync(self, volume: int) -> None:
        """Set camera speaker volume (0..100)."""
        tapo = self._ensure_tapo_sync()
        try:
            tapo.setSpeakerVolume(int(volume))
            return
        except Exception:
            pass
        tapo.executeFunction(
            "setAudioConfig",
            {"audio_config": {"speaker": {"volume": str(int(volume))}}},
        )

    async def async_set_speaker_volume(self, volume: int) -> None:
        """Set speaker volume (0..100%)."""
        vol = max(0, min(100, int(volume)))
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._set_speaker_volume_sync, vol)
        self.speaker_volume = vol
        self.async_set_updated_data(self._build_state_snapshot())

    def _set_microphone_volume_sync(self, volume: int) -> None:
        """Set camera microphone volume (0..100)."""
        tapo = self._ensure_tapo_sync()
        try:
            tapo.setMicrophoneVolume(int(volume))
            return
        except Exception:
            pass
        tapo.executeFunction(
            "setAudioConfig",
            {"audio_config": {"microphone": {"volume": str(int(volume))}}},
        )

    async def async_set_microphone_volume(self, volume: int) -> None:
        """Set microphone volume (0..100%)."""
        vol = max(0, min(100, int(volume)))
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._set_microphone_volume_sync, vol
            )
        self.microphone_volume = vol
        self.async_set_updated_data(self._build_state_snapshot())

    # ---------------- Night Vision & Light Frequency Methods ----------------

    def _set_night_vision_mode_sync(self, option: str) -> None:
        """Set Night Vision mode ('Infrared', 'Full-Color', 'Smart')."""
        tapo = self._ensure_tapo_sync()
        nv_code = NIGHT_VISION_TO_API.get(option, "inf_night_vision")
        dn_code = NIGHT_VISION_TO_DAYNIGHT.get(option, "auto")

        # 1. Try modern night_vision_mode config in image.switch
        try:
            if hasattr(tapo, "setNightVisionModeConfig"):
                tapo.setNightVisionModeConfig(nv_code)
                return
        except Exception:
            pass

        try:
            tapo.executeFunction(
                "setNightVisionModeConfig",
                {"image": {"switch": {"night_vision_mode": nv_code}}},
            )
            return
        except Exception:
            pass

        # 2. Fallback to classic Day/Night inf_type in image.common
        try:
            tapo.setDayNightMode(dn_code)
            return
        except Exception:
            pass

        tapo.executeFunction(
            "setLightFrequencyInfo",
            {"image": {"common": {"inf_type": dn_code}}},
        )

    async def async_set_night_vision_mode(self, option: str) -> None:
        """Set Night Vision mode and update coordinator state."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._set_night_vision_mode_sync, option
            )
        self.night_vision_mode = option
        self.async_set_updated_data(self._build_state_snapshot())

    def _set_light_frequency_sync(self, option: str) -> None:
        """Set power-line light frequency anti-flicker mode ('Auto', '50Hz', '60Hz')."""
        tapo = self._ensure_tapo_sync()
        raw_val = LIGHT_FREQUENCY_TO_API.get(option, "auto")
        try:
            tapo.setLightFrequencyMode(raw_val)
            return
        except Exception:
            pass
        tapo.executeFunction(
            "setLightFrequencyInfo",
            {"image": {"common": {"light_freq_mode": raw_val}}},
        )

    async def async_set_light_frequency(self, option: str) -> None:
        """Set Light Frequency mode and update coordinator state."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._set_light_frequency_sync, option
            )
        self.light_frequency = option
        self.async_set_updated_data(self._build_state_snapshot())

    # ---------------- AI & Motion Detection Sensitivity Methods ----------------

    def _set_sensitivity_sync(
        self,
        spec: TapoSensitivitySpec,
        level_10: int,
        word_3: str,
    ) -> None:
        """Set AI or motion detection sensitivity supporting both 10-level (10..100) and 3-level ('low'/'medium'/'high') cameras."""
        tapo = self._ensure_tapo_sync()
        is_enabled = self._switch_states.get(spec.switch_key, True)
        enabled_str = "on" if is_enabled else "off"
        api_word = "medium" if word_3 in ("normal", "medium") else word_3
        numeric_str = str(max(1, min(10, level_10)) * 10)

        # Case 1: Motion or Tamper detection with both sensitivity and digital_sensitivity
        if spec.has_digital_sensitivity:
            payload = {
                spec.module: {
                    spec.section: {
                        "enabled": enabled_str,
                        "sensitivity": api_word,
                        "digital_sensitivity": numeric_str,
                    }
                }
            }
            try:
                tapo.executeFunction(spec.set_method, payload)
                return
            except Exception:
                # Fallback without digital_sensitivity if camera only supports 3-level word
                tapo.executeFunction(
                    spec.set_method,
                    {
                        spec.module: {
                            spec.section: {
                                "enabled": enabled_str,
                                "sensitivity": api_word,
                            }
                        }
                    },
                )
                return

        # Case 2: AI visual / sound detection modules
        fmt = self._sensitivity_format.get(spec.key, spec.default_format)
        primary_val = api_word if fmt == "word" else numeric_str
        fallback_val = numeric_str if fmt == "word" else api_word

        try:
            tapo.executeFunction(
                spec.set_method,
                {
                    spec.module: {
                        spec.section: {
                            "enabled": enabled_str,
                            "sensitivity": primary_val,
                        }
                    }
                },
            )
        except Exception:
            tapo.executeFunction(
                spec.set_method,
                {
                    spec.module: {
                        spec.section: {
                            "enabled": enabled_str,
                            "sensitivity": fallback_val,
                        }
                    }
                },
            )
            self._sensitivity_format[spec.key] = (
                "numeric" if fmt == "word" else "word"
            )

    async def async_set_sensitivity_10(
        self, spec: TapoSensitivitySpec, level: int
    ) -> None:
        """Set sensitivity using 1-10 slider."""
        lvl_10 = max(1, min(10, int(level)))
        w_3 = "low" if lvl_10 <= 3 else ("normal" if lvl_10 <= 7 else "high")
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._set_sensitivity_sync, spec, lvl_10, w_3
            )
        self._sensitivity_10[spec.key] = lvl_10
        self._sensitivity_3[spec.key] = w_3
        self.async_set_updated_data(self._build_state_snapshot())

    async def async_set_sensitivity_3(
        self, spec: TapoSensitivitySpec, level_word: str
    ) -> None:
        """Set sensitivity using 3-level select ('low', 'normal', 'high')."""
        w_3 = level_word.strip().lower()
        if w_3 not in ("low", "normal", "high"):
            w_3 = "normal"
        lvl_10 = word_to_level10(w_3)
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._set_sensitivity_sync, spec, lvl_10, w_3
            )
        self._sensitivity_3[spec.key] = w_3
        self._sensitivity_10[spec.key] = lvl_10
        self.async_set_updated_data(self._build_state_snapshot())

    def _reboot_camera_sync(self) -> None:
        """Reboot camera."""
        tapo = self._ensure_tapo_sync()
        tapo.reboot()

    async def async_reboot_camera(self) -> None:
        """Reboot camera."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._reboot_camera_sync)

    # ---------------- Batched State & Switch Polling Methods ----------------

    def _poll_camera_state_and_events_sync(self) -> list[dict[str, Any]]:
        """Poll both device states (real-time sync with Tapo app) and local AI detection events."""
        self._poll_counter += 1

        try:
            new_switches = self._read_switches_sync()
            if new_switches:
                self._switch_states.update(new_switches)
        except Exception as sw_err:
            _LOGGER.debug("Lỗi làm mới trạng thái switch trên %s: %s", self.host, sw_err)

        if self.supports_ptz and (self._poll_counter % 5 == 0):
            try:
                _, latest_presets = self._detect_ptz_and_presets_sync()
                if latest_presets:
                    self.presets = latest_presets
            except Exception:
                pass

        return self._poll_camera_events_sync()

    def _build_batch_requests(self) -> list[dict[str, Any]]:
        """Build deduplicated list of get* sub-requests for multipleRequest."""
        reqs: list[dict[str, Any]] = []
        if self.supports_ptz:
            reqs.append(
                {
                    "method": "getTargetTrackConfig",
                    "params": {"target_track": {"name": ["target_track_info"]}},
                }
            )
        reqs.extend(
            [
                {
                    "method": "getBCDConfig",
                    "params": {"sound_detection": {"name": ["bcd"]}},
                },
                {
                    "method": "getBarkDetectionConfig",
                    "params": {"bark_detection": {"name": ["detection"]}},
                },
                {
                    "method": "getMeowDetectionConfig",
                    "params": {"meow_detection": {"name": ["detection"]}},
                },
                {
                    "method": "getGlassDetectionConfig",
                    "params": {"glass_detection": {"name": ["detection"]}},
                },
                {
                    "method": "getPersonDetectionConfig",
                    "params": {"people_detection": {"name": ["detection"]}},
                },
                {
                    "method": "getPetDetectionConfig",
                    "params": {"pet_detection": {"name": ["detection"]}},
                },
                {
                    "method": "getVehicleDetectionConfig",
                    "params": {"vehicle_detection": {"name": ["detection"]}},
                },
                {
                    "method": "getDetectionConfig",
                    "params": {"motion_detection": {"name": ["motion_det"]}},
                },
                {
                    "method": "getTamperDetectionConfig",
                    "params": {"tamper_detection": {"name": ["tamper_det"]}},
                },
                {
                    "method": "getLensMaskConfig",
                    "params": {"lens_mask": {"name": ["lens_mask_info"]}},
                },
                {
                    "method": "getLedStatus",
                    "params": {"led": {"name": ["config"]}},
                },
                {
                    "method": "getLdc",
                    "params": {"image": {"name": ["switch", "common"]}},
                },
                {
                    "method": "getRecordPlan",
                    "params": {"record_plan": {"name": ["chn1_channel"]}},
                },
                {
                    "method": "getAudioConfig",
                    "params": {"audio_config": {"name": ["speaker", "microphone"]}},
                },
                {
                    "method": "getLastAlarmInfo",
                    "params": {"msg_alarm": {"name": ["chn1_msg_alarm_info"]}},
                },
            ]
        )
        return [
            r
            for r in reqs
            if r["method"] not in self._unsupported_batch_methods
        ]

    def _ingest_result_body(self, res_body: dict[str, Any]) -> None:
        """Store raw module/section dicts from a Tapo response body."""
        if not isinstance(res_body, dict):
            return
        for mod_name, mod_val in res_body.items():
            if isinstance(mod_val, dict):
                for sec_name, sec_val in mod_val.items():
                    if isinstance(sec_val, dict):
                        existing = self._raw_sections.get((mod_name, sec_name), {})
                        existing.update(sec_val)
                        self._raw_sections[(mod_name, sec_name)] = existing

    def _extract_states_from_raw_sections(self) -> dict[str, bool]:
        """Parse switches, sensitivities, image modes, audio volumes, and alarm config from cached sections."""
        states: dict[str, bool] = {}

        # 1. Switches
        for sw in AI_DETECTION_SWITCHES:
            if sw.ptz_only and not self.supports_ptz:
                continue
            sec_data = self._raw_sections.get((sw.get_module, sw.get_section))
            if isinstance(sec_data, dict) and sw.field_name in sec_data:
                raw_v = str(sec_data[sw.field_name]).strip().lower()
                if sw.field_name == "flip_type":
                    states[sw.key] = raw_v in ("center", "on", "1", "true")
                else:
                    states[sw.key] = raw_v == sw.on_value.lower()

        # 2. Sensitivities (1-10 and 3-level)
        for sp in AI_SENSITIVITY_SPECS:
            sec_data = self._raw_sections.get((sp.module, sp.section))
            if not isinstance(sec_data, dict):
                continue

            has_dig = False
            if sp.has_digital_sensitivity and "digital_sensitivity" in sec_data:
                try:
                    d_val = int(float(sec_data["digital_sensitivity"]))
                    lvl_10 = (
                        max(1, min(10, round(d_val / 10.0)))
                        if d_val > 10
                        else max(1, min(10, d_val))
                    )
                    self._sensitivity_10[sp.key] = lvl_10
                    has_dig = True
                except (ValueError, TypeError):
                    pass

            if "sensitivity" in sec_data:
                s_raw = str(sec_data["sensitivity"]).strip().lower()
                try:
                    n_val = int(float(s_raw))
                    self._sensitivity_format[sp.key] = "numeric"
                    lvl_10 = (
                        max(1, min(10, round(n_val / 10.0)))
                        if n_val > 10
                        else max(1, min(10, n_val))
                    )
                    self._sensitivity_10[sp.key] = lvl_10
                    self._sensitivity_3[sp.key] = (
                        "low"
                        if lvl_10 <= 3
                        else ("normal" if lvl_10 <= 7 else "high")
                    )
                except (ValueError, TypeError):
                    if s_raw in ("low", "medium", "normal", "high"):
                        self._sensitivity_format[sp.key] = "word"
                        w_norm = "normal" if s_raw in ("medium", "normal") else s_raw
                        self._sensitivity_3[sp.key] = w_norm
                        if not has_dig:
                            self._sensitivity_10[sp.key] = word_to_level10(w_norm)

        # 3. Night Vision & Light Frequency
        img_switch = self._raw_sections.get(("image", "switch"), {})
        img_common = self._raw_sections.get(("image", "common"), {})
        nv_raw = img_switch.get("night_vision_mode") or img_common.get("inf_type")
        if nv_raw and str(nv_raw) in NIGHT_VISION_FROM_API:
            self.night_vision_mode = NIGHT_VISION_FROM_API[str(nv_raw)]

        lf_raw = img_common.get("light_freq_mode")
        if lf_raw and str(lf_raw) in LIGHT_FREQUENCY_FROM_API:
            self.light_frequency = LIGHT_FREQUENCY_FROM_API[str(lf_raw)]

        # 4. Audio Volumes (Speaker & Microphone)
        spk_sec = self._raw_sections.get(("audio_config", "speaker"), {})
        if "volume" in spk_sec:
            try:
                self.speaker_volume = max(0, min(100, int(float(spk_sec["volume"]))))
            except (ValueError, TypeError):
                pass

        mic_sec = self._raw_sections.get(("audio_config", "microphone"), {})
        if "volume" in mic_sec:
            try:
                self.microphone_volume = max(0, min(100, int(float(mic_sec["volume"]))))
            except (ValueError, TypeError):
                pass

        # 5. Siren / Alarm Config
        alarm_sec = self._raw_sections.get(("msg_alarm", "chn1_msg_alarm_info"), {})
        if alarm_sec:
            modes = alarm_sec.get("alarm_mode")
            if isinstance(modes, list):
                if "sound" in modes and "light" in modes:
                    self.alarm_mode = "both"
                elif "light" in modes:
                    self.alarm_mode = "light"
                else:
                    self.alarm_mode = "sound"

            vol_raw = str(
                alarm_sec.get("alarm_volume") or alarm_sec.get("siren_volume") or ""
            ).strip().lower()
            if vol_raw:
                if vol_raw.isdigit():
                    v_10 = max(1, min(10, int(vol_raw)))
                    self.siren_volume = v_10
                    self.siren_volume_level = (
                        "low" if v_10 <= 3 else ("normal" if v_10 <= 7 else "high")
                    )
                elif vol_raw in ("low", "normal", "medium", "high"):
                    lvl = "normal" if vol_raw in ("normal", "medium") else vol_raw
                    self.siren_volume_level = lvl
                    self.siren_volume = 3 if lvl == "low" else (6 if lvl == "normal" else 10)

            dur_raw = (
                alarm_sec.get("alarm_duration")
                if "alarm_duration" in alarm_sec
                else alarm_sec.get("siren_duration")
            )
            if dur_raw is not None:
                try:
                    d_int = max(0, min(300, int(float(dur_raw))))
                    if d_int > 0 or not self._user_custom_siren_duration:
                        self.siren_duration = d_int
                except (ValueError, TypeError):
                    pass

        return states

    def _read_switches_sync(self) -> dict[str, bool]:
        """Read all switches, sensitivities, image settings, and audio/siren configs in 1 batched multipleRequest."""
        tapo = self._ensure_tapo_sync()
        req_list = self._build_batch_requests()

        if req_list:
            try:
                raw_resp: Any = None
                if hasattr(tapo, "performRequest"):
                    raw_resp = tapo.performRequest(
                        {"method": "multipleRequest", "params": {"requests": req_list}}
                    )
                else:
                    raw_resp = tapo.executeFunction(
                        "multipleRequest", {"requests": req_list}
                    )

                resp_items: list[Any] | None = None
                if isinstance(raw_resp, dict):
                    if "result" in raw_resp and isinstance(raw_resp["result"], dict):
                        resp_items = raw_resp["result"].get("responses")
                    elif "responses" in raw_resp:
                        resp_items = raw_resp.get("responses")
                elif isinstance(raw_resp, list):
                    resp_items = raw_resp

                if isinstance(resp_items, list) and resp_items:
                    for idx, item in enumerate(resp_items):
                        if not isinstance(item, dict):
                            continue
                        err_code = item.get("error_code", 0)
                        method_name = item.get("method") or (
                            req_list[idx]["method"] if idx < len(req_list) else ""
                        )
                        if err_code != 0:
                            if method_name:
                                self._unsupported_batch_methods.add(method_name)
                            continue
                        res_body = item.get("result", item)
                        if isinstance(res_body, dict):
                            self._ingest_result_body(res_body)

                    states = self._extract_states_from_raw_sections()
                    if states:
                        return states
            except Exception as batch_err:
                _LOGGER.debug(
                    "multipleRequest đọc trạng thái trên %s gặp lỗi (%s), chuyển sang đọc từng phần",
                    self.host,
                    batch_err,
                )

        # Fallback: query each item individually and prune unsupported methods
        for req in req_list:
            m_name = req["method"]
            try:
                res = tapo.executeFunction(m_name, req["params"])
                if isinstance(res, dict):
                    self._ingest_result_body(res)
            except Exception:
                self._unsupported_batch_methods.add(m_name)

        return self._extract_states_from_raw_sections()

    async def async_refresh_switches(self) -> None:
        """Refresh AI detection configuration switches and device states from the camera."""
        try:
            async with self._api_lock:
                new_states = await self.hass.async_add_executor_job(
                    self._read_switches_sync
                )
                if new_states:
                    self._switch_states.update(new_states)
        except Exception as err:
            _LOGGER.debug("Không thể đọc trạng thái switch AI trên %s: %s", self.host, err)

    def _set_switch_sync(self, spec: TapoAISwitchSpec, enabled: bool) -> None:
        """Enable or disable a specific AI detection, image processing, or hardware module on the camera."""
        tapo = self._ensure_tapo_sync()
        target_val = spec.on_value if enabled else spec.off_value

        # Special handling for Image Flip
        if spec.key == "flip":
            try:
                tapo.setImageFlipVertical(enabled)
                return
            except Exception:
                pass
            try:
                tapo.executeFunction(
                    "setRotationStatus",
                    {"image": {"switch": {"flip_type": target_val}}},
                )
                return
            except Exception:
                tapo.executeFunction(
                    "setLdc",
                    {"image": {"switch": {"flip_type": target_val}}},
                )
                return

        # Special handling for Lens Distortion Correction (LDC)
        if spec.key == "lens_distortion":
            try:
                tapo.setLensDistortionCorrection(enabled)
                return
            except Exception:
                pass
            tapo.executeFunction(
                "setLdc",
                {"image": {"switch": {"ldc": target_val}}},
            )
            return

        # Special handling for Record to SD Card (preserve weekly schedule)
        if spec.key == "record_to_sd":
            cur_plan = dict(
                self._raw_sections.get(("record_plan", "chn1_channel"), {})
            )
            if not cur_plan:
                default_day = '["0000-2400:2"]'
                cur_plan = {
                    day: default_day
                    for day in (
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    )
                }
            cur_plan["enabled"] = target_val
            tapo.executeFunction(
                "setRecordPlan",
                {"record_plan": {"chn1_channel": cur_plan}},
            )
            self._raw_sections[("record_plan", "chn1_channel")] = cur_plan
            return

        # Special handling for Microphone Mute
        if spec.key == "microphone_mute":
            try:
                tapo.executeFunction(
                    "setAudioConfig",
                    {"audio_config": {"microphone": {"mute": target_val}}},
                )
                return
            except Exception:
                cur_mic = dict(
                    self._raw_sections.get(("audio_config", "microphone"), {})
                )
                cur_mic["mute"] = target_val
                tapo.executeFunction(
                    "setAudioConfig",
                    {"audio_config": {"microphone": cur_mic}},
                )
                return

        # Special handling for Auto Alarm switch
        if spec.key == "auto_alarm_switch":
            self._apply_alarm_config_sync(enabled=enabled)
            return

        # Standard AI detection & control switches
        payload = {
            spec.set_module: {
                spec.set_section: {
                    spec.field_name: target_val,
                }
            }
        }
        tapo.executeFunction(spec.set_method, payload)

    async def async_set_ai_switch(self, spec: TapoAISwitchSpec, enabled: bool) -> None:
        """Set an AI detection or hardware switch state and update coordinator data."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._set_switch_sync, spec, enabled)
        self._switch_states[spec.key] = enabled
        self.async_set_updated_data(self._build_state_snapshot())
