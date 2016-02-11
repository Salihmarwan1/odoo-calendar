# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution, third party addon
#    Copyright (C) 2004-2016 Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _
from pytz import timezone
from openerp.exceptions import except_orm, Warning, RedirectWarning
from datetime import datetime, timedelta
from time import strptime, mktime, strftime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

from openerp import http
from openerp.http import request

import logging
_logger = logging.getLogger(__name__)


try:
    from icalendar import Calendar, Event, vDatetime
except ImportError:
    raise Warning('icalendar library missing, pip install icalendar')

try:
    import urllib2
except ImportError:
    raise Warning('urllib2 library missing, pip install urllib2')    
    

# calendar_ics -> res.partner

# http://ical.oops.se/holidays/Sweden/-1,+1
# http://www.skatteverketkalender.se/skvcal-manadsmoms-maxfyrtiomiljoner-ingenperiodisk-ingenrotrut-verk1.ics
class res_partner_icalendar(http.Controller):
#        http://partner/<res.partner>/calendar/[private.ics|freebusy.ics|public.ics]
     #~ simple_blog_list = request.env['blog.post'].sudo().search([('blog_id', '=', simple_blog.id)], order='message_last_post desc')
    
    @http.route(['/partner/<model("res.partner"):partner>/calendar/private.ics'], type='http', auth="user", website=True)
    def icalendar_private(self, partner=False, **post):
        if partner:
            return partner.get_ics_calendar(type='private').to_ical()
        else:
            pass # Some error page

    @http.route(['/partner/<model("res.partner"):partner>/calendar/freebusy.ics'], type='http', auth="public", website=True)
    def icalendar_freebusy(self, partner=False, **post):
        if partner:
            #~ raise Warning("Public successfull %s" % partner.get_ics_calendar(type='public').to_ical())
            #~ return partner.get_ics_calendar(type='public').to_ical()
            document = partner.sudo().get_ics_calendar(type='freebusy').to_ical()
            return request.make_response(
                document,
                headers=[
                    ('Content-Disposition', 'attachment; filename="freebusy.ics"'),
                    ('Content-Type', 'text/calendar'),
                    ('Content-Length', len(document)),
                ]
            )
        else:
            raise Warning()
            pass # Some error page

    @http.route(['/partner/<model("res.partner"):partner>/calendar/public.ics'], type='http', auth="public", website=True)
    def icalendar_public(self, partner=False, **post):
        if partner:
            #~ raise Warning("Public successfull %s" % partner.get_ics_calendar(type='public').to_ical())
            #~ return partner.get_ics_calendar(type='public').to_ical()
            document = partner.sudo().get_ics_calendar(type='public').to_ical()
            return request.make_response(
                document,
                headers=[
                    ('Content-Disposition', 'attachment; filename="public.ics"'),
                    ('Content-Type', 'text/calendar'),
                    ('Content-Length', len(document)),
                ]
            )
        else:
            raise Warning("Public failed")
            pass # Some error page

