"""Sensors of the PID Controller integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    EntityCategory,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
import probatio

from .const import CONF_SOURCE, DOMAIN
from .entity import PIDEntity
from .legacy import LEGACY_TEMPLATE_KEYS, async_convert_legacy_config
from .pid import PIDState

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
        AddEntitiesCallback,
    )
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

    from .controller import PIDConfigEntry, PIDController

PARALLEL_UPDATES = 0

# Schema of the legacy YAML platform (v1), only used to import it.
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_NAME, default="PID Controller"): cv.string,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
        probatio.Required(CONF_ENTITY_ID): cv.entity_id,
        probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        probatio.Optional(CONF_ICON): cv.template,
        probatio.Optional(CONF_DEVICE_CLASS): cv.template,
        **{probatio.Optional(key): cv.template for key in LEGACY_TEMPLATE_KEYS},
    }
)


@dataclass(frozen=True, kw_only=True)
class PIDSensorEntityDescription(SensorEntityDescription):
    """Describes a PID controller sensor."""

    value_fn: Callable[[PIDController], float | None]


def _term(name: str) -> Callable[[PIDController], float | None]:
    return lambda controller: getattr(controller.pid.state, name)


DIAGNOSTIC_SENSORS = tuple(
    PIDSensorEntityDescription(
        key=key,
        translation_key=key,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_term(key),
    )
    for key in ("p_term", "i_term", "d_term", "error")
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: PIDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PID controller sensors."""
    async_add_entities(
        [
            PIDOutputSensor(entry),
            *(PIDDiagnosticSensor(entry, desc) for desc in DIAGNOSTIC_SENSORS),
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,  # noqa: ARG001
    discovery_info: DiscoveryInfoType | None = None,  # noqa: ARG001
) -> None:
    """Import a controller from the legacy YAML sensor platform."""
    import_data, warnings = await async_convert_legacy_config(hass, config)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )
    imported = result.get("type") == "create_entry"
    name = import_data[CONF_NAME]
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_{import_data[CONF_SOURCE]}_{name}",
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml" if imported else "deprecated_yaml_exists",
        translation_placeholders={
            "name": name,
            "warnings": "\n".join(f"- {warning}" for warning in warnings) or "-",
        },
    )


class PIDOutputSensor(PIDEntity, SensorEntity, RestoreEntity):
    """The controller output."""

    _attr_name = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "output"

    def __init__(self, entry: PIDConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry, SensorEntityDescription(key="output"))
        self._attr_native_unit_of_measurement = entry.options.get(
            CONF_UNIT_OF_MEASUREMENT
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the controller state and follow its updates."""
        await super().async_added_to_hass()
        if (extra := await self.async_get_last_extra_data()) is not None:
            data = extra.as_dict()
            self.controller.async_restore(
                PIDState.from_dict(data.get("pid", {})), data.get("output")
            )
        self.async_on_remove(self.controller.async_add_listener(self._on_update))

    @property
    @override
    def native_value(self) -> float | None:
        """Return the controller output."""
        return self.controller.output

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the source value used by the controller."""
        return {
            "source": self.controller.source_value,
            "source_available": self.controller.source_available,
        }

    @property
    @override
    def extra_restore_state_data(self) -> PIDExtraStoredData:
        """Return the PID state to restore after a restart."""
        return PIDExtraStoredData(self.controller.output, self.controller.pid.state)

    @callback
    def _on_update(self) -> None:
        self.async_write_ha_state()


class PIDDiagnosticSensor(PIDEntity, SensorEntity):
    """A term of the PID calculation."""

    entity_description: PIDSensorEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the controller updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.async_add_listener(self._on_update))

    @property
    @override
    def native_value(self) -> float | None:
        """Return the term."""
        return self.entity_description.value_fn(self.controller)

    @callback
    def _on_update(self) -> None:
        self.async_write_ha_state()


@dataclass(slots=True)
class PIDExtraStoredData(ExtraStoredData):
    """Output and PID state stored across restarts."""

    output: float | None
    pid: PIDState

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the data."""
        return {"output": self.output, "pid": self.pid.as_dict()}
