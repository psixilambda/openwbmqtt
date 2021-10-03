"""The openwbmqtt component for controlling the openWB wallbox via home assistant / MQTT"""
from __future__ import annotations

import copy
from datetime import timedelta
import logging

from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)
from homeassistant.components import mqtt
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt, slugify

# Import global values.
from .const import (
    CHARGE_POINTS,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    MQTT_ROOT_TOPIC,
    SENSORS_GLOBAL,
    SENSORS_PER_LP,
    SENSORS_HOUSEBATTERY,
    openwbSensorEntityDescription,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors for openWB."""

    """Reuse data obtained in the configuration flow so that it can be used when setting up the entries.
    Data flow is config_flow.py --> data --> init.py --> hass.data --> sensor.py --> hass.data"""
    nChargePoints = hass.data[DOMAIN][config.entry_id][CHARGE_POINTS]
    mqttRoot = hass.data[DOMAIN][config.entry_id][MQTT_ROOT_TOPIC]
    integrationUniqueID = config.unique_id

    sensorList = []
    # Create all global sensors.
    global_sensors = copy.deepcopy(SENSORS_GLOBAL)
    for description in global_sensors:
        description.mqttTopic = f"{mqttRoot}/{description.key}"
        _LOGGER.debug("mqttTopic: %s", description.mqttTopic)
        sensorList.append(
            openwbSensor(uniqueID=integrationUniqueID, description=description)
        )
    # Create all housebattery sensors.
    housebattery_sensors = copy.deepcopy(SENSORS_HOUSEBATTERY)
    for description in housebattery_sensors:
        description.mqttTopic = f"{mqttRoot}/{description.key}"
        _LOGGER.debug("mqttTopic: %s", description.mqttTopic)
        sensorList.append(
            openwbSensor(uniqueID=integrationUniqueID, description=description)
        )
    # Create all sensors for each charge point, respectively.
    for chargePoint in range(1, nChargePoints + 1):
        local_sensors_per_lp = copy.deepcopy(SENSORS_PER_LP)
        for description in local_sensors_per_lp:
            description.mqttTopic = (
                f"{mqttRoot}/lp/{str(chargePoint)}/{description.key}"
            )
            _LOGGER.debug("mqttTopic: %s", description.mqttTopic)
            sensorList.append(
                openwbSensor(
                    uniqueID=integrationUniqueID,
                    description=description,
                    nChargePoints=int(nChargePoints),
                    currentChargePoint=chargePoint,
                )
            )

    async_add_entities(sensorList)


class openwbSensor(SensorEntity):
    """Representation of an openWB sensor that is updated via MQTT."""

    entity_description: openwbSensorEntityDescription

    def __init__(
        self,
        uniqueID: str | None,
        description: openwbSensorEntityDescription,
        nChargePoints: int | None = None,
        currentChargePoint: int | None = None,
    ) -> None:
        """Initialize the sensor."""
        # Group all sensors to one device. The device is identified by the prefix (which is unique).
        self._attr_device_info = {
            ATTR_NAME: uniqueID,
            ATTR_IDENTIFIERS: {(DOMAIN, uniqueID)},
            ATTR_MANUFACTURER : MANUFACTURER,
            ATTR_MODEL: MODEL,
        }
        self.entity_description = description
        if nChargePoints:
            self._attr_unique_id = slugify(
                f"{uniqueID}-CP{currentChargePoint}-{description.name}"
            )
            self.entity_id = f"sensor.{uniqueID}-CP{currentChargePoint}-{description.name}"
            self._attr_name = f"{description.name} (LP{currentChargePoint})"
        else:
            self._attr_unique_id = slugify(f"{uniqueID}-{description.name}")
            self.entity_id = f"sensor.{uniqueID}-{description.name}"
            self._attr_name = description.name

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)
            else:
                self._attr_native_value = message.payload

            # Map values as defined in the value map dict.
            if self.entity_description.valueMap is not None:
                try:
                    self._attr_native_value = self.entity_description.valueMap.get(
                        int(self._attr_native_value)
                    )
                except ValueError:
                    self._attr_native_value = self._attr_native_value

            # Reformat TimeRemaining --> timestamp.
            if "TimeRemaining" in self.entity_description.key:
                now = dt.utcnow()
                if "H" in self._attr_native_value:
                    tmp = self._attr_native_value.split()
                    delta = timedelta(hours = int(tmp[0]), minutes = int(tmp[2]))
                    self._attr_native_value = now + delta
                elif "Min" in self._attr_native_value:
                    tmp = self._attr_native_value.split()
                    delta = timedelta(minutes = int(tmp[0]))
                    self._attr_native_value = now + delta
                else:
                    self._attr_native_value = None

            # Update entity state with value published on MQTT.
            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self.entity_description.mqttTopic, message_received, 1
        )
