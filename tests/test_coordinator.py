"""Regression tests for polling load, outage handling and cache correctness."""
from __future__ import annotations

from pathlib import Path
import time

import pytest
import requests

from conftest import UpdateFailed

UNREACHABLE = "HTTPSConnectionPool(host='192.0.2.10', port=443): [Errno 113] Host is unreachable"


class DeadTapo:
    """Every camera call fails like a camera that dropped off Wi-Fi."""

    def __init__(self) -> None:
        self.calls = 0

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def _fail(*args, **kwargs):
            self.calls += 1
            raise requests.exceptions.ConnectionError(UNREACHABLE)

        return _fail


class HealthyTapo:
    """Answers every request successfully and records which methods were called."""

    def __init__(self, alarm_info: dict | None = None) -> None:
        self.methods: list[str] = []
        self.payloads: dict[str, dict] = {}
        self.alarm_info = alarm_info or {}

    def executeFunction(self, method, params):
        self.methods.append(method)
        self.payloads[method] = params
        if method == "multipleRequest":
            return {
                "result": {
                    "responses": [
                        {"method": r["method"], "error_code": 0, "result": {}}
                        for r in params["requests"]
                    ]
                }
            }
        if method == "getLensMaskConfig":
            return {"lens_mask": {"lens_mask_info": {"enabled": "off"}}}
        if method == "getLastAlarmInfo":
            return {"msg_alarm": {"chn1_msg_alarm_info": dict(self.alarm_info)}}
        return {}

    def getEvents(self, **kwargs):
        self.methods.append("getEvents")
        return []


def test_full_poll_stops_at_first_network_error(coordinator):
    coordinator.tapo = DeadTapo()
    coordinator._force_full_config_sync = True
    with pytest.raises(OSError):
        coordinator._poll_camera_state_and_events_sync()
    assert coordinator.tapo.calls == 1


def test_light_poll_stops_at_first_network_error(coordinator):
    coordinator.tapo = DeadTapo()
    coordinator._force_full_config_sync = False
    coordinator._switch_states = {"privacy_mode_switch": False}
    coordinator._last_full_sync_ts = time.monotonic()
    coordinator._poll_counter = 1
    with pytest.raises(OSError):
        coordinator._poll_camera_state_and_events_sync()
    assert coordinator.tapo.calls == 1


def test_config_sync_is_time_based_not_every_other_poll(coordinator):
    coordinator.tapo = HealthyTapo()
    for _ in range(20):
        coordinator._poll_camera_state_and_events_sync()
    batches = coordinator.tapo.methods.count("multipleRequest")
    chunks_per_sync = -(-len(coordinator._build_batch_requests()) // 3)
    assert batches == chunks_per_sync


def test_privacy_mode_read_is_throttled(coordinator):
    coordinator.tapo = HealthyTapo()
    for _ in range(5):
        coordinator._poll_camera_state_and_events_sync()
    assert coordinator.tapo.methods.count("getLensMaskConfig") == 1


def test_batch_does_not_repeat_lens_mask_request(coordinator):
    methods = [r["method"] for r in coordinator._build_batch_requests()]
    assert "getLensMaskConfig" not in methods


def test_missing_sd_card_is_not_a_connection_failure(coordinator):
    class NoSdTapo(HealthyTapo):
        def getEvents(self, **kwargs):
            raise Exception('Error: STORAGE_NOT_EXIST, Response: {"error_code": -71114}')

        def executeFunction(self, method, params):
            if method == "searchDetectionList":
                raise Exception('Error: STORAGE_NOT_EXIST, Response: {"error_code": -71114}')
            return super().executeFunction(method, params)

    coordinator.tapo = NoSdTapo()
    assert coordinator._poll_camera_events_sync() == []


def test_entities_become_unavailable_after_sustained_outage(coordinator, run):
    coordinator.tapo = DeadTapo()
    run(coordinator._async_update_data())  # first failure: still available
    coordinator._down_since = time.monotonic() - 61
    with pytest.raises(UpdateFailed):
        run(coordinator._async_update_data())

    coordinator.tapo = HealthyTapo()
    run(coordinator._async_update_data())
    assert coordinator._down_since is None


def test_onvif_states_reset_when_listener_disconnects(coordinator):
    key = next(iter(coordinator._onvif_active_state))
    coordinator._onvif_active_state[key] = True
    coordinator._reset_onvif_states()
    assert not any(coordinator._onvif_active_state.values())
    assert not coordinator.is_sensor_active(key)


def test_alarm_change_reads_camera_before_writing_enabled_flag(coordinator):
    coordinator.tapo = HealthyTapo(alarm_info={"enabled": "on", "alarm_mode": ["sound"]})
    coordinator._raw_sections = {}
    coordinator._switch_states = {}
    coordinator._apply_alarm_config_sync(None, None, "high", None)
    sent = coordinator.tapo.payloads["setLastAlarmInfo"]["msg_alarm"]["chn1_msg_alarm_info"]
    assert sent["enabled"] == "on"


def test_sensitivity_cache_stores_value_actually_sent(coordinator):
    from tapo_local_ai.const import AI_SENSITIVITY_SPECS

    spec = next(s for s in AI_SENSITIVITY_SPECS if not s.has_digital_sensitivity)
    coordinator._sensitivity_format[spec.key] = "word"

    class RejectFirstTapo(HealthyTapo):
        def executeFunction(self, method, params):
            if method == spec.set_method and not self.methods:
                self.methods.append(method)
                raise Exception("Error: -40210")
            return super().executeFunction(method, params)

    coordinator.tapo = RejectFirstTapo()
    coordinator._set_sensitivity_sync(spec, 8, "high")
    cached = coordinator._raw_sections[(spec.module, spec.section)]["sensitivity"]
    assert cached == "80"


def test_sensitivity_network_error_does_not_flip_format(coordinator):
    from tapo_local_ai.const import AI_SENSITIVITY_SPECS

    spec = next(s for s in AI_SENSITIVITY_SPECS if not s.has_digital_sensitivity)
    coordinator._sensitivity_format[spec.key] = "word"
    coordinator.tapo = DeadTapo()
    with pytest.raises(OSError):
        coordinator._set_sensitivity_sync(spec, 8, "high")
    assert coordinator._sensitivity_format[spec.key] == "word"


def test_every_websocket_command_requires_admin():
    source = (
        Path(__file__).resolve().parents[1]
        / "custom_components/tapo_local_ai/websocket.py"
    ).read_text(encoding="utf-8")
    assert source.count("@websocket_api.websocket_command(") == 8
    assert source.count("@websocket_api.require_admin") == 8
