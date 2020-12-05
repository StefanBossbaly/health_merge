"""Platform for sensor integration."""
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_PLATFORM,
    CONF_SENSORS,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
import voluptuous as vol

from .const import (
    ATTR_STATUS,
    CONF_HEALTH_SENSORS,
    DOMAIN,
    PLATFORMS,
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
    hass: HomeAssistant,
    config: Dict[str, Union[str, bool]],
    async_add_entities: Callable, 
    discovery_info=None
) -> None:
    """Set up the health merge sensors."""

    health_sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        sensors = device_config[CONF_HEALTH_SENSORS]
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)

        _LOGGER.info(f"Added health_merge sensor: {device}: {device_config}")

        health_sensors.append(
            HealthMerge(
                device,
                friendly_name,
                sensors
            )
        )
    
    async_add_entities(health_sensors)


class HealthMerge(Entity):
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
    def device_state_attributes(self) -> Dict[str, str]:
        """Return the state attributes."""
        attrs = {}

        if self._attr_status is not None:
            attrs[ATTR_STATUS] = self._attr_status

        return attrs

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        raw_states = [self.hass.states.get(sensor_id) for sensor_id in self._sensor_ids]
        states = list(filter(None, raw_states))
        all_healths = [state.state for state in states]

        for health_state in (STATE_CRITICAL, STATE_BAD, STATE_WARN, STATE_GOOD):
            if health_state in all_healths:
                raw_status_attributes = [state.attributes.get(ATTR_STATUS, None) for state in states if state.state == health_state]
                status_attributes = list(filter(None, raw_status_attributes))
                
                self._available = True
                self._state = health_state

                if len(status_attributes) > 0:
                    self._attr_status = "\n".join(status_attributes)
                else:
                    self._attr_status = None

                return
        
        self._available = True