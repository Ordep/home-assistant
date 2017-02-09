import logging
from datetime import timedelta, datetime

import urllib
import requests
import voluptuous as vol

from xml.dom import minidom
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
import ssl

_LOGGER = logging.getLogger(__name__)

ATTR_STATION = "Station"
ATTR_ORIGIN = "Origin"
ATTR_LAST_LOCATION = "Last location"
ATTR_DESTINATION = "Destination"
ATTR_DIRECTION = "Direction"
ATTR_DUE_IN = "Due in"
ATTR_DUE_AT = "Due at"
ATTR_EXPECTED_AT = "Expected at"
ATTR_STATUS = "Status"
ATTR_NEXT_UP = "Later Train"

CONF_ATTRIBUTION = "Data provided by api.irishrail.ie"
CONF_STATION = 'station'
CONF_DIRECTION = 'direction'

DEFAULT_NAME = 'Next Train'
ICON = 'mdi:train'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): cv.string,
    vol.Optional(CONF_DIRECTION, default=None): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})

def _parse_station_data(url):
    attr_map = {
        'origin': 'Origin',
        'destination': 'Destination',
        'last_location': 'Lastlocation',
        'due_in_mins': 'Duein',
        'status': 'Status',
        'scheduled_arrival_time': 'Schdepart',
        'expected_departure_time': 'Expdepart',
        'direction': 'Direction',
    }
    return _parse(url, 'objStationData', attr_map)


def _parse(url, obj_name, attr_map):
    data = requests.get(url).content
    parsed_xml = minidom.parseString(data)
    parsed_objects = []
    for obj in parsed_xml.getElementsByTagName(obj_name):
        parsed_obj = {}
        for (py_name, xml_name) in attr_map.items():
            tag = obj.getElementsByTagName(xml_name)[0].firstChild
            parsed_obj[py_name] = tag.nodeValue if tag else None
        parsed_objects.append(parsed_obj)
    return parsed_objects


def setup_platform(hass, config, add_devices, discovery_info=None):
    station = config.get(CONF_STATION)
    direction = config.get(CONF_DIRECTION)
    name = config.get(CONF_NAME)

    data = IrishRailTransportData(station, direction)
    add_devices([IrishRailTransportSensor(data, station, direction, name)])


class IrishRailTransportSensor(Entity):

    def __init__(self, data, station, direction, name):
        """Initialize the sensor."""
        self.data = data
        self._station = station
        self._direction = direction
        self._name = name
        self.update()

    @property
    def station(self):
        """Return the station of the sensor."""
        return self._station

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "min"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if len(self._times) > 0:
            next_up = "None"
            if len(self._times) > 1:
                next_up = self._times[1][ATTR_ORIGIN] + " to "
                next_up += self._times[1][ATTR_DESTINATION] + " in "
                next_up += self._times[1][ATTR_DUE_IN]

            return {
                ATTR_STATION: self._station,
                ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
                ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
                ATTR_EXPECTED_AT: self._times[0][ATTR_EXPECTED_AT],
                ATTR_ORIGIN: self._times[0][ATTR_ORIGIN],
                ATTR_LAST_LOCATION: self._times[0][ATTR_LAST_LOCATION] if not None else 'No Information',
                ATTR_DESTINATION: self._times[0][ATTR_DESTINATION],
                ATTR_DIRECTION: self._times[0][ATTR_DIRECTION],
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_STATUS: self._times[0][ATTR_STATUS],
                ATTR_NEXT_UP: next_up
            }


    def update(self):
        """Get the latest data from irishrail and update the states."""
        self.data.update()
        self._times = self.data.info
        if len(self._times) > 0:
            self._state = self._times[0][ATTR_DUE_IN]
        else:
            self._state = None



class IrishRailTransportData(object):
    def __init__(self, station, direction):
        """Initialize the data object."""
        self.station = station
        self.direction = direction
        self.info = [{ATTR_DUE_AT: 'n/a',
                      ATTR_STATION: self.station,
                      ATTR_ORIGIN: 'n/a',
                      ATTR_LAST_LOCATION: 'n/a',
                      ATTR_DESTINATION: 'n/a',
                      ATTR_EXPECTED_AT: 'n/a',
                      ATTR_DIRECTION: 'n/a' if direction is None else direction,
                      ATTR_DUE_IN: 'n/a',
                      ATTR_STATUS: 'n/a'}]


    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from irishrail"""
        url = 'http://api.irishrail.ie/realtime/realtime.asmx/getStationDataByNameXML?'
        param_dict = {
            'StationDesc': self.station
        }
        url = url + urllib.parse.urlencode(param_dict)
        result = _parse_station_data(url)

        if len(result) > 0:
            train = []
            for item in result:
                direction = item.get('direction')
                if direction == self.direction or self.direction is None:
                    train_data = {ATTR_DUE_AT: item.get('scheduled_arrival_time'),
                                  ATTR_STATION: self.station,
                                  ATTR_ORIGIN: item.get('origin'),
                                  ATTR_LAST_LOCATION: item.get('last_location'),
                                  ATTR_DESTINATION: item.get('destination'),
                                  ATTR_DIRECTION: direction,
                                  ATTR_DUE_IN: item.get('due_in_mins'),
                                  ATTR_EXPECTED_AT: item.get('expected_departure_time'),
                                  ATTR_STATUS: item.get('status')
                                  }
                    train.append(train_data)

        if len(train) > 0:
            self.info = train

