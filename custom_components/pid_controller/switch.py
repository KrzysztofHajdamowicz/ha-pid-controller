"""Switches of the PID Controller integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_ENABLED, CONF_INVERT
from .entity import PIDEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .controller import PIDConfigEntry

PARALLEL_UPDATES = 0

SWITCHES = (
    SwitchEntityDescription(key=CONF_ENABLED, translation_key=CONF_ENABLED),
    SwitchEntityDescription(
        key=CONF_INVERT,
        translation_key=CONF_INVERT,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PID controller switches."""
    async_add_entities(PIDSwitch(entry, description) for description in SWITCHES)


class PIDSwitch(PIDEntity, SwitchEntity, RestoreEntity):
    """A boolean PID controller parameter."""

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last value into the controller."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.controller.async_set_parameter(
                self.entity_description.key, last.state == STATE_ON
            )

    @property
    @override
    def is_on(self) -> bool:
        """Return the parameter value."""
        return bool(getattr(self.controller.parameters, self.entity_description.key))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the parameter on."""
        self.controller.async_set_parameter(self.entity_description.key, value=True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the parameter off."""
        self.controller.async_set_parameter(self.entity_description.key, value=False)
        self.async_write_ha_state()
