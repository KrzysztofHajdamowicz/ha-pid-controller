# PID Controller for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![CI][ci-shield]][ci]
[![License][license-shield]](LICENSE.md)
[![HACS][hacs-shield]][hacs]

*Please :star: this repo if you find it useful.*

A PID controller helper: it reads a numeric entity (a temperature, PM2.5 or humidity sensor) and calculates an output that drives it towards a set point. Use the output to set a fan speed, a valve position, a heater power or anything else that takes a number.

[![Open your Home Assistant instance and open this repository in the Home Assistant Community Store.][hacs-button]][hacs-link]
[![Open your Home Assistant instance and start setting up a new PID controller.][setup-button]][setup-link]

> **Maintained fork.** This is the maintained continuation of [soloam/ha-pid-controller](https://github.com/soloam/ha-pid-controller), which is no longer updated. Thanks to Diogo Silva ([@soloam](https://github.com/soloam)) for the original integration.

![PID graph][pid-graph]

## Breaking changes in v2.0.0

- The controller is set up in the UI (**Settings → Devices & services → Helpers → Create helper → PID Controller**). The `sensor: - platform: pid_controller` YAML configuration is **imported automatically** on the first start and then has to be removed, see [Migrating from v1](#migrating-from-v1-yaml).
- The set point, gains and limits are entities of the controller instead of templates.
- The `pid_controller.reset_pid` and `pid_controller.autotune_pid` actions are gone: use the **Reset** button. Autotune never worked.
- Requires Home Assistant 2026.9 or newer.

## Installation

### Home Assistant Community Store (recommended)

1. Click the **Open in HACS** button above, or add `https://github.com/KrzysztofHajdamowicz/ha-pid-controller` as a custom repository of type *Integration*.
2. Download **PID Controller** and restart Home Assistant.
3. Click the **Add helper** button above, or go to **Settings → Devices & services → Helpers → Create helper → PID Controller**.

### Manual installation

1. Download `pid_controller.zip` from the [latest release][releases].
2. Unpack it into `<config>/custom_components/pid_controller/`.
3. Restart Home Assistant and add the helper as described above.

## Configuration

Each controller is its own config entry; add as many as you need. The setup asks for:

- **Name**\
  Name of the controller device. The output sensor takes this name, so *Air purifier PID* becomes `sensor.air_purifier_pid`.
- **Source entity**\
  The measured value: a `sensor`, `number` or `input_number` entity.
- **Output unit of measurement** (optional)\
  Unit of the output sensor, for example `%`.
- **Initial values** (optional)\
  Starting set point, gains and output range. They can be changed later on the device page.

The source entity and the output unit can be changed later with **Configure** on the controller.

### Entities

| Entity | Category | Description |
|---|---|---|
| Output (`sensor.<name>`) | | The controller output between minimum and maximum. Attributes `source` and `source_available` show the value used for the last calculation. |
| Set point | | The value the source should reach. Takes the unit of the source. |
| Enabled | | When off, the output is the minimum and the controller is paused. |
| Proportional / Integral / Derivative gain | Configuration | The P, I and D gains. All three at 0 turn the controller into an on/off switch. |
| Minimum / Maximum | Configuration | The output range. |
| Precision | Configuration | Number of decimals of the output; 0 gives whole numbers. |
| Rounding | Configuration | Round, floor or ceil to the precision. |
| Sample time | Configuration | Seconds between calculations (see below). 0 calculates on every change of the source. |
| Windup limit | Configuration | Limits the integral term to ± this many percent; 0 means no limit. |
| Invert | Configuration | Turn on when a higher output lowers the source, e.g. a fan or an air purifier. |
| Reset | Configuration | Forget the integral and start over. |
| Proportional / Integral / Derivative term, Error | Diagnostic | The parts of the last calculation, disabled by default. |

All values are restored after a restart, including the integral, so the output continues where it left off.

## How it works

The controller calculates on a 0–100 % scale and maps the result onto *minimum*–*maximum*:

```
error  = set point − source
output = P·error + I·∑(error·Δt) + D·d(−source)/dt      (clamped to 0..100 %)
state  = minimum + (maximum − minimum) · output / 100   (rounded to the precision)
```

Gains tuned with v1 keep working, because v1 used the same scale.

- **When it calculates.** Every *sample time* seconds, so the integral keeps working while the source does not change, and on changes of the source once a sample time has passed since the last calculation. Changing any of the controller entities recalculates at once.
- **Derivative on measurement.** The derivative reacts to changes of the source only, so moving the set point does not cause a jump.
- **Anti-windup.** The integral stops growing while the output is at 0 or 100 % and the error would push it further, and is limited by the windup limit.
- **Unavailable source.** While the source is `unavailable`, `unknown` or not a number, the controller pauses and the output keeps its last value. This is logged once when it happens and once when the source is back.

### Tuning

Start with only P, as in the graphs below from the original tutorial: increase P until the source oscillates around the set point, halve it, then add I until the remaining offset disappears in a reasonable time. D is rarely needed for slow processes such as room temperature or air quality.

| P only | Adding I | Adding D | Tuned |
|---|---|---|---|
| ![Phase 1][phase-1] | ![Phase 2][phase-2] | ![Phase 3][phase-3] | ![Phase 4][phase-4] |

## Example: air purifier

A controller *Air purifier PID* with the PM2.5 sensor as source, set point 10, **Invert** on, minimum 0, maximum 14 and precision 0 outputs the favorite level of the purifier:

```yaml
automation:
  - alias: "Air purifier follows the PID controller"
    triggers:
      - trigger: state
        entity_id: sensor.air_purifier_pid
    actions:
      - action: number.set_value
        target:
          entity_id: number.air_purifier_favorite_level
        data:
          value: "{{ states('sensor.air_purifier_pid') }}"

  - alias: "Quieter air purifier at night"
    triggers:
      - trigger: time
        at: "22:00:00"
    actions:
      - action: number.set_value
        target:
          entity_id: number.air_purifier_pid_maximum
        data:
          value: 6
```

## Migrating from v1 (YAML)

On the first start with v2, every `platform: pid_controller` sensor is imported into a controller with the same name, so the output keeps its entity ID (for example `sensor.oczyszczacz_salon_pid`). Each template is rendered once and its current value becomes the starting value of the matching entity; a repair issue lists what was imported.

Then:

1. Remove the `platform: pid_controller` entries (and a bare `pid_controller:` line, if you had one) from your YAML and restart.
2. Update automations and dashboards that changed the old `input_number`/`input_boolean`/`input_select` helpers: change the controller entities instead, for example `number.<name>_maximum` instead of `input_number.pid_maximum`.
3. Delete the helpers you no longer need.

## Known limitations

- The output is a sensor. Use an automation to apply it to the device you control.
- The output range is 0 % or more. For heating and cooling with one controller, use two controllers, one inverted.

## Troubleshooting

- Enable debug logging for `custom_components.pid_controller` and check the **Proportional / Integral / Derivative term** diagnostic entities to see how the output is made up.
- Download the diagnostics of the controller (**⋮ → Download diagnostics**) when opening an [issue][issues].

## Removal

Delete the controller in **Settings → Devices & services → Helpers**, then remove the integration in HACS and restart Home Assistant.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE.md). Original work © Diogo Silva (@soloam), maintained by Krzysztof Hajdamowicz.

[ci]: https://github.com/KrzysztofHajdamowicz/ha-pid-controller/actions/workflows/ci.yml
[ci-shield]: https://img.shields.io/github/actions/workflow/status/KrzysztofHajdamowicz/ha-pid-controller/ci.yml?branch=dev&style=popout
[hacs]: https://hacs.xyz
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=popout
[hacs-button]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-link]: https://my.home-assistant.io/redirect/hacs_repository/?owner=KrzysztofHajdamowicz&repository=ha-pid-controller&category=integration
[setup-button]: https://my.home-assistant.io/badges/config_flow_start.svg
[setup-link]: https://my.home-assistant.io/redirect/config_flow_start/?domain=pid_controller
[issues]: https://github.com/KrzysztofHajdamowicz/ha-pid-controller/issues
[license-shield]: https://img.shields.io/github/license/KrzysztofHajdamowicz/ha-pid-controller.svg?style=popout
[releases]: https://github.com/KrzysztofHajdamowicz/ha-pid-controller/releases
[releases-shield]: https://img.shields.io/github/release/KrzysztofHajdamowicz/ha-pid-controller.svg?style=popout
[pid-graph]: resources/pid_graph.png
[phase-1]: resources/pip_phase1.png
[phase-2]: resources/pip_phase2.png
[phase-3]: resources/pip_phase3.png
[phase-4]: resources/pip_phase4.png
