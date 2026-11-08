"""Minimal Home Assistant stubs so coordinator logic can be tested without installing HA."""
from __future__ import annotations

import asyncio
import importlib.machinery
from datetime import datetime, timezone
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import pytest

STUBBED_ROOTS = ("homeassistant", "voluptuous", "onvif")


class _AutoModule(types.ModuleType):
    """Module whose unknown attributes are MagicMocks."""

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        value = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, value)
        return value


class _StubFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in STUBBED_ROOTS:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        module = _AutoModule(spec.name)
        module.__path__ = []
        return module

    def exec_module(self, module):
        return None


def _real_module(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    parent, _, child = name.rpartition(".")
    if parent:
        setattr(__import__(parent, fromlist=["_"]), child, module)
    return module


class UpdateFailed(Exception):
    """Stand-in for homeassistant.helpers.update_coordinator.UpdateFailed."""


class DataUpdateCoordinator:
    """Tiny stand-in for HA's DataUpdateCoordinator."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, *, name=None, update_interval=None, **kwargs):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = None
        self.last_update_success = True

    def async_update_listeners(self) -> None:
        return None

    def async_set_updated_data(self, data) -> None:
        self.data = data
        self.last_update_success = True


sys.meta_path.insert(0, _StubFinder())

_real_module(
    "homeassistant.util.dt",
    utcnow=lambda: datetime.now(timezone.utc),
    now=lambda: datetime.now(timezone.utc),
    as_local=lambda value: value,
    get_default_time_zone=lambda: timezone.utc,
    start_of_local_day=lambda day: datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
)
_real_module(
    "homeassistant.helpers.update_coordinator",
    DataUpdateCoordinator=DataUpdateCoordinator,
    UpdateFailed=UpdateFailed,
    CoordinatorEntity=MagicMock,
)
_real_module("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
_real_module(
    "homeassistant.const",
    CONF_HOST="host",
    CONF_PASSWORD="password",
    CONF_USERNAME="username",
    Platform=MagicMock(),
    EntityCategory=MagicMock(),
    UnitOfTime=MagicMock(),
    DEGREE="°",
    PERCENTAGE="%",
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components"))


class FakeEntry:
    def __init__(self, options: dict | None = None) -> None:
        self.data = {"host": "192.0.2.10", "username": "user", "password": "pw"}
        self.options = options or {}
        self.entry_id = "entry1"
        self.title = "Tapo C125"
        self.unique_id = "SERIAL1"


async def _run_in_executor(func, *args):
    return func(*args)


@pytest.fixture
def coordinator():
    from tapo_local_ai.coordinator import TapoLocalAICoordinator

    hass = MagicMock()
    hass.async_add_executor_job = _run_in_executor
    coord = TapoLocalAICoordinator(hass, FakeEntry())
    coord.device_model = "C125"
    return coord


@pytest.fixture
def run():
    return lambda coro: asyncio.run(coro)