class res_partner(models.Model):
    _inherit = "res.partner"
    
    ics_url  = fields.Char(string='Url',required=False)
    ics_active = fields.Boolean(string='Active',default=False)
    ics_nextdate = fields.Datetime(string="Next")
    #~ ics_frequency = fields.Integer(string="Frequency",default=60, help="Frequency in minutes, 60 = every hour, 1440 once per day, 10080 week, 43920 month, 131760 quarterly")
    ics_frequency = fields.Selection([('15', 'Every fifteen minutes'), ('60', 'Every hour'), ('360', 'Four times a day'), ('1440', 'Once per day'), ('10080', 'Once every week'), ('43920', 'Once every month'), ('131760', 'Once every third month')], string='Frequency', default='60')
    ics_class = fields.Selection([('private', 'Private'), ('public', 'Public'), ('freebusy', 'Free/busy')], string='Privacy', default='private')
    ics_show_as = fields.Selection([('free', 'Free'), ('busy', 'Busy')], string='Show Time as')
    ics_location = fields.Char(string='Location', help="Location of Event")
    ics_allday = fields.Boolean(string='All Day')
    ics_url_field = fields.Char(string='URL to the calendar', compute='create_ics_url')

    @api.one
    def create_ics_url(self):
        self.ics_url_field = '%s/partner/%s/calendar/%s.ics' % (self.env['ir.config_parameter'].sudo().get_param('web.base.url'), self.id, self.ics_class)

    @api.v7
    def ics_cron_job(self, cr, uid, context=None):
        for ics in self.pool.get('res.partner').browse(cr, uid, self.pool.get('res.partner').search(cr, uid, [('ics_active','=',True)])):
            if (datetime.fromtimestamp(mktime(strptime(ics.ics_nextdate, DEFAULT_SERVER_DATETIME_FORMAT))) < datetime.today()):
                ics.get_ics_events()
                ics.ics_nextdate = datetime.fromtimestamp(mktime(strptime(ics.ics_nextdate, DEFAULT_SERVER_DATETIME_FORMAT))) + timedelta(minutes=int(ics.ics_frequency))
                _logger.info('Cron job for %s done' % ics.name)

    @api.one
    def rm_ics_events(self):
        self.env['calendar.event'].search(['&',('partner_ids','in',self.id),('ics_subscription','=',True)]).unlink()

    @api.one
    def get_ics_events(self):
        if (self.ics_url):
            try:
                res = urllib2.urlopen(self.ics_url).read()
            except urllib2.HTTPError as e:
                _logger.error('ICS a %s %s' % (e.code, e.reason))
                return False
            except urllib2.URLError as e:
                _logger.error('ICS c %s %s' % (e.code, e.reason))
                return False
            _logger.error('ICS %s' % res)

            self.env['calendar.event'].search(['&',('partner_ids','in',self.id),('ics_subscription','=',True)]).unlink()
            #~ for event in self.env['calendar.event'].search([('ics_id','=',self.id)]):
                #~ event.unlink()
                
            self.env['calendar.event'].set_ics_event(res, self)
                    
    def get_ics_calendar(self,type='public'):
        calendar = Calendar()
        if type == 'private':
            calendar.add_component([self.env['calendar.event'].search([('partner_ids','in',self.id)]).get_ics_event()])
        elif type == 'freebusy':
            for event in self.env['calendar.event'].search([('partner_ids','in',self.id)]):
                #~ raise Warning(event.read(['class'])[0]['class'])
                if event.read(['class'])[0]['class'] == 'freebusy':
                    calendar.add_component(event.get_ics_file())
        elif type == 'public':
            for event in self.env['calendar.event'].search([('partner_ids','in',self.id)]):
                #~ raise Warning(event.get_ics_event().get('class'))
                if event.read(['class'])[0]['class'] == 'public':
                    calendar.add_component(event.get_ics_file())
            
        return calendar
        

    # vtodo, vjournal, vfreebusy


  #~ eventprop  = *(

             #~ ; the following are optional,
             #~ ; but MUST NOT occur more than once

             #~ class / created / description / dtstart / geo /
             #~ last-mod / location / organizer / priority /
             #~ dtstamp / seq / status / summary / transp /
             #~ uid / url / recurid /

             #~ ; either 'dtend' or 'duration' may appear in
             #~ ; a 'eventprop', but 'dtend' and 'duration'
             #~ ; MUST NOT occur in the same 'eventprop'

             #~ dtend / duration /

             #~ ; the following are optional,
             #~ ; and MAY occur more than once

             #~ attach / attendee / categories / comment /
             #~ contact / exdate / exrule / rstatus / related /
             #~ resources / rdate / rrule / x-prop

             #~ )

            
