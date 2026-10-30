"""PID algorithm, independent of Home Assistant."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Self

from .const import OUTPUT_SCALE


@dataclass(slots=True)
class PIDState:
    """Internal state of the controller, persisted across restarts."""

    integral: float = 0.0
    last_input: float | None = None
    last_time: float | None = None
    output: float = 0.0
    p_term: float = 0.0
    i_term: float = 0.0
    d_term: float = 0.0
    error: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the state as a dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Restore the state from a dict, ignoring unknown keys."""
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in fields})


@dataclass(slots=True)
class PID:
    """
    PID controller with an output on a 0..100 % scale.

    - Derivative on measurement: changing the set point causes no derivative kick.
    - Conditional integration: the integral only stops growing while the output
      is saturated and the error would push it further out.
    - ``windup`` additionally limits the integral to +/- windup (0 = no limit).
    - With all gains at zero the controller works as an on/off switch.
    """

    kp: float = 0.0
    ki: float = 0.0
    kd: float = 0.0
    windup: float = 0.0
    state: PIDState = field(default_factory=PIDState)

    def reset(self) -> None:
        """Forget the integral and the previous sample."""
        self.state = PIDState()

    def update(self, set_point: float, measurement: float, now: float) -> float:
        """Calculate a new output for ``measurement`` taken at ``now`` (seconds)."""
        state = self.state
        error = set_point - measurement

        if self.kp == 0 and self.ki == 0 and self.kd == 0:
            output = 0.0 if measurement >= set_point else OUTPUT_SCALE
            state.p_term = state.i_term = state.d_term = 0.0
            state.integral = 0.0
        else:
            dt = 0.0 if state.last_time is None else now - state.last_time
            if dt < 0:
                return state.output

            p_term = self.kp * error
            d_term = 0.0
            if state.last_input is not None and dt > 0:
                d_term = -self.kd * (measurement - state.last_input) / dt

            i_step = self.ki * error * dt
            integral = self._limit_windup(state.integral + i_step)
            unclamped = p_term + integral + d_term
            if not (unclamped > OUTPUT_SCALE and i_step > 0) and not (
                unclamped < 0 and i_step < 0
            ):
                state.integral = integral

            output = min(max(p_term + state.integral + d_term, 0.0), OUTPUT_SCALE)
            state.p_term = p_term
            state.i_term = state.integral
            state.d_term = d_term

        state.error = error
        state.output = output
        state.last_input = measurement
        state.last_time = now
        return output

    def _limit_windup(self, value: float) -> float:
        if self.windup <= 0:
            return value
        return min(max(value, -self.windup), self.windup)
