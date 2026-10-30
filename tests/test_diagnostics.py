"""Tests of the diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import SOURCE


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    """Diagnostics show the parameters, PID state and source."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, loaded_entry
    )
    assert diagnostics["parameters"]["set_point"] == 10
    assert diagnostics["parameters"]["round"] == "round"
    assert diagnostics["output"] == 0
    assert diagnostics["pid"]["error"] == -20
    assert diagnostics["source"] == {
        "entity_id": SOURCE,
        "value": 30,
        "available": True,
    }
    assert diagnostics["last_update"] is not None
