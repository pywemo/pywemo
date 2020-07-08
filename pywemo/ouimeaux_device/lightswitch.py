"""Representation of a WeMo LightSwitch device."""

import logging
from .switch import Switch

LOG = logging.getLogger(__name__)


class LightSwitch(Switch):
    """Representation of a WeMo LightSwitch device."""

    def subscription_update(self, _type, _params):
        """Update device state based on subscription event."""
        LOG.debug("subscription_update %s %s", _type, _params)
        if _type == "BinaryState":
            try:
                self._state = int(_params)
            except ValueError:
                LOG.error(
                    "Could not parse BinaryState update '%s': %s", _params, e)
                self._state = 0
            return True
        return False

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo LightSwitch "{name}">'.format(name=self.name)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "LightSwitch"
