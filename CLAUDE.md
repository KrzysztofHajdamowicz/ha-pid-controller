# ha-pid-controller

Home Assistant custom integration (domain `pid_controller`): a multi-instance PID controller helper set up with a config flow. Maintained fork of soloam/ha-pid-controller.

## Layout

- `custom_components/pid_controller/pid.py`: the PID algorithm, no Home Assistant imports. Works on a 0..100 % scale.
- `controller.py`: `PIDController` (the `runtime_data` of a config entry) reads the source, runs the PID on the sample timer and on source changes, maps the output onto minimum..maximum and notifies the entities. Parameters live in the frozen `PIDParameters` dataclass; entities change them through `async_set_parameter`.
- Platform modules (`number`, `switch`, `select`, `button`, `sensor`) only expose and restore parameters. The output sensor also stores the PID state (`PIDExtraStoredData`) for a bumpless restart.
- `legacy.py` + `sensor.async_setup_platform`: one-time import of the v1 YAML platform, with a repair issue.

## Conventions

- Branch `dev` is the default; every change goes through a PR into `dev`. Commit messages are imperative and in English.
- Home Assistant 2026.9 is the minimum (Probatio replaced voluptuous there). Use `probatio`, not `voluptuous`. Keep it in sync in `hacs.json` and the `test-minimum` CI job.
- Translations: `translations/en.json` is the source (no `strings.json`), keep `pl.json` complete.
- Checks: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`, coverage ≥ 95 %. `uv run python -I scripts/smoke_test.py` boots real Home Assistant.
- Never add Home Assistant itself to the dev dependencies: `pytest-homeassistant-custom-component` pins the matching release.
