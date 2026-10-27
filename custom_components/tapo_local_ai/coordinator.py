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
    DEFAULT_PTZ_STEP_ANGLE,
    DEFAULT_RTSP_PORT,
    DOMAIN,
    EVENT_TAPO_AI_DETECTED,
    FIXED_MODEL_KEYWORDS,
    PTZ_MODEL_KEYWORDS,
    TapoAISwitchSpec,
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


class TapoLocalAICoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator managing local pytapo polling, ONVIF PullPoint push, and PTZ motor controls."""

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
        self.supports_ptz: bool = bool(
            infer_ptz_from_model_or_user(
                self.device_model, self.username, self.device_name
            )
        )
        self.ptz_step_angle: int = DEFAULT_PTZ_STEP_ANGLE
        self.presets: dict[str, str] = {}
        self.patrol_mode: str = "Off"

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
        self._switch_states: dict[str, bool] = {
            spec.key: False for spec in AI_DETECTION_SWITCHES
        }
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

        if inferred is False:
            return False, {}

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

        # Detect PTZ capability & presets FIRST so we know whether to query PTZ-only switches
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

        # Refresh switch states using batched multipleRequest
        await self.async_refresh_switches()

        if self.enable_onvif:
            self._stop_onvif.clear()
            self._onvif_task = self.entry.async_create_background_task(
                self.hass,
                self._async_onvif_pullpoint_loop(),
                name=f"tapo_local_ai_onvif_{self.host}",
            )

    async def async_shutdown(self) -> None:
        """Clean up ONVIF subscription and close Tapo transport."""
        self._stop_onvif.set()
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
                new_sw = self._read_switches_sync()
                if new_sw:
                    self._switch_states.update(new_sw)
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
        """Fetch latest local AI detection events and switch states from camera."""
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
            "presets": dict(self.presets),
            "patrol_mode": self.patrol_mode,
            "ptz_step_angle": self.ptz_step_angle,
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

    def _manual_alarm_sync(self, start: bool) -> None:
        """Start or stop manual siren/alarm on camera."""
        tapo = self._ensure_tapo_sync()
        if start:
            tapo.startManualAlarm()
        else:
            tapo.stopManualAlarm()

    async def async_set_manual_alarm(self, start: bool) -> None:
        """Trigger or stop manual camera alarm."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._manual_alarm_sync, start)

    def _reboot_camera_sync(self) -> None:
        """Reboot camera."""
        tapo = self._ensure_tapo_sync()
        tapo.reboot()

    async def async_reboot_camera(self) -> None:
        """Reboot camera."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._reboot_camera_sync)

    # ---------------- Switch Configuration Methods ----------------

    def _poll_camera_state_and_events_sync(self) -> list[dict[str, Any]]:
        """Poll both switch states (real-time sync with Tapo app) and local AI detection events."""
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

    def _read_switches_sync(self) -> dict[str, bool]:
        """Read AI detection and control switch states via batched multipleRequest (with per-switch fallback)."""
        tapo = self._ensure_tapo_sync()
        target_specs = [
            sw
            for sw in AI_DETECTION_SWITCHES
            if (not sw.ptz_only) or self.supports_ptz
        ]

        states: dict[str, bool] = {}

        # 1. Always try a single batched multipleRequest first (fast ~50ms, avoids C125 burst rate-limiting)
        try:
            req_list = [
                {
                    "method": sw.get_method,
                    "params": {sw.get_module: {"name": [sw.get_section]}},
                }
                for sw in target_specs
            ]
            batch_res = tapo.executeFunction(
                "multipleRequest", {"requests": req_list}
            )
            if isinstance(batch_res, list):
                spec_by_method = {sw.get_method: sw for sw in target_specs}
                for idx, item in enumerate(batch_res):
                    if not isinstance(item, dict):
                        continue
                    if item.get("error_code", 0) != 0:
                        continue
                    sw = spec_by_method.get(str(item.get("method", "")))
                    if sw is None and idx < len(target_specs):
                        sw = target_specs[idx]
                    if sw is None:
                        continue
                    res_body = item.get("result", item)
                    if isinstance(res_body, dict):
                        sec_data = res_body.get(sw.get_module, {}).get(
                            sw.get_section, {}
                        )
                        if isinstance(sec_data, dict) and "enabled" in sec_data:
                            states[sw.key] = (
                                str(sec_data["enabled"]).lower() == "on"
                            )
                if states:
                    return states
        except Exception as batch_err:
            _LOGGER.debug(
                "multipleRequest đọc switch trên %s không khả dụng (%s), chuyển sang đọc tuần tự",
                self.host,
                batch_err,
            )

        # 2. Sequential fallback if multipleRequest was rejected
        for sw in target_specs:
            try:
                res = tapo.executeFunction(
                    sw.get_method,
                    {sw.get_module: {"name": [sw.get_section]}},
                )
                sec_data = (
                    res.get(sw.get_module, {}).get(sw.get_section, {})
                    if isinstance(res, dict)
                    else {}
                )
                if isinstance(sec_data, dict) and "enabled" in sec_data:
                    states[sw.key] = str(sec_data["enabled"]).lower() == "on"
            except Exception:
                continue

        return states

    async def async_refresh_switches(self) -> None:
        """Refresh AI detection configuration switches from the camera."""
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
        """Enable or disable a specific AI detection or control module on the camera."""
        tapo = self._ensure_tapo_sync()
        payload = {
            spec.set_module: {
                spec.set_section: {
                    "enabled": "on" if enabled else "off",
                }
            }
        }
        tapo.executeFunction(spec.set_method, payload)

    async def async_set_ai_switch(self, spec: TapoAISwitchSpec, enabled: bool) -> None:
        """Set an AI detection switch state and update coordinator data."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._set_switch_sync, spec, enabled)
        self._switch_states[spec.key] = enabled
        self.async_set_updated_data(self._build_state_snapshot())
