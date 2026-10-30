"""Select entities of the PID Controller integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_ROUND, RoundMode
from .entity import PIDEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .controller import PIDConfigEntry

PARALLEL_UPDATES = 0

ROUND_DESCRIPTION = SelectEntityDescription(
    key=CONF_ROUND,
    translation_key=CONF_ROUND,
    entity_category=EntityCategory.CONFIG,
    options=[mode.value for mode in RoundMode],
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PID controller selects."""
    async_add_entities([PIDRoundSelect(entry, ROUND_DESCRIPTION)])


class PIDRoundSelect(PIDEntity, SelectEntity, RestoreEntity):
    """How the output is rounded."""

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last value into the controller."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self.options:
            self.controller.async_set_parameter(CONF_ROUND, RoundMode(last.state))

    @property
    @override
    def current_option(self) -> str:
        """Return the rounding mode."""
        return self.controller.parameters.round.value

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the rounding mode."""
        self.controller.async_set_parameter(CONF_ROUND, RoundMode(option))
        self.async_write_ha_state()
