"""The PID Controller integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
)
from homeassistant.helpers.start import async_at_started

from .const import CONF_INITIAL_VALUES, CONF_SOURCE, DOMAIN
from .controller import PIDConfigEntry, PIDController, PIDParameters

PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: PIDConfigEntry) -> bool:
    """Set up a PID controller from a config entry."""
    source = entry.options[CONF_SOURCE]
    controller = PIDController(
        hass,
        source,
        PIDParameters.from_mapping(entry.options.get(CONF_INITIAL_VALUES, {})),
    )
    entry.runtime_data = controller

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_SOURCE: source_entity_id}
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(hass, source),
            source_entity_id_or_uuid=source,
        )
    )

    # The entities restore their values into the controller while they are
    # added, so the controller only starts once every platform is set up.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(controller.async_stop)

    @callback
    def _async_start(_hass: HomeAssistant) -> None:
        controller.async_start()

    entry.async_on_unload(async_at_started(hass, _async_start))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PIDConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
