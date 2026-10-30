"""Config flow for the PID Controller integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast, override

from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
    entity_selector_without_own_entities,
)
import probatio

from .const import (
    CONF_DERIVATIVE,
    CONF_INITIAL_VALUES,
    CONF_INTEGRAL,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_PROPORTIONAL,
    CONF_SET_POINT,
    CONF_SOURCE,
    DEFAULTS,
    DOMAIN,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigFlowResult

SOURCE_DOMAINS = [SENSOR_DOMAIN, NUMBER_DOMAIN, INPUT_NUMBER_DOMAIN]
SOURCE_SELECTOR_CONFIG = selector.EntitySelectorConfig(domain=SOURCE_DOMAINS)

_NUMBER_BOX = selector.NumberSelector(
    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any")
)
_GAIN_BOX = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, mode=selector.NumberSelectorMode.BOX, step="any"
    )
)

INITIAL_VALUES_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_SET_POINT, default=DEFAULTS[CONF_SET_POINT]
        ): _NUMBER_BOX,
        probatio.Required(
            CONF_PROPORTIONAL, default=DEFAULTS[CONF_PROPORTIONAL]
        ): _GAIN_BOX,
        probatio.Required(CONF_INTEGRAL, default=DEFAULTS[CONF_INTEGRAL]): _GAIN_BOX,
        probatio.Required(
            CONF_DERIVATIVE, default=DEFAULTS[CONF_DERIVATIVE]
        ): _GAIN_BOX,
        probatio.Required(CONF_MINIMUM, default=DEFAULTS[CONF_MINIMUM]): _NUMBER_BOX,
        probatio.Required(CONF_MAXIMUM, default=DEFAULTS[CONF_MAXIMUM]): _NUMBER_BOX,
    }
)


async def _validate_user(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Reject a name that is already used by another controller."""
    name = user_input[CONF_NAME].strip()
    entries = handler.parent_handler.hass.config_entries.async_entries(DOMAIN)
    if any(entry.title.casefold() == name.casefold() for entry in entries):
        msg = "name_exists"
        raise SchemaFlowError(msg)
    return {**user_input, CONF_NAME: name}


async def _get_options_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(CONF_SOURCE): entity_selector_without_own_entities(
                cast("SchemaOptionsFlowHandler", handler.parent_handler),
                SOURCE_SELECTOR_CONFIG,
            ),
            probatio.Optional(CONF_UNIT_OF_MEASUREMENT): selector.TextSelector(),
        }
    )


CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): selector.TextSelector(),
        probatio.Required(CONF_SOURCE): selector.EntitySelector(SOURCE_SELECTOR_CONFIG),
        probatio.Optional(CONF_UNIT_OF_MEASUREMENT): selector.TextSelector(),
        probatio.Required(CONF_INITIAL_VALUES): section(
            INITIAL_VALUES_SCHEMA, {"collapsed": True}
        ),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, validate_user_input=_validate_user),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(_get_options_schema),
}


class PIDControllerConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for a PID controller."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    VERSION = 1

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return the config entry title."""
        return cast("str", options[CONF_NAME])

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a controller from the legacy YAML sensor platform."""
        self._async_abort_entries_match({CONF_NAME: import_data[CONF_NAME]})
        return self.async_create_entry(data=import_data)
