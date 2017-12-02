from .switch import Switch
from xml.etree import cElementTree as et
from pywemo.ouimeaux_device.api.xsd.device import quote_xml

import sys
if sys.version_info[0] < 3:
	class IntEnum(object):
		pass
else:
	from enum import IntEnum

# These enums were derived from the Humidifier.deviceevent.GetAttributeList() service call
# Thus these names/values were not chosen randomly and the numbers have meaning.
class FanMode(IntEnum):
	Off = 0 # Fan and device turned off
	Minimum = 1
	Low = 2
	Medium = 3
	High = 4
	Maximum = 5

fanModeNames = {
	FanMode.Off: "Off",
	FanMode.Minimum: "Minimum",
	FanMode.Low: "Low",
	FanMode.Medium: "Medium",
	FanMode.High: "High",
	FanMode.Maximum: "Maximum",
}

DesiredHumidity = IntEnum(
	value = 'DesiredHumidity',
	names = [
		('45', 0),
		('50', 1),
		('55', 2),
		('60', 3),
		('100', 4), # "Always On" mode
	]
)

desiredHumidityNames = {
	DesiredHumidity['45']: "45",
	DesiredHumidity['50']: "50",
	DesiredHumidity['55']: "55",
	DesiredHumidity['60']: "60",
	DesiredHumidity['100']: "100",
}

class WaterLevel(IntEnum):
	Empty = 0
	Low = 1
	Good = 2

waterLevelNames = {
	WaterLevel.Empty: "Empty",
	WaterLevel.Low: "Low",
	WaterLevel.Good: "Good",
}

def attributeXmlToDict(xmlBlob):
	"""
	Returns attribute values as a dict of key value pairs.
	"""
	xmlBlob = "<attributes>" + xmlBlob + "</attributes>"
	xmlBlob = xmlBlob.replace("&gt;", ">")
	xmlBlob = xmlBlob.replace("&lt;", "<")
	result = {}
	attributes = et.fromstring(xmlBlob)
	
	result["WaterLevel"] = int(2)
	
	for attribute in attributes:
		if attribute[0].text == "FanMode":
			try:
				result["FanMode"] = int(attribute[1].text)
			except ValueError:
				pass
		elif attribute[0].text == "DesiredHumidity":
			try:
				result["DesiredHumidity"] = int(attribute[1].text)
			except ValueError:
				pass
		elif attribute[0].text == "CurrentHumidity":
			try:
				result["CurrentHumidity"] = float(attribute[1].text)
			except ValueError:
				pass
		elif attribute[0].text == "NoWater" and attribute[1].text == "1":
			try:
				result["WaterLevel"] = int(0)
			except ValueError:
				pass
		elif attribute[0].text == "WaterAdvise" and attribute[1].text == "1":
			try:
				result["WaterLevel"] = int(1)
			except ValueError:
				pass
		elif attribute[0].text == "FilterLife":
			try:
				result["FilterLife"] = float(round((float(attribute[1].text) / float(60480)) * float(100), 2))
			except ValueError:
				pass
		elif attribute[0].text == "ExpiredFilterTime":
			try:
				result["FilterExpired"] = bool(int(attribute[1].text))
			except ValueError:
				pass
	
	return result


class Humidifier(Switch):
	def __init__(self, *args, **kwargs):
		Switch.__init__(self, *args, **kwargs)
		self._attributes = {}
		self.update_attributes()

	def __repr__(self):
		return '<WeMo Humidifier "{name}">'.format(name=self.name)

	def update_attributes(self):
		"""
		Request state from device
		"""
		resp = self.deviceevent.GetAttributes().get('attributeList')
		self._attributes = attributeXmlToDict(resp)
		self._state = self.fanMode

	def subscription_update(self, _type, _params):
		"""
		Handle reports from device
		"""
		if _type == "attributeList":
			self._attributes.update(attributeXmlToDict(_params))
			self._state = self.fanMode
			
			return True

		return Switch.subscription_update(self, _type, _params)

	@property
	def fanMode(self):
		return self._attributes.get('FanMode')

	@property
	def fanMode_string(self):
		return fanModeNames.get(self.fanMode, "Unknown")
	
	@property
	def desiredHumidity(self):
		return self._attributes.get('DesiredHumidity')

	@property
	def desiredHumidity_percent(self):
		return desiredHumidityNames.get(self.desiredHumidity, "Unknown")
	
	@property
	def currentHumidity_percent(self):
		return self._attributes.get('CurrentHumidity')
	
	@property
	def waterLevel(self):
		return self._attributes.get('WaterLevel')

	@property
	def waterLevel_string(self):
		return waterLevelNames.get(self.waterLevel, "Unknown")
	
	@property
	def filterLife_percent(self):
		return self._attributes.get('FilterLife')
	
	@property
	def filterExpired(self):
		return self._attributes.get('FilterExpired')

	def get_state(self, force_update=False):
		"""
		Returns 0 if off and 1 if on.
		"""
		# The base implementation using GetBinaryState doesn't work for Humidifier (always returns 0)
		# so use fan mode instead.
		if force_update or self._state is None:
			self.update_attributes()

		# Consider the Humidifier to be "on" if it's not off.
		return int(self._state != FanMode.Off)

	def set_state(self, fanMode, desiredHumidity):
		"""
		Set the fanMode and desiredHumidity of this device.
		"""
		
		# Set some defaults
		fanModeInt = 0
		desiredHumidityInt = 0
		
		# Figure out if we get values coming in as ints or enums
		if type(fanMode) == "FanMode":
			fanModeInt = fanMode.value
		else:
			fanModeInt = int(fanMode)
		
		if type(desiredHumidity) == "DesiredHumidity":
			desiredHumidityInt = desiredHumidity.value
		else:
			desiredHumidityInt = int(desiredHumidity)
		
		# Send the attribute list to the device
		self.deviceevent.SetAttributes(attributeList =
			quote_xml("<attribute><name>FanMode</name><value>" + str(fanModeInt) + "</value></attribute><attribute><name>DesiredHumidity</name><value>" + str(desiredHumidityInt) + "</value></attribute>"))
		
		# Refresh the device state		
		self.get_state(True)
