"""Support for the Dynalite channels as covers."""
import asyncio

from .const import ATTR_POSITION, ATTR_TILT_POSITION, CONF_TEMPLATE, CONF_TIME_COVER
from .dynalitebase import DynaliteMultiDevice


class DynaliteTimeCoverDevice(DynaliteMultiDevice):
    """Representation of a Dynalite Channel as a Home Assistant Cover."""

    def __init__(self, area, bridge, poll_timer):
        """Initialize the cover."""
        self._current_position = 0
        self._direction = "stop"
        self._poll_timer = poll_timer
        super().__init__(4, area, bridge)

    @property
    def available(self):
        """Return if device is available."""
        return self._bridge.available(CONF_TEMPLATE, self._area, CONF_TIME_COVER)

    @property
    def category(self):
        """Return the category of the entity: light, switch, or cover."""
        return "cover"

    @property
    def unique_id(self):
        """Return the ID of this room switch."""
        return "dynalite_area_" + str(self._area) + "_time_cover"

    @property
    def has_tilt(self):
        """Return whether cover supports tilt."""
        return False

    @property
    def device_class(self):
        """Return the class of the cover."""
        return self._bridge.get_device_class(self._area)

    def update_level(self, actual_level, target_level):
        """Update the current level."""
        if actual_level == target_level:
            self._direction = "stop"
            self._bridge.remove_timer_listener(self.timer_callback)
        else:
            self._direction = "open" if target_level > actual_level else "close"
            self._bridge.add_timer_listener(self.timer_callback)
        self._bridge.update_device(self)

    def timer_callback(self):
        """Update the progress of open and close."""
        duration = self._bridge.get_cover_duration(self._area)
        assert self._direction in ["open", "close"]
        if self._direction == "open":
            self._current_position += self._poll_timer / duration
            getattr(self, "update_tilt", int)(self._poll_timer)
            if self._current_position >= 1.0:
                self._current_position = 1.0
                self._direction = "stop"
                self._bridge.remove_timer_listener(self.timer_callback)
        elif self._direction == "close":
            self._current_position -= self._poll_timer / duration
            getattr(self, "update_tilt", int)(self._poll_timer)
            if self._current_position <= 0.0:
                self._current_position = 0.0
                self._direction = "stop"
                self._bridge.remove_timer_listener(self.timer_callback)
        self._bridge.update_device(self)

    @property
    def current_cover_position(self):
        """Return the position of the cover from 0 to 100."""
        return int(self._current_position * 100)

    @property
    def is_opening(self):
        """Return whether cover is currently opening."""
        return self._direction == "open"

    @property
    def is_closing(self):
        """Return whether cover is currently closing."""
        return self._direction == "close"

    @property
    def is_closed(self):
        """Return whether cover is closed."""
        return self._current_position == 0

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.get_device(1).async_turn_on()
        self.update_level(self._current_position, 1.0)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.get_device(2).async_turn_on()
        self.update_level(self._current_position, 0.0)

    async def async_set_cover_position(self, **kwargs):
        """Set the cover to a specific position."""
        target_position = kwargs[ATTR_POSITION] / 100
        position_diff = target_position - self._current_position
        if position_diff > 0.001:
            await self.async_open_cover()
            while (
                self._current_position < target_position and self._direction == "open"
            ):
                await asyncio.sleep(self._poll_timer)
            if self._direction == "open":
                await self.async_stop_cover()
                await asyncio.sleep(self._poll_timer)  # doing twice for safety
                await self.async_stop_cover()
        elif position_diff < -0.001:
            await self.async_close_cover()
            while (
                self._current_position > target_position and self._direction == "close"
            ):
                await asyncio.sleep(self._poll_timer)
            if self._direction == "close":
                await self.async_stop_cover()
                await asyncio.sleep(self._poll_timer)  # doing twice for safety
                await self.async_stop_cover()
        else:
            await self.async_stop_cover()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.get_device(3).async_turn_on()
        self.update_level(self._current_position, self._current_position)

    def listener(self, device, stop_fade):
        """Update according to updates in underlying devices."""
        if device == self.get_device(1):
            if device.is_on:
                self.update_level(self._current_position, 1.0)
        elif device == self.get_device(2):
            if device.is_on:
                self.update_level(self._current_position, 0.0)
        elif device == self.get_device(3):
            if device.is_on:
                self.update_level(self._current_position, self._current_position)
        elif device == self.get_device(4):
            if stop_fade or device.direction == "stop":
                self.update_level(self._current_position, self._current_position)
            elif device.direction == "open":
                self.update_level(self._current_position, 1.0)
            else:
                self.update_level(self._current_position, 0.0)
        super().listener(device, stop_fade)


class DynaliteTimeCoverWithTiltDevice(DynaliteTimeCoverDevice):
    """Representation of a Dynalite Channel as a Home Assistant Cover that uses up and down for tilt."""

    def __init__(self, area, bridge, poll_timer):
        """Initialize the cover."""
        self._current_tilt = 0
        super().__init__(area, bridge, poll_timer)

    @property
    def has_tilt(self):
        """Return whether cover supports tilt."""
        return True

    def update_tilt(self, poll_timer):
        """Update the current tilt based on diff and tilt_percentage."""
        assert self._direction in ["open", "close"]
        if self._direction == "open":
            mult = poll_timer
        elif self._direction == "close":
            mult = -poll_timer
        tilt_duration = self._bridge.get_cover_tilt_duration(self._area)
        tilt_diff = mult / tilt_duration
        self._current_tilt = max(0, min(1, self._current_tilt + tilt_diff))

    @property
    def current_cover_tilt_position(self):
        """Return the current cover tilt."""
        return int(self._current_tilt * 100)

    async def apply_tilt_diff(self, tilt_diff):
        """Move the cover up or down based on a diff."""
        duration = self._bridge.get_cover_duration(self._area)
        tilt_duration = self._bridge.get_cover_tilt_duration(self._area)
        factor = tilt_duration / duration
        position_diff = tilt_diff * factor
        target_position = int(
            100 * max(0, min(1, self._current_position + position_diff))
        )
        await self.async_set_cover_position(position=target_position)

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        if self._current_tilt == 1:
            return
        await self.apply_tilt_diff(1 - self._current_tilt)

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        if self._current_tilt == 0:
            return
        await self.apply_tilt_diff(0 - self._current_tilt)

    async def async_set_cover_tilt_position(self, **kwargs):
        """Set the cover tilt position."""
        target_position = kwargs[ATTR_TILT_POSITION] / 100
        await self.apply_tilt_diff(target_position - self._current_tilt)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        await self.async_stop_cover()
