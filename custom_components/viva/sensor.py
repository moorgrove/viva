"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinator
from .const import DOMAIN

SENSOR_TYPE_WIND = "wind"
SENSOR_TYPE_WIND_DIRECTION = "wind_direction"
SENSOR_TYPE_LEVEL = "level"
SENSOR_TYPE_WATER_TEMP = "watertemp"

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViVaSensorDescription(SensorEntityDescription):
    """Class describing ViVa sensor entities."""

    type: str | None = None
    convert: Callable[[Any], Any] | None = None
    decimals: int = 1


LEVEL_SENSOR = ViVaSensorDescription(
    key="Vattenstånd",
    type=SENSOR_TYPE_LEVEL,
    device_class=SensorDeviceClass.DISTANCE,
    name="Vattenstånd",
    icon="mdi:ferry",
    native_unit_of_measurement=UnitOfLength.CENTIMETERS,
    state_class=SensorStateClass.MEASUREMENT,
)

AVG_WIND_DIRECTION_SENSOR = ViVaSensorDescription(
    key="Vindriktning",
    type=SENSOR_TYPE_WIND_DIRECTION,
    icon="mdi:compass-outline",
    name="Vindriktning",
    native_unit_of_measurement="",
)

AVG_WIND_SENSOR = ViVaSensorDescription(
    key="Medelvind",
    type=SENSOR_TYPE_WIND,
    device_class=SensorDeviceClass.WIND_SPEED,
    name="Medelvind",
    native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    state_class=SensorStateClass.MEASUREMENT,
)

GUST_WIND_SENSOR = ViVaSensorDescription(
    key="Byvind",
    type=SENSOR_TYPE_WIND,
    device_class=SensorDeviceClass.WIND_SPEED,
    name="Byvind",
    native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    state_class=SensorStateClass.MEASUREMENT,
)

TEMP_SENSOR = ViVaSensorDescription(
    key="Vattentemp",
    type=SENSOR_TYPE_WATER_TEMP,
    device_class=SensorDeviceClass.TEMPERATURE,
    name="Vattentemp",
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = await get_coordinator(hass, config_entry)

    entities = []
    for idx, obs in enumerate(coordinator.data["Samples"]):
        obs2 = coordinator.data["Samples"][obs]
        if obs2["Type"] == SENSOR_TYPE_LEVEL:
            entities.append(ViVaSensor(coordinator, LEVEL_SENSOR, obs))
        elif obs2["Type"] == SENSOR_TYPE_WIND and obs2["Name"] == "Medelvind":
            entities.append(ViVaSensor(coordinator, AVG_WIND_SENSOR, obs))
            entities.append(ViVaSensor(coordinator, AVG_WIND_DIRECTION_SENSOR, obs))
        elif obs2["Type"] == SENSOR_TYPE_WIND and obs2["Name"] == "Byvind":
            entities.append(ViVaSensor(coordinator, GUST_WIND_SENSOR, obs))
        elif obs2["Type"] == SENSOR_TYPE_WATER_TEMP:
            entities.append(ViVaSensor(coordinator, TEMP_SENSOR, obs))
        else:
            _LOGGER.warning(
                "Unsupported sensor type %s on station %s",
                obs2["Type"],
                obs2["StationID"],
            )
            continue
        _LOGGER.debug(
            "Setting up sensor %s on station %s", obs2["Type"], obs2["StationID"]
        )
    async_add_entities(entities)


class ViVaSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: ViVaSensorDescription
    sensor_id: str = ""

    def __init__(self, coordinator, description: ViVaSensorDescription, sensor_id: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.sensor_id = sensor_id
        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"{self.coordinator.data['ID']}-{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data["ID"])},
            name=self.coordinator.data["Name"],
            manufacturer="Sjöfartsverket",
            model="ViVa",
            configuration_url="https://geokatalog.sjofartsverket.se/kartvisarefyren/",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""

        retstr = self.coordinator.data["Samples"][self.sensor_id].get("Value")

        if self.entity_description.type == SENSOR_TYPE_WIND:
            retval = retstr.split()
            return retval[1]

        if self.entity_description.type == SENSOR_TYPE_WIND_DIRECTION:
            retval = retstr.split()
            return retval[0]

        return retstr

    @property
    def available(self):
        """Return the availability of the entity."""

        return (
            self.coordinator.last_update_success
            and "Samples" in self.coordinator.data
            and self.sensor_id in self.coordinator.data["Samples"]
        )
