"""Diagnostics of the PID Controller integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .controller import PIDConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PIDConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data
    return {
        "options": dict(entry.options),
        "parameters": controller.parameters.as_dict(),
        "pid": controller.pid.state.as_dict(),
        "output": controller.output,
        "source": {
            "entity_id": controller.source_entity_id,
            "value": controller.source_value,
            "available": controller.source_available,
        },
        "last_update": controller.last_update.isoformat()
        if controller.last_update
        else None,
    }
