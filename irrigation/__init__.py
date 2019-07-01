import asyncio
import logging
import voluptuous as vol

from datetime import datetime
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_NAME , ATTR_ICON,
    EVENT_HOMEASSISTANT_START,EVENT_HOMEASSISTANT_STOP, 
    SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON, STATE_OFF)
from homeassistant.helpers.event import (
    async_track_time_change, async_track_state_change)


def time_hhmm_str(value: str) -> str:

    """Validate and transform watering time."""
    if isinstance(value, int):
        raise vol.Invalid('Wrap time values in quotes with format hh:mm')
    if not isinstance(value, str):
        raise vol.Invalid('Wrap time values in quotes with format hh:mm')

    try:
        parsed = [int(x) for x in value.split(':')]
    except ValueError:
        raise vol.Invalid('Make sure you wrap time values in quotes hh:mm')

    if len(parsed) == 2:
        hour, minute = parsed
        if hour > 23 or hour < 0:
            raise vol.Invalid('Make sure value hh between 0 and 23')
        if minute > 59 or minute < 0:
            raise vol.Invalid('Make sure value mm between 0 and 59')
    else:
        raise vol.Invalid('Wrap time values in quotes with format hh:mm')

    return str(value)


# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)

DOMAIN                = 'irrigation'
ENTITY_ID_FORMAT      = DOMAIN + '.{}'
ZONE_DOMAIN           = 'irrigation_zone'
ZONE_ENTITY_ID_FORMAT = ZONE_DOMAIN + '.{}'

PLATFORM_PROGRAM = 'program'
PLATFORM_ZONE    = 'zone'
PLATFORMS = [PLATFORM_PROGRAM,PLATFORM_ZONE]

STATE_ECO        = 'Eco'
ATTR_IGNORE      = 'ignore'
ATTR_IRRIG_ID    = 'name'
ATTR_NAME        = 'name'
ATTR_REMAINING   = 'remaining'
ATTR_REPEAT      = 'repeat'
ATTR_RUNTIME     = 'runtime'
ATTR_SENSOR      = 'sensor_entity'
ATTR_START       = 'start'
ATTR_SWITCH      = 'switch_entity'
ATTR_TEMPLATE    = 'template'
ATTR_WAIT        = 'wait'
ATTR_WATER       = 'water'
ATTR_ZONES       = 'zones'
ATTR_ZONE        = 'zone'
ATTR_ICON        = 'icon'
ATTR_ICON_WATER  = 'icon_on'
ATTR_ICON_WAIT   = 'icon_wait'
ATTR_ICON_OFF    = 'icon_off'
ATTR_PROGRAMS    = 'programs'
CONST_ENTITY     = 'entity_id'
CONST_SILENT     = 'silent'
CONST_SWITCH     = 'switch'

