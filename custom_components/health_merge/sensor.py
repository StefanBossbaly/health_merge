"""Platform for sensor integration."""
import logging
from typing import Any, Callable, Dict, Iterator, List, Optional

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_SENSORS, STATE_UNAVAILABLE
from homeassistant.core import State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import voluptuous as vol

from .const import (
    ATTR_STATUS,
    ATTR_STATUS_NO_PROBLEM_VAL,
    CONF_HEALTH_SENSORS,
    STATE_BAD,
    STATE_CRITICAL,
    STATE_GOOD,
    STATE_WARN,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Health Sensor"

HEALTH_SENSOR_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_HEALTH_SENSORS): cv.entity_ids,
        }
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(HEALTH_SENSOR_SCHEMA)
    }
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info=None
) -> None:
    """Set up the health merge sensors."""

    health_sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        sensors = device_config[CONF_HEALTH_SENSORS]
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)

        _LOGGER.debug(f"Added health_merge sensor: {device}: {device_config}")

        health_sensors.append(
            HealthMergeSensor(
                device,
                friendly_name,
                sensors
            )
        )

    async_add_entities(health_sensors)


def _find_state_attributes(states: List[State], key: str) -> Iterator[str]:
    """Find attributes with matching key from states."""
    for state in states:
        value = state.attributes.get(key)
        if value is not None:
            yield value


class HealthMergeSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, device_id: str, friendly_name: str, sensor_ids: List[str]) -> None:
        """Initialize the sensor."""

        self._name = friendly_name
        self._sensor_ids = sensor_ids
        self._available = False
        self._state = None
        self._async_unsub_state_changed = None

        self._attr_status = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(
            entity_id: str, old_state: State, new_state: State
        ) -> None:
            """Handle child updates."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_state_changed = async_track_state_change(
            self.hass, self._sensor_ids, async_state_changed_listener
        )
        await self.async_update()

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal from HASS."""
        if self._async_unsub_state_changed is not None:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return whether the merge sensor is available."""
        return self._available

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self) -> bool:
        """Disable polling for group."""
        return False

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attrs = {}

        if self._attr_status is not None:
            attrs[ATTR_STATUS] = self._attr_status

        return attrs

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        # Get a list of sensors that are valid
        raw_sensors = [self.hass.states.get(sensor_id) for sensor_id in self._sensor_ids]
        health_sensors = list(filter(None, raw_sensors))

        # Set available
        self._available = any(health_sensor.state != STATE_UNAVAILABLE for health_sensor in health_sensors)

        # Check to see if there are any bad healths
        for current_health_state in (STATE_CRITICAL, STATE_BAD, STATE_WARN):
            # Get a list of health states at the current level
            current_health_sensors = [health_sensor for health_sensor in health_sensors if health_sensor.state == current_health_state]

            # See if there are any sensors at this level
            if current_health_sensors:
                # Set the health state
                self._state = current_health_state

                # Find any status at this health status
                status_attributes = list(_find_state_attributes(current_health_sensors, ATTR_STATUS))

                # Collapse any status attributes at this health state
                if status_attributes:
                    self._attr_status = "\n".join(status_attributes)
                else:
                    self._attr_status = None

                # We found the state, no need to keep processing
                return

        # No error states were detected
        self._state = STATE_GOOD
        self._attr_status = ATTR_STATUS_NO_PROBLEM_VAL
