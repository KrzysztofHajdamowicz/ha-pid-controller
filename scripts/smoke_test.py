#!/usr/bin/env python3
"""
Smoke test the integration against any installed Home Assistant release.

pytest-homeassistant-custom-component only exists for stable releases, so this
boots a real Home Assistant instance instead, which also works with betas:
it creates a controller through the config flow, imports a YAML controller
and checks that both react to their source sensors.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
import sys
import tempfile

from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import SOURCE_USER, ConfigEntries
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ROOT = Path(__file__).resolve().parent.parent


async def _settle(hass: HomeAssistant) -> None:
    await hass.async_block_till_done()
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    if state is None:
        msg = f"{entity_id} does not exist"
        raise AssertionError(msg)
    return state.state


async def _run(config_dir: Path) -> None:
    hass = HomeAssistant(str(config_dir))
    loader.async_setup(hass)
    hass.config.skip_pip = True
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    if not await async_load_base_functionality(hass):
        msg = "Base functionality failed to load"
        raise AssertionError(msg)

    hass.states.async_set("sensor.pm25", "30")
    hass.states.async_set("input_number.max", "9")

    # YAML is only read when the sensor component is set up, as at startup.
    yaml_ok = await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "pid_controller",
                    "name": "Legacy",
                    "entity_id": "sensor.pm25",
                    "set_point": "10",
                    "p": "5",
                    "invert": "true",
                    "maximum": '{{ states("input_number.max") }}',
                }
            ]
        },
    )
    result = await hass.config_entries.flow.async_init(
        "pid_controller", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Smoke",
            "source": "sensor.pm25",
            "initial_values": {
                "set_point": 10,
                "proportional": 2,
                "integral": 0,
                "derivative": 0,
                "minimum": 0,
                "maximum": 100,
            },
        },
    )
    if result["type"] != "create_entry":
        msg = f"Config flow did not create an entry: {result}"
        raise AssertionError(msg)

    await hass.async_start()
    await _settle(hass)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.smoke_sample_time", "value": 0},
        blocking=True,
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.smoke_invert"}, blocking=True
    )
    await _settle(hass)
    checks = {"smoke inverted at 30": (_state(hass, "sensor.smoke"), "40.0")}
    hass.states.async_set("sensor.pm25", "15")
    await _settle(hass)
    checks["smoke inverted at 15"] = (_state(hass, "sensor.smoke"), "10.0")
    checks["yaml import"] = (str(yaml_ok), "True")
    checks["legacy output at 15"] = (_state(hass, "sensor.legacy"), "2.25")

    await hass.async_stop()

    print(f"Home Assistant {ha_version}")
    failed = False
    for name, (actual, expected) in checks.items():
        ok = actual == expected
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {actual} (expected {expected})")
    if failed:
        sys.exit(1)


def main() -> None:
    """Run the smoke test in a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        shutil.copytree(
            ROOT / "custom_components" / "pid_controller",
            config_dir / "custom_components" / "pid_controller",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        asyncio.run(_run(config_dir))


if __name__ == "__main__":
    main()