DFLT_ICON_WATER  = 'mdi:water'
DFLT_ICON_WAIT   = 'mdi:timer-sand'
DFLT_ICON_OFF    = 'mdi:water-off'
DFLT_ICON        = 'mdi:fountain'

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(ATTR_ZONES):[{    
                vol.Required(ATTR_IRRIG_ID): cv.string,
                vol.Required(ATTR_WATER): vol.Range(min=1, max=30),
                vol.Optional(ATTR_WAIT): vol.Range(min=1, max=30),
                vol.Optional(ATTR_REPEAT): vol.Range(min=1, max=30),
                vol.Optional(ATTR_TEMPLATE): cv.template,
                vol.Required(ATTR_SWITCH): cv.entity_domain('switch'),
                vol.Optional(ATTR_ICON_WATER,default=DFLT_ICON_WATER): cv.icon,
                vol.Optional(ATTR_ICON_WAIT,default=DFLT_ICON_WAIT): cv.icon,
                vol.Optional(ATTR_ICON_OFF,default=DFLT_ICON_OFF): cv.icon,
            }],
            vol.Required(ATTR_PROGRAMS):[{    
                vol.Required(ATTR_IRRIG_ID): cv.string,
                vol.Optional(ATTR_TEMPLATE): cv.template,
                vol.Optional(ATTR_ICON,default=DFLT_ICON): cv.icon,
                vol.Optional(ATTR_START): time_hhmm_str,
                vol.Optional(ATTR_ZONES): [{
                    vol.Required(ATTR_ZONE): cv.entity_domain('irrigation_zone'),
                    vol.Optional(ATTR_WATER): vol.Range(min=1, max=30),
                    vol.Optional(ATTR_WAIT): vol.Range(min=1, max=30),
                    vol.Optional(ATTR_REPEAT): vol.Range(min=1, max=30),
                }],
            }],
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, config):

    @asyncio.coroutine
    def async_run_program_service(call):
        try:
            perform_eval = call.data.get(CONST_SILENT,False)            
            entity_id = call.data.get(CONST_ENTITY)
        except:
            perform_eval = call.get(CONST_SILENT,False)            
            entity_id = call.get(CONST_ENTITY)

        """ stop any running zones  before starting a new program"""
        hass.services.async_call(DOMAIN, 
                                 'stop_programs', 
                                 {CONST_SILENT:True})

        entity = component.get_entity(entity_id)
        if entity:
            target_irrigation = [ entity ]
            tasks = [irrigation.async_run_program(perform_eval)
                     for irrigation in target_irrigation]
            if tasks:
                yield from asyncio.wait(tasks, loop=hass.loop)
        else:
            _LOGGER.error('irrigation program not found: %s', entity_id)
    """ END async_run_program_service """

    @asyncio.coroutine
    def async_run_zone_service(call):

        try:
            entity_id = call.data.get(CONST_ENTITY)
            y_water   = call.data.get(ATTR_WATER,0)
            y_wait    = call.data.get(ATTR_WAIT,0)
            y_repeat  = call.data.get(ATTR_REPEAT,0)
            y_ignore  = True
        except:
            entity_id = call.get(CONST_ENTITY)
            y_water   = call.get(ATTR_WATER,0)
            y_wait    = call.get(ATTR_WAIT,0)
            y_repeat  = call.get(ATTR_REPEAT,0)
            y_ignore  = False

        DATA = {ATTR_WATER:y_water, 
                ATTR_WAIT:y_wait, 
                ATTR_REPEAT:y_repeat,
                ATTR_IGNORE:y_ignore}

        entity = component.get_entity(entity_id)
        if entity:
            target_irrigation = [ entity ]
            tasks = [irrigation_zone.async_run_zone(DATA)
                     for irrigation_zone in target_irrigation]
            if tasks:
                yield from asyncio.wait(tasks, loop=hass.loop)
        else:
            _LOGGER.error('irrigation_zone not found: %s', entity_id)
    """ END async_run_zone_service """

    @asyncio.coroutine
    def async_stop_program_service(call):
