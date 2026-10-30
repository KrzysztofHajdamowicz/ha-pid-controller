"""Tests of the PID algorithm."""

from __future__ import annotations

import pytest

from custom_components.pid_controller.pid import PID, PIDState


def test_proportional() -> None:
    """The proportional term follows the error."""
    pid = PID(kp=2)
    assert pid.update(50, 40, 0) == 20
    assert pid.state.p_term == 20
    assert pid.state.error == 10


def test_output_is_clamped() -> None:
    """The output stays within 0..100."""
    pid = PID(kp=10)
    assert pid.update(50, 0, 0) == 100
    assert pid.update(0, 50, 1) == 0


def test_integral_accumulates_over_time() -> None:
    """The integral grows with error * time."""
    pid = PID(ki=1)
    pid.update(10, 5, 0)
    assert pid.update(10, 5, 2) == 10
    assert pid.update(10, 5, 4) == 20


def test_integral_does_not_freeze_at_saturation() -> None:
    """Regression for soloam#43: the integral recovers after saturation."""
    pid = PID(kp=1, ki=0.5)
    pid.update(100, 0, 0)
    for step in range(1, 50):
        pid.update(100, 0, step * 10)
    # Conditional integration kept the integral from winding up.
    assert pid.state.integral < 1
    pid.update(100, 150, 500)
    assert pid.state.output == 0
    assert pid.state.integral <= 0


def test_integral_grows_from_zero_output() -> None:
    """Regression for soloam#64: a zero output does not block the integral."""
    pid = PID(ki=1)
    for step in range(20):
        pid.update(10, 20, step)
    assert pid.state.output == 0
    for step in range(20, 25):
        pid.update(10, 0, step)
    assert pid.state.output > 0


def test_windup_limits_integral() -> None:
    """The integral is limited to +/- windup."""
    pid = PID(ki=10, windup=5)
    pid.update(10, 0, 0)
    pid.update(10, 0, 1)
    assert pid.state.integral == 5


def test_no_derivative_kick() -> None:
    """The first sample and set point changes cause no derivative spike."""
    pid = PID(kp=1, kd=50)
    assert pid.update(20, 10, 0) == 10
    assert pid.state.d_term == 0
    pid.update(60, 10, 1)
    assert pid.state.d_term == 0
    pid.update(60, 12, 2)
    assert pid.state.d_term == pytest.approx(-100)


def test_on_off_mode() -> None:
    """Without gains the controller switches between 0 and 100."""
    pid = PID()
    assert pid.update(20, 10, 0) == 100
    assert pid.update(20, 20, 1) == 0


def test_time_going_backwards_keeps_output() -> None:
    """A sample older than the previous one is ignored."""
    pid = PID(kp=1)
    pid.update(20, 10, 10)
    assert pid.update(20, 0, 5) == 10


def test_reset() -> None:
    """Reset forgets the integral and the last sample."""
    pid = PID(ki=1)
    pid.update(10, 0, 0)
    pid.update(10, 0, 1)
    pid.reset()
    assert pid.state == PIDState()


def test_state_round_trip() -> None:
    """The state survives a dict round trip and ignores unknown keys."""
    state = PIDState(integral=3.5, last_input=2, output=10)
    assert PIDState.from_dict({**state.as_dict(), "unknown": 1}) == state
