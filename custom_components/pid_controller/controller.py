"""Runtime of one PID controller instance."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta
from math import ceil, floor, isfinite
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DERIVATIVE,
    CONF_ENABLED,
    CONF_INTEGRAL,
    CONF_INVERT,
    CONF_PROPORTIONAL,
    CONF_SAMPLE_TIME,
    DEFAULTS,
    LOGGER,
    OUTPUT_SCALE,
    RoundMode,
)
from .pid import PID, PIDState

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

type PIDConfigEntry = ConfigEntry[PIDController]


@dataclass(frozen=True, slots=True)
class PIDParameters:
    """Parameters of a controller, each exposed as its own entity."""

    set_point: float
    proportional: float
    integral: float
    derivative: float
    minimum: float
    maximum: float
    precision: int
    sample_time: float
    windup: float
    invert: bool
    enabled: bool
    round: RoundMode

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> PIDParameters:
        """Build parameters from a mapping, filling gaps with the defaults."""
        merged = {**DEFAULTS, **values}
        return cls(
            set_point=float(merged["set_point"]),
            proportional=float(merged["proportional"]),
            integral=float(merged["integral"]),
            derivative=float(merged["derivative"]),
            minimum=float(merged["minimum"]),
            maximum=float(merged["maximum"]),
            precision=int(merged["precision"]),
            sample_time=float(merged["sample_time"]),
            windup=float(merged["windup"]),
            invert=bool(merged["invert"]),
            enabled=bool(merged["enabled"]),
            round=RoundMode(merged["round"]),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the parameters as a dict."""
        return {field.name: getattr(self, field.name) for field in fields(self)}


# Changing these restarts the controller: the integral accumulated with the
# old sign (invert) or while the controller was paused is meaningless.
_RESET_ON_CHANGE = {CONF_INVERT, CONF_ENABLED}
_GAINS = {CONF_PROPORTIONAL, CONF_INTEGRAL, CONF_DERIVATIVE}


class PIDController:
    """Read the source entity, run the PID and publish the output."""

    def __init__(
        self,
        hass: HomeAssistant,
        source_entity_id: str,
        parameters: PIDParameters,
    ) -> None:
        """Initialize the controller."""
        self.hass = hass
        self.source_entity_id = source_entity_id
        self.parameters = parameters
        self.pid = PID()
        self.output: float | None = None
        self.source_value: float | None = None
        self.source_available = True
        self.last_update: datetime | None = None
        self._last_compute: float | None = None
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_source: CALLBACK_TYPE | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._started = False

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Call ``update_callback`` whenever the output or PID state changes."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    @callback
    def async_restore(self, state: PIDState, output: float | None) -> None:
        """Restore the PID state saved before a restart."""
        # Monotonic time does not survive a restart: start a fresh time base.
        state.last_time = None
        self.pid.state = state
        self.output = output

    @callback
    def async_start(self) -> None:
        """Start following the source entity and the sample timer."""
        self._started = True
        self._unsub_source = async_track_state_change_event(
            self.hass, self.source_entity_id, self._async_source_changed
        )
        self._schedule_timer()
        self.async_update()

    @callback
    def async_stop(self) -> None:
        """Stop the controller."""
        self._started = False
        if self._unsub_source is not None:
            self._unsub_source()
            self._unsub_source = None
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def async_set_parameter(self, key: str, value: Any) -> None:
        """Change one parameter and recalculate the output."""
        old = self.parameters
        self.parameters = replace(old, **{key: value})
        if not self._started or getattr(old, key) == getattr(self.parameters, key):
            # Values restored before the start must not touch the PID state.
            return
        if key in _RESET_ON_CHANGE:
            self.pid.reset()
        if key == CONF_SAMPLE_TIME:
            self._schedule_timer()
        self.async_update()

    @callback
    def async_reset(self) -> None:
        """Reset the integral and recalculate the output."""
        self.pid.reset()
        self.async_update()

    @callback
    def async_update(self, *, force: bool = True) -> None:
        """Run the controller once and notify the entities."""
        if not self._started:
            return
        params = self.parameters
        now = time.monotonic()
        if (
            not force
            and self._last_compute is not None
            and now - self._last_compute < params.sample_time
        ):
            return

        if not params.enabled:
            self.output = self._format(params.minimum)
            self._notify()
            return

        measurement = self._read_source()
        if measurement is None:
            # Hold the last output: an unavailable sensor is not a reason to
            # drive the actuator to an extreme.
            self._notify()
            return

        sign = -1.0 if params.invert else 1.0
        self.pid.kp = sign * params.proportional
        self.pid.ki = sign * params.integral
        self.pid.kd = sign * params.derivative
        self.pid.windup = params.windup

        raw = self.pid.update(params.set_point, measurement, now)
        if params.invert and not any(getattr(params, gain) for gain in _GAINS):
            # On/off mode: inverted means "on while above the set point".
            raw = OUTPUT_SCALE - raw
            self.pid.state.output = raw

        self._last_compute = now
        self.last_update = dt_util.utcnow()
        self.output = self._scale(raw)
        self._notify()

    def _scale(self, raw: float) -> float:
        """Map the 0..100 % PID output onto minimum..maximum."""
        params = self.parameters
        fraction = raw / OUTPUT_SCALE if params.minimum <= params.maximum else 0.0
        return self._format(
            params.minimum + (params.maximum - params.minimum) * fraction
        )

    def _format(self, value: float) -> float:
        params = self.parameters
        factor = 10**params.precision
        match params.round:
            case RoundMode.FLOOR:
                value = floor(value * factor) / factor
            case RoundMode.CEIL:
                value = ceil(value * factor) / factor
            case RoundMode.ROUND:
                value = round(value, params.precision)
        return int(value) if params.precision == 0 else value

    def _read_source(self) -> float | None:
        state = self.hass.states.get(self.source_entity_id)
        value: float | None = None
        if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                value = float(state.state)
            except ValueError:
                value = None
            if value is not None and not isfinite(value):
                value = None

        available = value is not None
        if available != self.source_available:
            self.source_available = available
            if available:
                LOGGER.info("Source %s is available again", self.source_entity_id)
            else:
                LOGGER.warning(
                    "Source %s has no numeric value (%s), holding the last output",
                    self.source_entity_id,
                    state.state if state is not None else "missing",
                )
        self.source_value = value
        return value

    def _schedule_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        if self.parameters.sample_time > 0:
            self._unsub_timer = async_track_time_interval(
                self.hass,
                self._async_timer_tick,
                timedelta(seconds=self.parameters.sample_time),
                name=f"PID controller {self.source_entity_id}",
                cancel_on_shutdown=True,
            )

    @callback
    def _async_timer_tick(self, _now: datetime) -> None:
        self.async_update()

    @callback
    def _async_source_changed(self, _event: Event[EventStateChangedData]) -> None:
        self.async_update(force=False)

    def _notify(self) -> None:
        for update_callback in list(self._listeners):
            update_callback()
