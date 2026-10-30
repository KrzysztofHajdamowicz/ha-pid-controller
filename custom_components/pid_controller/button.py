"""Button entities of the PID Controller integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory

from .entity import PIDEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .controller import PIDConfigEntry

PARALLEL_UPDATES = 0

RESET_DESCRIPTION = ButtonEntityDescription(
    key="reset", translation_key="reset", entity_category=EntityCategory.CONFIG
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PID controller buttons."""
    async_add_entities([PIDResetButton(entry, RESET_DESCRIPTION)])


class PIDResetButton(PIDEntity, ButtonEntity):
    """Reset the integral of the controller."""

    @override
    async def async_press(self) -> None:
        """Reset the controller."""
        self.controller.async_reset()
