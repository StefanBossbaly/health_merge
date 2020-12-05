"""Tests for the sensor module."""
from pytest_homeassistant_custom_component.async_mock import AsyncMock, MagicMock

# from custom_components.health_merge.sensor import HealthMerge


async def test_async_update_success(hass, aioclient_mock):
    """Tests a fully successful async_update."""
    health_sensor1 = MagicMock()
    health_sensor1.state = AsyncMock()

    pass


async def test_async_update_failed():
    """Tests a failed async_update."""
    pass
