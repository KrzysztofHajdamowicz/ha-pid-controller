"""Tests of the controller behaviour through its entities."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.number import ATTR_VALUE
from homeassistant.components.select import ATTR_OPTION
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from .conftest import OUTPUT, set_source, setup_entry


async def _set_number(hass: HomeAssistant, key: str, value: float) -> None:
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: f"number.air_purifier_{key}", ATTR_VALUE: value},
        blocking=True,
    )


async def _switch(hass: HomeAssistant, key: str, *, on: bool) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {ATTR_ENTITY_ID: f"switch.air_purifier_{key}"},
        blocking=True,
    )


def _output(hass: HomeAssistant) -> float:
    return float(hass.states.get(OUTPUT).state)


@pytest.fixture
def initial_values() -> dict[str, Any]:
    """Return a controller with set point 10 and P = 2 (0 s sample time)."""
    return {
        "set_point": 10.0,
        "proportional": 2.0,
        "minimum": 0.0,
        "maximum": 100.0,
        "sample_time": 0,
    }


async def test_follows_source(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """The output follows the source entity."""
    set_source(hass, "5")
    await hass.async_block_till_done()
    assert _output(hass) == 10

    set_source(hass, "-40")
    await hass.async_block_till_done()
    assert _output(hass) == 100

    state = hass.states.get(OUTPUT)
    assert state.attributes["source"] == -40
    assert state.attributes["unit_of_measurement"] == "%"


async def test_invert(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Invert drives the output up while the source is above the set point."""
    await _switch(hass, "invert", on=True)
    assert _output(hass) == 40


async def test_output_range_and_rounding(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """The 0..100 % PID output is mapped onto minimum..maximum and rounded."""
    await _switch(hass, "invert", on=True)
    await _set_number(hass, "maximum", 9)
    assert _output(hass) == 3.6

    await _set_number(hass, "precision", 0)
    assert hass.states.get(OUTPUT).state == "4"

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.air_purifier_rounding", ATTR_OPTION: "floor"},
        blocking=True,
    )
    assert hass.states.get(OUTPUT).state == "3"

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.air_purifier_rounding", ATTR_OPTION: "ceil"},
        blocking=True,
    )
    assert hass.states.get(OUTPUT).state == "4"

    # A minimum above the maximum keeps the output at the minimum.
    await _set_number(hass, "minimum", 20)
    assert hass.states.get(OUTPUT).state == "20"


async def test_set_point_change(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Changing the set point recalculates the output at once."""
    await _set_number(hass, "set_point", 70)
    assert _output(hass) == 80
    assert (
        hass.states.get("number.air_purifier_set_point").attributes[
            "unit_of_measurement"
        ]
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )


async def test_disabled_outputs_minimum(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """A disabled controller outputs its minimum and ignores the source."""
    await _set_number(hass, "set_point", 70)
    await _set_number(hass, "minimum", 5)
    await _switch(hass, "enabled", on=False)
    assert _output(hass) == 5

    set_source(hass, "0")
    await hass.async_block_till_done()
    assert _output(hass) == 5

    await _switch(hass, "enabled", on=True)
    assert _output(hass) == 100


async def test_on_off_mode(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Without gains the controller switches between minimum and maximum."""
    await _set_number(hass, "proportional_gain", 0)
    assert _output(hass) == 0
    await _switch(hass, "invert", on=True)
    assert _output(hass) == 100
    set_source(hass, "5")
    await hass.async_block_till_done()
    assert _output(hass) == 0


async def test_unavailable_source_holds_output(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unavailable source keeps the last output and is logged once."""
    set_source(hass, "0")
    await hass.async_block_till_done()
    assert _output(hass) == 20

    caplog.set_level(logging.INFO)
    for value in (STATE_UNAVAILABLE, "not a number", "nan"):
        set_source(hass, value)
        await hass.async_block_till_done()
        assert _output(hass) == 20
    assert caplog.text.count("holding the last output") == 1
    assert hass.states.get(OUTPUT).attributes["source_available"] is False

    set_source(hass, "5")
    await hass.async_block_till_done()
    assert _output(hass) == 10
    assert "is available again" in caplog.text


async def test_integral_runs_on_timer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The integral keeps growing on the sample timer with a constant source."""
    set_source(hass, "0")
    await setup_entry(hass, mock_config_entry)
    await _set_number(hass, "proportional_gain", 0)
    await _set_number(hass, "integral_gain", 0.1)
    await _set_number(hass, "sample_time", 10)
    start = _output(hass)

    for _ in range(3):
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert _output(hass) == pytest.approx(start + 3 * 0.1 * 10 * 10, abs=0.5)

    # Source changes faster than the sample time are not calculated yet.
    freezer.tick(timedelta(seconds=2))
    set_source(hass, "1")
    await hass.async_block_till_done()
    assert hass.states.get(OUTPUT).attributes["source"] == 0

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.air_purifier_reset"},
        blocking=True,
    )
    assert _output(hass) == 0


async def test_restore_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Parameters and the integral survive a restart."""
    # Each mock call replaces the restore cache, so everything goes in one call.
    mock_restore_cache_with_extra_data(
        hass,
        [
            (State("switch.air_purifier_invert", "off"), {}),
            (State("select.air_purifier_rounding", "floor"), {}),
            (
                State(OUTPUT, "42"),
                {"output": 42, "pid": {"integral": 30.0, "last_input": 30}},
            ),
            (
                State("number.air_purifier_set_point", "50"),
                {
                    "native_max_value": 1_000_000,
                    "native_min_value": -1_000_000,
                    "native_step": 0.01,
                    "native_unit_of_measurement": None,
                    "native_value": 50,
                },
            ),
        ],
    )
    hass.states.async_set("sensor.pm25", "30")
    await setup_entry(hass, mock_config_entry)

    assert hass.states.get("number.air_purifier_set_point").state == "50.0"
    assert hass.states.get("select.air_purifier_rounding").state == "floor"
    # P = 2 * 20 plus the restored integral of 30, no derivative on restart.
    assert _output(hass) == 70
    assert mock_config_entry.runtime_data.pid.state.integral == 30
