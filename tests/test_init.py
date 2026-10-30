"""Tests of setting up and unloading the integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pid_controller.const import CONF_SOURCE, DOMAIN

from .conftest import OUTPUT, SOURCE, set_source, setup_entry


async def test_setup_and_unload(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The entry creates a device with the controller entities."""
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(OUTPUT).state == "0.0"

    entities = er.async_entries_for_config_entry(entity_registry, loaded_entry.entry_id)
    assert {entity.entity_id for entity in entities} >= {
        OUTPUT,
        "number.air_purifier_set_point",
        "number.air_purifier_gain_p",
        "number.air_purifier_maximum",
        "number.air_purifier_sample_time",
        "switch.air_purifier_enabled",
        "switch.air_purifier_invert",
        "select.air_purifier_rounding",
        "button.air_purifier_reset",
        "sensor.air_purifier_term_i",
    }
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, loaded_entry.entry_id), loaded_entry.entry_id
    )
    assert device is not None
    assert device.name == "Air purifier"

    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_multiple_instances(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Several controllers can run side by side."""
    hass.states.async_set("sensor.temperature", "18")
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Heating",
        options={
            CONF_NAME: "Heating",
            CONF_SOURCE: "sensor.temperature",
            "initial_values": {"set_point": 21, "proportional": 10},
        },
    )
    await setup_entry(hass, second)

    assert hass.states.get("sensor.heating").state == "30.0"
    assert hass.states.get(OUTPUT).state == "0.0"


async def test_source_entity_renamed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The controller follows a renamed source entity."""
    source = entity_registry.async_get_or_create(
        "sensor", "test", "pm25", suggested_object_id="pm25"
    )
    assert source.entity_id == SOURCE
    set_source(hass, "30")
    await setup_entry(hass, mock_config_entry)

    entity_registry.async_update_entity(SOURCE, new_entity_id="sensor.pm25_salon")
    await hass.async_block_till_done()

    assert mock_config_entry.options[CONF_SOURCE] == "sensor.pm25_salon"
    assert mock_config_entry.runtime_data.source_entity_id == "sensor.pm25_salon"
