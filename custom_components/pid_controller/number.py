"""Number entities holding the PID controller parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, EntityCategory, UnitOfTime

from .const import (
    CONF_DERIVATIVE,
    CONF_INTEGRAL,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_PRECISION,
    CONF_PROPORTIONAL,
    CONF_SAMPLE_TIME,
    CONF_SET_POINT,
    CONF_WINDUP,
)
from .entity import PIDEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .controller import PIDConfigEntry

PARALLEL_UPDATES = 0

_LIMIT = 1_000_000


@dataclass(frozen=True, kw_only=True)
class PIDNumberEntityDescription(NumberEntityDescription):
    """Describes a PID controller parameter."""

    unit_from_source: bool = False


NUMBERS = (
    PIDNumberEntityDescription(
        key=CONF_SET_POINT,
        translation_key=CONF_SET_POINT,
        native_min_value=-_LIMIT,
        native_max_value=_LIMIT,
        native_step=0.01,
        unit_from_source=True,
    ),
    *(
        PIDNumberEntityDescription(
            key=key,
            translation_key=key,
            entity_category=EntityCategory.CONFIG,
            native_min_value=0,
            native_max_value=_LIMIT,
            native_step=0.0001,
        )
        for key in (CONF_PROPORTIONAL, CONF_INTEGRAL, CONF_DERIVATIVE)
    ),
    *(
        PIDNumberEntityDescription(
            key=key,
            translation_key=key,
            entity_category=EntityCategory.CONFIG,
            native_min_value=-_LIMIT,
            native_max_value=_LIMIT,
            native_step=0.01,
        )
        for key in (CONF_MINIMUM, CONF_MAXIMUM)
    ),
    PIDNumberEntityDescription(
        key=CONF_PRECISION,
        translation_key=CONF_PRECISION,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=6,
        native_step=1,
    ),
    PIDNumberEntityDescription(
        key=CONF_SAMPLE_TIME,
        translation_key=CONF_SAMPLE_TIME,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=86_400,
        native_step=1,
    ),
    PIDNumberEntityDescription(
        key=CONF_WINDUP,
        translation_key=CONF_WINDUP,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=1_000,
        native_step=0.1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PID controller parameters."""
    source_state = hass.states.get(entry.runtime_data.source_entity_id)
    source_unit = (
        source_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if source_state else None
    )
    async_add_entities(
        PIDNumber(entry, description, source_unit) for description in NUMBERS
    )


class PIDNumber(PIDEntity, RestoreNumber):
    """A PID controller parameter."""

    _attr_mode = NumberMode.BOX
    entity_description: PIDNumberEntityDescription

    def __init__(
        self,
        entry: PIDConfigEntry,
        description: PIDNumberEntityDescription,
        source_unit: str | None,
    ) -> None:
        """Initialize the parameter."""
        super().__init__(entry, description)
        if description.unit_from_source:
            self._attr_native_unit_of_measurement = source_unit

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last value into the controller."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._set(last.native_value)

    @property
    @override
    def native_value(self) -> float:
        """Return the parameter value."""
        return float(getattr(self.controller.parameters, self.entity_description.key))

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Change the parameter."""
        self._set(value)
        self.async_write_ha_state()

    def _set(self, value: float) -> None:
        key = self.entity_description.key
        self.controller.async_set_parameter(
            key, int(value) if key == CONF_PRECISION else float(value)
        )