#        silent = call.data.get(CONST_SILENT,False)

        for program in conf.get(ATTR_PROGRAMS):
            y_irrigation_id = cv.slugify(program.get(ATTR_IRRIG_ID))
            entity_id = ENTITY_ID_FORMAT.format(y_irrigation_id)
            entity = component.get_entity(entity_id)
            if entity:
                target_irrigation = [ entity ]
                tasks = [irrigation.async_stop_program()
                         for irrigation in target_irrigation]
                if tasks:
                    yield from asyncio.wait(tasks, loop=hass.loop)
            else:
                _LOGGER.error('irrigation program not found: %s',
                              entity_id)
                
        for zone in conf.get(ATTR_ZONES):
            y_irrigation_id = cv.slugify(zone.get(ATTR_IRRIG_ID))
            entity_id = ZONE_ENTITY_ID_FORMAT.format(y_irrigation_id)
            entity = component.get_entity(entity_id)
            if entity:
                target_irrigation = [ entity ]
                tasks = [irrigation_zone.async_stop_zone()
                         for irrigation_zone in target_irrigation]
                if tasks:
                    yield from asyncio.wait(tasks, loop=hass.loop)
            else:
                _LOGGER.error('irrigation_zone not found: %s', 
                              entity_id)


    """ END async_stop_program_service """
    
    @asyncio.coroutine
    def async_stop_switches(call):
        for zone in conf.get(ATTR_ZONES):
            y_irrigation_id = cv.slugify(zone.get(ATTR_IRRIG_ID))

            entity_id = ZONE_ENTITY_ID_FORMAT.format(y_irrigation_id)
            entity = component.get_entity(entity_id)
            if entity:
                target_irrigation = [ entity ]
                tasks = [irrigation_zone.async_stop_switch()
                         for irrigation_zone in target_irrigation]
                if tasks:
                    yield from asyncio.wait(tasks, loop=hass.loop)
            else:
                _LOGGER.error('irrigation_zone not found: %s', entity_id)
    """ END async_stop_switches """


    @asyncio.coroutine
    def async_run_refresh_program(call):

        for program in conf.get(ATTR_PROGRAMS):
            y_irrigation_id = cv.slugify(program.get(ATTR_IRRIG_ID))
            entity_id = ENTITY_ID_FORMAT.format(y_irrigation_id)
            entity = component.get_entity(entity_id)
            if entity:
                target_irrigation = [ entity ]
                tasks = [irrigation.async_refresh_program()
                         for irrigation in target_irrigation]
                if tasks:
                    yield from asyncio.wait(tasks, loop=hass.loop)
            else:
                _LOGGER.error('irrigation program not found: %s',
                              entity_id)
    """ END async_run_zone_service """
    
    
    """ create the entities and time tracking on setup of the component """
    conf = config[DOMAIN]
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entities = []
    zoneentities = []


    for program in conf.get(ATTR_PROGRAMS):
        y_irrigation_id = cv.slugify(program.get(ATTR_IRRIG_ID))

        p_entity = ENTITY_ID_FORMAT.format(y_irrigation_id)
        entities.append(Irrigation(p_entity, 
                                   program, 
                                   component))
        """ set automation to start the program at the desired times """
        y_hour, y_minute  = program.get(ATTR_START).split(':')
        DATA = {CONST_ENTITY:p_entity,CONST_SILENT:True}
        async_track_time_change(hass, 
                                async_run_program_service(DATA), 
                                hour=int(y_hour), 
                                minute=int(y_minute), 
                                second=00)

    for zone in conf.get(ATTR_ZONES):
        y_irrigation_id = cv.slugify(zone.get(ATTR_IRRIG_ID))
        p_entity = ZONE_ENTITY_ID_FORMAT.format(y_irrigation_id)
        zoneentities.append(IrrigationZone(p_entity, 
                                           zone))    


    await component.async_add_entities(entities)
    await component.async_add_entities(zoneentities)


    async_track_time_change(hass, 
                            async_run_refresh_program({}), 
                            hour=00, 
                            minute=00, 
                            second=00)


    """ define services """
    hass.services.async_register(DOMAIN, 
                                 'run_program', 
                                 async_run_program_service)
    hass.services.async_register(DOMAIN, 
                                 'run_zone', 
                                 async_run_zone_service)
    hass.services.async_register(DOMAIN, 
                                 'stop_programs', 
                                 async_stop_program_service)
    """ house keeping to help ensure solenoids are in a safe state """
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, 
                               async_stop_switches)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, 
                               async_stop_switches)

    return True


