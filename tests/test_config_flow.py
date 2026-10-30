"""Tests of the config and options flows."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pid_controller.const import (
    CONF_INITIAL_VALUES,
    CONF_SOURCE,
    DOMAIN,
)

from .conftest import NAME, SOURCE

INITIAL = {
    "set_point": 12.0,
    "proportional": 2.0,
    "integral": 0.1,
    "derivative": 0.0,
    "minimum": 0.0,
    "maximum": 9.0,
}


async def test_user_flow(hass: HomeAssistant) -> None:
    """A controller is created from the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: f"  {NAME} ",
            CONF_SOURCE: SOURCE,
            CONF_UNIT_OF_MEASUREMENT: "level",
            CONF_INITIAL_VALUES: INITIAL,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {}
    assert result["options"] == {
        CONF_NAME: NAME,
        CONF_SOURCE: SOURCE,
        CONF_UNIT_OF_MEASUREMENT: "level",
        CONF_INITIAL_VALUES: INITIAL,
    }
    await hass.async_block_till_done()
    assert hass.states.get("number.air_purifier_maximum").state == "9.0"


async def test_user_flow_name_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A second controller with the same name is rejected, then fixed."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    user_input = {
        CONF_NAME: NAME.upper(),
        CONF_SOURCE: SOURCE,
        CONF_INITIAL_VALUES: INITIAL,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "name_exists"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**user_input, CONF_NAME: "Bedroom"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """The source and unit can be changed, which reloads the controller."""
    hass.states.async_set("sensor.pm25_bedroom", "3")
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SOURCE: "sensor.pm25_bedroom", CONF_UNIT_OF_MEASUREMENT: "level"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert loaded_entry.options[CONF_SOURCE] == "sensor.pm25_bedroom"
    assert loaded_entry.options[CONF_NAME] == NAME
    state = hass.states.get("sensor.air_purifier")
    assert state.attributes["unit_of_measurement"] == "level"
    assert state.attributes["source"] == 3


async def test_import_flow(hass: HomeAssistant) -> None:
    """An imported controller is created once."""
    import_data = {
        CONF_NAME: NAME,
        CONF_SOURCE: SOURCE,
        CONF_UNIT_OF_MEASUREMENT: "points",
        CONF_INITIAL_VALUES: INITIAL,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == import_data

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