class calendar_event(models.Model):
    _inherit = 'calendar.event'
    
    ics_subscription = fields.Boolean(default=False) # partner_ids + ics_subscription -> its ok to delete

    @api.multi
    def set_ics_event(self, ics_file, partner):
        for event in Calendar.from_ical(ics_file).walk('vevent'):            
            #~ if not event.get('uid'):
                #~ event.add('uid',reduce(lambda x,y: x ^ y, map(ord, str(event.get('dtstart') and event.get('dtstart').dt or '' + event.get('summary') + event.get('dtend') and event.get('dtend').dt or ''))) % 1024)
                
            #~ ics_record = [
                #~ ('dtstart','start_date',event.get('dtstart') and event.get('dtstart').dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                #~ ('dtend','stop_date',event.get('dtend') and event.get('dtend').dt.strftime(DEFAULT_SERVER_DATE_FORMAT)),
                #~ ('dtstamp','start_datetime',event.get('dtstamp') and event.get('dtstamp').dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                #~ ('description','description',description),
                #~ ('duration','duration',event.get('duration')),
                #~ ('location','location',event.get('location') and unicode(event.get('location')) or self.ics_location),
                #~ ('class','class',event.get('class') and str(event.get('class')) or self.ics_class),
                #~ ('summary','name',summary),
                #~ ]

            summary = ''
            description = unicode(event.get('description', ''))
            if unicode(event.get('summary')) and len(unicode(event.get('summary'))) < 35:
                summary = unicode(event.get('summary'))
            elif len(unicode(event.get('summary'))) >= 35:
                summary = unicode(event.get('summary'))[:35]
                if not event.get('description'):
                    description = unicode(event.get('summary'))
            
            record = {r[1]:r[2] for r in [ ('dtstart','start_date',event.get('dtstart') and event.get('dtstart').dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                                                  ('dtend','stop_date',event.get('dtend') and event.get('dtend').dt.strftime(DEFAULT_SERVER_DATE_FORMAT)),
                                                  #~ ('dtstamp','start_datetime',event.get('dtstamp') and event.get('dtstamp').dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                                                  #~ ('description','description',description),
                                                  ('duration','duration',event.get('duration')),
                                                  ('location','location',event.get('location') and unicode(event.get('location')) or partner.ics_location),
                                                  ('class','class',event.get('class') and str(event.get('class')) or partner.ics_class),
                                                  ('summary','name',summary),
                                                  ] if event.get(r[0])}
            record['partner_ids'] = [(6,0,[partner.id])]
            record['ics_subscription'] = True
            record['start'] = record.get('start_date')
            record['stop'] = record.get('stop_date') or record.get('start')
            record['description'] = description
            record['show_as'] = partner.ics_show_as
            record['allday'] = partner.ics_allday

            if not record.get('stop_date'):
                record['allday'] = True
                record['stop_date'] = record['start_date']
            _logger.error('ICS %s' % record)
            self.env['calendar.event'].create(record)

    @api.multi
    def get_ics_event(self):
        event = self[0]
        ics = Event()
        ics = self.env['calendar.attendee'].get_ics_file(event)
        calendar = Calendar()
        date_format = DEFAULT_SERVER_DATETIME_FORMAT
        
        
        #~ for t in ics_record:
            #~ ics[t[2]] = eval(t[3])
        #~ 
        #~ foo = {ics[t[2]]: event.read([t[1]]) for t in ics_record}
        #~ 
        #~ 
        #~ ics['uid'] = event.id
        #~ ics['allday'] = event.allday
        #~ 
        #~ if ics['allday']:
            #~ date_format = DEFAULT_SERVER_DATE_FORMAT
            #~ 
        #~ ics['dtstart'] = vDatetime(datetime.fromtimestamp(mktime(strptime(event.start_date, date_format))))
        #~ ics['dtend'] = vDatetime(datetime.fromtimestamp(mktime(strptime(event.stop_date, date_format))))
        #~ ics['summary'] = event.name
        #~ ics['description'] = event.description
        #~ ics['class'] = event.read(['class'])

        #~ calendar.add_component(ics)
        #~ raise Warning(calendar.to_ical())
        return ics

    @api.multi
    def get_ics_file(self):
        """
        Returns iCalendar file for the event invitation.
        @param event_obj: event object (browse record)
        @return: .ics file content
        """
        ics = Event()
        event = self[0]

        def ics_datetime(idate, allday=False):
            if idate:
                if allday:
                    return fields.Date.from_string(idate)
                else:
                    return fields.Datetime.from_string(idate).replace(tzinfo=timezone('UTC'))
            return False

        #~ try:
            #~ # FIXME: why isn't this in CalDAV?
            #~ import vobject
        #~ except ImportError:
            #~ return res

        #~ cal = vobject.iCalendar()
        
        #~ event = cal.add('vevent')
        if not event.start or not event.stop:
            raise osv.except_osv(_('Warning!'), _("First you have to specify the date of the invitation."))
        ics['created'] = ics_datetime(strftime(DEFAULT_SERVER_DATETIME_FORMAT))
        ics['dtstart'] = ics_datetime(event.start, event.allday)
        ics['dtend'] = ics_datetime(event.stop, event.allday)
        #~ raise Warning(event.read(['class'])[0]['class'])
        if event.read(['class'])[0]['class'] == 'freebusy':
            ics['summary'] = 'Busy'
        else:
            ics['summary'] = event.name
        #~ raise Warning(event.read(['class'])[0]['class'])
        #~ ics['class'] = event.read(['class'])[0]['class']
        if event.description and event.read(['class'])[0]['class'] != 'freebusy':
            ics['description'] = event.description
        if event.location:
            ics['location'] = event.location
        if event.rrule:
            ics['rrule'] = event.rrule

        if event.alarm_ids:
            for alarm in event.alarm_ids:
                valarm = ics.add('valarm')
                interval = alarm.interval
                duration = alarm.duration
                trigger = valarm.add('TRIGGER')
                trigger.params['related'] = ["START"]
                if interval == 'days':
                    delta = timedelta(days=duration)
                elif interval == 'hours':
                    delta = timedelta(hours=duration)
                elif interval == 'minutes':
                    delta = timedelta(minutes=duration)
                trigger.value = delta
                valarm.add('DESCRIPTION').value = alarm.name or 'Odoo'
        #~ if event.attendee_ids:
            #~ for attendee in event.attendee_ids:
                #~ attendee_add = ics.add('attendee')
                #~ attendee_add.value = 'MAILTO:' + (attendee.email or '')
        #~ res = cal.serialize()
        #~ raise Warning(ics['summary'])
        return ics

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
