"""Conversion of the legacy YAML sensor platform (v1) into a config entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template, result_as_boolean

from .const import (
    CONF_DERIVATIVE,
    CONF_ENABLED,
    CONF_INITIAL_VALUES,
    CONF_INTEGRAL,
    CONF_INVERT,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_PRECISION,
    CONF_PROPORTIONAL,
    CONF_ROUND,
    CONF_SAMPLE_TIME,
    CONF_SET_POINT,
    CONF_SOURCE,
    CONF_WINDUP,
    LEGACY_DEFAULTS,
    RoundMode,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

# Legacy YAML key -> parameter key.
LEGACY_TEMPLATE_KEYS: Final = {
    "set_point": CONF_SET_POINT,
    "p": CONF_PROPORTIONAL,
    "i": CONF_INTEGRAL,
    "d": CONF_DERIVATIVE,
    "minimum": CONF_MINIMUM,
    "maximum": CONF_MAXIMUM,
    "precision": CONF_PRECISION,
    "sample_time": CONF_SAMPLE_TIME,
    "windup": CONF_WINDUP,
    "invert": CONF_INVERT,
    "enabled": CONF_ENABLED,
    "round": CONF_ROUND,
}
LEGACY_UNIT: Final = "points"
_BOOLEAN_STATES: Final = {"on", "off", "true", "false", "yes", "no", "1", "0"}


async def async_convert_legacy_config(
    hass: HomeAssistant, config: ConfigType
) -> tuple[dict[str, Any], list[str]]:
    """
    Convert a legacy platform config into config entry options.

    Templates are rendered once: their current value becomes the initial value of
    the matching entity. Returns the options and human readable warnings.
    """
    warnings: list[str] = []
    initial: dict[str, Any] = {}

    for legacy_key, key in LEGACY_TEMPLATE_KEYS.items():
        default = LEGACY_DEFAULTS[key]
        if (template := config.get(legacy_key)) is None:
            initial[key] = default
            continue

        rendered, entities = _render(hass, template)
        try:
            value = _convert(key, rendered)
        except ValueError:
            warnings.append(
                f"{legacy_key}: '{template.template}' gave '{rendered}', "
                f"using the default {default}"
            )
            value = default
        else:
            if entities:
                warnings.append(
                    f"{legacy_key}: followed {', '.join(sorted(entities))}, "
                    f"now its own entity starting at {value}"
                )
        initial[key] = value

    return (
        {
            CONF_NAME: config[CONF_NAME],
            CONF_SOURCE: config[CONF_ENTITY_ID],
            CONF_UNIT_OF_MEASUREMENT: config.get(CONF_UNIT_OF_MEASUREMENT, LEGACY_UNIT),
            CONF_INITIAL_VALUES: initial,
        },
        warnings,
    )


def _render(hass: HomeAssistant, template: Template) -> tuple[str | None, set[str]]:
    template = Template(template.template, hass)
    try:
        info = template.async_render_to_info(parse_result=False)
        return str(info.result()), set(info.entities)
    except TemplateError:
        return None, set()


def _convert(key: str, rendered: str | None) -> Any:
    if rendered is None:
        msg = "Template could not be rendered"
        raise ValueError(msg)
    match key:
        case "invert" | "enabled":
            # result_as_boolean() reads anything unknown as False, which would
            # silently turn an unavailable helper into "off".
            value = rendered.strip().lower()
            if value not in _BOOLEAN_STATES:
                msg = f"Not a boolean: {rendered}"
                raise ValueError(msg)
            return result_as_boolean(value)
        case "round":
            return RoundMode(rendered.strip().lower())
        case "precision":
            return int(float(rendered))
        case _:
            return float(rendered)
