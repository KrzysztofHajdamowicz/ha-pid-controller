"""Constants for the PID Controller integration."""

from __future__ import annotations

from enum import StrEnum
import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "pid_controller"
NAME: Final = "PID Controller"
ISSUE_URL: Final = "https://github.com/KrzysztofHajdamowicz/ha-pid-controller/issues"

CONF_SOURCE: Final = "source"
CONF_INITIAL_VALUES: Final = "initial_values"

# Controller parameters, exposed as their own entities. The same keys are used
# for the initial values stored in the config entry options.
CONF_SET_POINT: Final = "set_point"
CONF_PROPORTIONAL: Final = "proportional"
CONF_INTEGRAL: Final = "integral"
CONF_DERIVATIVE: Final = "derivative"
CONF_MINIMUM: Final = "minimum"
CONF_MAXIMUM: Final = "maximum"
CONF_PRECISION: Final = "precision"
CONF_SAMPLE_TIME: Final = "sample_time"
CONF_WINDUP: Final = "windup"
CONF_INVERT: Final = "invert"
CONF_ENABLED: Final = "enabled"
CONF_ROUND: Final = "round"


class RoundMode(StrEnum):
    """How the controller output is rounded to the configured precision."""

    ROUND = "round"
    FLOOR = "floor"
    CEIL = "ceil"


DEFAULTS: Final[dict[str, float | bool | str]] = {
    CONF_SET_POINT: 0.0,
    CONF_PROPORTIONAL: 1.0,
    CONF_INTEGRAL: 0.0,
    CONF_DERIVATIVE: 0.0,
    CONF_MINIMUM: 0.0,
    CONF_MAXIMUM: 100.0,
    CONF_PRECISION: 2,
    CONF_SAMPLE_TIME: 10.0,
    CONF_WINDUP: 100.0,
    CONF_INVERT: False,
    CONF_ENABLED: True,
    CONF_ROUND: RoundMode.ROUND,
}

# Defaults of the legacy YAML platform (v1), used when importing YAML entries
# that do not set an option, so imported controllers behave as before.
LEGACY_DEFAULTS: Final[dict[str, float | bool | str]] = {
    **DEFAULTS,
    CONF_PROPORTIONAL: 0.0,
    CONF_MAXIMUM: 1.0,
    CONF_SAMPLE_TIME: 0.0,
    CONF_WINDUP: 20.0,
}

# The PID itself always works on a 0..100 % scale, which is mapped onto the
# configured minimum..maximum output range.
OUTPUT_SCALE: Final = 100.0