class Irrigation(RestoreEntity):
    """Representation of an Irrigation program."""

    def __init__(self, irrigation_id, attributes, component):
        """Initialize a Irrigation program."""
        self.entity_id   = irrigation_id 
        self._attributes = attributes
        self._component = component
        self._name      = attributes.get(ATTR_NAME)
        self._zones      = attributes.get(ATTR_ZONES)
        self._start_time = attributes.get(ATTR_START)
        self._stop = False
        """ default to today for new programs """
        now            = dt_util.utcnow()
        time_date      = dt_util.start_of_local_day(dt_util.as_local(now))
        self._last_run = dt_util.as_local(time_date).date().isoformat()
        self._template = attributes.get(ATTR_TEMPLATE)
        self._state_attributes = None
        self._running = False
        self._running_zone = None


    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_sensor_state_listener(entity, 
                                           old_state, 
                                           new_state):
            """Handle device state changes."""
            self._new_state = new_state.state
            self.async_schedule_update_ha_state(True)

        @callback
        def template_sensor_startup(event):
            """Update icons on startup."""
            async_track_state_change(self.hass, 
                                     self.entity_id, 
                                     template_sensor_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_sensor_startup)

        """ Run when entity about to be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()

        if state:
            """ handle bad data or new entity"""
            if not cv.date(state.state):
                now            = dt_util.utcnow()
                time_date      = dt_util.start_of_local_day(dt_util.as_local(now))
                self._last_run = dt_util.as_local(time_date).date().isoformat()
            else:
                self._last_run = state.state


    @property
    def should_poll(self):
        """If entity should be polled."""
        return False


    @property
    def name(self):
        """Return the name of the variable."""

        if self._running:
            x = '{}, running {}.'.format(
                  self._name, self._running_zone)
        else:
            x = '{}, runs at {}, last ran'.format(
                  self._name,
                  self._start_time)
        return x


    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        if self._attributes is not None:
            return self._attributes.get(ATTR_ICON)
        else:
            return None


    @property
    def state(self):
        """Return the state of the component."""
        return self._last_run


    @property
    def state_attributes(self):
        """Return the state attributes.
        Implemented by component base class.
        """
        return self._state_attributes


    @asyncio.coroutine
    async def async_update(self):

        a = datetime.now()
        b = datetime.fromisoformat(self._last_run + " 00:00:00")
        d = a - b
        ATTRS = {'start_time':self._start_time, 'days_since':d.days}
        setattr(self, '_state_attributes', ATTRS)
 

    @asyncio.coroutine
    async def async_stop_program(self):
        self._stop = True
        self._running = False
        self.async_schedule_update_ha_state()


    @asyncio.coroutine
    async def async_refresh_program(self):
        self.async_schedule_update_ha_state(True)
    

    @asyncio.coroutine
    async def async_run_program(self, perform_eval):
        self._stop = False
        self._running = True

        """ assess the template """
        r_eval = 'true'
        if self._template is not None:
            self._template.hass = self.hass
            try:
                r_eval = self._template.async_render().lower() == 'true'
            except TemplateError as ex:
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning(ex)
                    return
                _LOGGER.error(ex)
                return

        if r_eval == 'false':
            return

        """ Iterate through all the defined zones """
        for zone in self._zones:
            if self._stop == True:
                break

            y_water    = int(zone.get(ATTR_WATER,0))
            y_wait     = int(zone.get(ATTR_WAIT,0))
            y_repeat   = int(zone.get(ATTR_REPEAT,1))
            y_zone     = zone.get(ATTR_ZONE)

            DATA = {CONST_ENTITY:y_zone, 
                    ATTR_WATER:y_water, 
                    ATTR_WAIT:y_wait, 
                    ATTR_REPEAT:y_repeat} 
            await self.hass.services.async_call(DOMAIN, 
                                                'run_zone', 
                                                DATA)

            entity = self._component.get_entity(y_zone)
            self._running_zone = entity.name
            self.async_schedule_update_ha_state()

            """ wait for the state to take """
            step = 2
            await asyncio.sleep(step)
            while entity.state != STATE_OFF:
                await asyncio.sleep(step)
                if self._stop == True:
                    break

        """ update the status to new last watering day """
        if perform_eval:
            now            = dt_util.utcnow()
            time_date      = dt_util.start_of_local_day(dt_util.as_local(now))
            self._last_run = dt_util.as_local(time_date).date().isoformat()

        self._running = False

        self.async_schedule_update_ha_state()

class IrrigationZone(Entity):
    """Representation of an Irrigation program."""

    def __init__(self, irrigation_id, attributes):
    
        """Initialize a Irrigation program."""
        self.entity_id   = irrigation_id
        self._name       = attributes.get(ATTR_NAME)
        self._switch     = attributes.get(ATTR_SWITCH)
        self._water      = int(attributes.get(ATTR_WATER))
        self._wait       = int(attributes.get(ATTR_WAIT,0))
        self._repeat     = int(attributes.get(ATTR_REPEAT,1))
        self._state      = STATE_OFF
        self._icon_water = attributes.get(ATTR_ICON_WATER,
                                          DFLT_ICON_WATER)
        self._icon_wait  = attributes.get(ATTR_ICON_WAIT,
                                          DFLT_ICON_WAIT)
        self._icon_off   = attributes.get(ATTR_ICON_OFF,
                                          DFLT_ICON_OFF)
        self._icon       = self._icon_off
        self._new_state  = STATE_OFF
        self._stop       = False
        self._template   = attributes.get(ATTR_TEMPLATE)

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_sensor_state_listener(entity, 
                                           old_state, 
                                           new_state):
            """Handle device state changes."""
            self._new_state = new_state.state
            self.async_schedule_update_ha_state(True)

        @callback
        def template_sensor_startup(event):
            """Update icons on startup."""
            async_track_state_change(self.hass, 
                                     self.entity_id, 
                                     template_sensor_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_sensor_startup)

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the variable."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon
 
    @property
    def state(self):
        """Return the state of the component."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes.
        Implemented by component base class.
        """
        return None

    async def async_update(self):
        """Update the state from the template."""
        
        self._state = self._new_state
        
        if self._state == STATE_OFF:
            icon = self._icon_off
        elif self._state == STATE_ECO:
            icon = self._icon_wait
        else:
            icon = self._icon_water
        
        setattr(self, '_icon', icon)


    @asyncio.coroutine
    async def async_stop_zone(self):
        self._state = STATE_OFF
        self._stop = True
        DATA = {ATTR_ENTITY_ID: self._switch}
        await self.hass.services.async_call(CONST_SWITCH, 
                                            SERVICE_TURN_OFF, 
                                            DATA)
        self.async_schedule_update_ha_state()


    @asyncio.coroutine
    async def async_stop_switch(self):
        DATA = {ATTR_ENTITY_ID: self._switch}
        await self.hass.services.async_call(CONST_SWITCH, 
                                            SERVICE_TURN_OFF, 
                                            DATA)
        self.async_schedule_update_ha_state()


    @asyncio.coroutine
    async def async_run_zone(self,DATA):
        self._stop = False
        y_ignore_template = DATA.get(ATTR_IGNORE,True)
        y_water  = int(DATA.get(ATTR_WATER,self._water))
        y_wait   = int(DATA.get(ATTR_WAIT,self._wait))
        y_repeat = int(DATA.get(ATTR_REPEAT,self._repeat))
        if y_water == 0:
            y_water  = self._water
            y_wait   = self._wait
            y_repeat = self._repeat

        """ assess the template """
        if not y_ignore_template:
            evaluated = 'true'
            if self._template is not None:
                self._template.hass = self.hass
                try:
                    evaluated = self._template.async_render().lower() == 'true'
                except TemplateError as ex:
                    if ex.args and ex.args[0].startswith(
                            "UndefinedError: 'None' has no attribute"):
                        # Common during HA startup - so just a warning
                        _LOGGER.warning(ex)
                        return
                    _LOGGER.error(ex)
                    return

            if not evaluated:
                return

        """ run the watering cycle, water/wait/repeat """
        DATA = {ATTR_ENTITY_ID: self._switch}
        for i in range(y_repeat, 0, -1):
            if self._stop == True:
                break
                
            self.hass.states.async_set(self.entity_id, STATE_ON)
            DATA = {ATTR_ENTITY_ID: self._switch}
            await self.hass.services.async_call(CONST_SWITCH, 
                                                SERVICE_TURN_ON, 
                                                DATA)
#            self.async_schedule_update_ha_state()

            water = y_water * 60
            step = 2
            for w in range(0,water, step):
                await asyncio.sleep(step)
                if self._stop == True:
                    break

            """ turn the switch entity off """
            if y_wait > 0 and i > 1: 
                if self._stop == True:
                    break
                """ Eco mode is enabled """
                self.hass.states.async_set(self.entity_id, STATE_ECO)
                await self.hass.services.async_call(CONST_SWITCH, 
                                                    SERVICE_TURN_OFF, 
                                                    DATA)
#                self.async_schedule_update_ha_state()

                wait = y_wait * 60
                step = 2
                for w in range(0,wait, step):
                    await asyncio.sleep(step)
                    if self._stop == True:
                        break
                        
            if i <= 1: 
                """ last/only cycle """
                self.hass.states.async_set(self.entity_id, STATE_OFF)
                await self.hass.services.async_call(CONST_SWITCH, 
                                                    SERVICE_TURN_OFF, 
                                                    DATA)

        self.async_schedule_update_ha_state()
        return True