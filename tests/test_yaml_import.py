"""Tests of importing the legacy YAML sensor platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pid_controller.const import DOMAIN

# The configuration this integration was used with in v1 (README example).
LEGACY_CONFIG = {
    "platform": "pid_controller",
    "name": "Oczyszczacz Salon PID",
    "set_point": '{{ states("input_number.pid_salon_set_point") }}',
    "p": '{{ states("input_number.pid_salon_proportional") }}',
    "i": "0.05",
    "d": "{{ 0 }}",
    "entity_id": "sensor.salon_pm25",
    "invert": '{{ states("input_boolean.pid_salon_invert") }}',
    "precision": "{{ 0 }}",
    "minimum": "0",
    "maximum": '{{ states("input_number.pid_salon_maximum") }}',
    "round": '{{ states("input_select.pid_salon_round") }}',
    "sample_time": "{{ states('input_number.missing') }}",
    "windup": "{{ 1 / 0 }}",
}


async def test_import_legacy_yaml(hass: HomeAssistant) -> None:
    """The YAML platform becomes a config entry with the current values."""
    hass.states.async_set("sensor.salon_pm25", "25")
    hass.states.async_set("input_number.pid_salon_set_point", "10.0")
    hass.states.async_set("input_number.pid_salon_proportional", "5")
    hass.states.async_set("input_boolean.pid_salon_invert", "on")
    hass.states.async_set("input_number.pid_salon_maximum", "9.0")
    hass.states.async_set("input_select.pid_salon_round", "Floor")

    assert await async_setup_component(hass, "sensor", {"sensor": [LEGACY_CONFIG]})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.title == "Oczyszczacz Salon PID"
    assert entry.options["source"] == "sensor.salon_pm25"
    assert entry.options["unit_of_measurement"] == "points"
    assert entry.options["initial_values"] == {
        "set_point": 10.0,
        "proportional": 5.0,
        "integral": 0.05,
        "derivative": 0.0,
        "minimum": 0.0,
        "maximum": 9.0,
        "precision": 0,
        "sample_time": 0.0,
        "windup": 20.0,
        "invert": True,
        "enabled": True,
        "round": "floor",
    }

    # The output sensor keeps the entity ID of the YAML sensor.
    assert hass.states.get("sensor.oczyszczacz_salon_pid").state == "6"
    assert hass.states.get("switch.oczyszczacz_salon_pid_invert").state == "on"

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, "deprecated_yaml_sensor.salon_pm25_Oczyszczacz Salon PID"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml"
    warnings = issue.translation_placeholders["warnings"]
    assert "set_point: followed input_number.pid_salon_set_point" in warnings
    assert "sample_time: '{{ states('input_number.missing') }}'" in warnings
    assert "windup:" in warnings


async def test_import_already_imported(hass: HomeAssistant) -> None:
    """A YAML platform that was imported before only raises an issue."""
    hass.states.async_set("sensor.salon_pm25", "25")
    MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        options={"name": "Salon", "source": "sensor.salon_pm25"},
    ).add_to_hass(hass)
    config = {
        "platform": "pid_controller",
        "name": "Salon",
        "entity_id": "sensor.salon_pm25",
    }
    assert await async_setup_component(hass, "sensor", {"sensor": [config]})
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, "deprecated_yaml_sensor.salon_pm25_Salon"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_exists"
