"""Fixtures for the PID Controller tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import PropertyMock, patch

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pid_controller.const import (
    CONF_INITIAL_VALUES,
    CONF_SOURCE,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"

SOURCE = "sensor.pm25"
NAME = "Air purifier"
OUTPUT = "sensor.air_purifier"


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in all tests."""


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable the entities that are disabled by default."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


@pytest.fixture
def initial_values() -> dict[str, Any]:
    """Return the initial values of the test controller."""
    return {
        "set_point": 10.0,
        "proportional": 1.0,
        "integral": 0.0,
        "derivative": 0.0,
        "minimum": 0.0,
        "maximum": 100.0,
    }


@pytest.fixture
def mock_config_entry(initial_values: dict[str, Any]) -> MockConfigEntry:
    """Return a config entry of a PID controller."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        entry_id="01PIDCONTROLLERTESTENTRY",
        options={
            CONF_NAME: NAME,
            CONF_SOURCE: SOURCE,
            CONF_UNIT_OF_MEASUREMENT: "%",
            CONF_INITIAL_VALUES: initial_values,
        },
    )


def set_source(hass: HomeAssistant, value: str) -> None:
    """Set the state of the source sensor."""
    hass.states.async_set(
        SOURCE,
        value,
        {CONF_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up a config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the test controller with the source at 30."""
    set_source(hass, "30")
    await setup_entry(hass, mock_config_entry)
    return mock_config_entry
