"""Base entity of the PID Controller integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, NAME

if TYPE_CHECKING:
    from .controller import PIDConfigEntry, PIDController


class PIDEntity(Entity):
    """Entity that belongs to one PID controller instance."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: PIDConfigEntry, description: EntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self.controller: PIDController = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=NAME,
            entry_type=DeviceEntryType.SERVICE,
        )
