# -*- coding: utf-8 -*-
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#


from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz
from babel.dates import format_datetime, format_date

from werkzeug.urls import url_encode

from odoo import http, _, fields
from odoo.http import request
from odoo.tools import html2plaintext, DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.tools.misc import get_lang
import uuid
import logging

_logger = logging.getLogger(__name__)


class WebsiteCalendar(http.Controller):

    @http.route([
        '/website/calendar/products',
        '/website/calendar/products/<model("calendar.booking.type"):booking_type>/'], type='http', auth="public",
        website=True)
    def calendar_booking_product_choice(self, booking_type=None, product_id=None, **kwargs):
        if not booking_type:
            country_code = request.session.geoip and request.session.geoip.get('country_code')
            if country_code:
                suggested_booking_types = request.env['calendar.booking.type'].search([
                    '|', ('country_ids', '=', False),
                    ('country_ids.code', 'in', [country_code])])
            else:
                suggested_booking_types = request.env['calendar.booking.type'].search([])
            if not suggested_booking_types:
                return request.render("website_calendar_ce.setup", {})
            booking_type = suggested_booking_types[0]
        else:
            suggested_booking_types = booking_type
        suggested_products = []
        if product_id and int(product_id) in booking_type.sudo().product_ids.ids:
            suggested_products = request.env['product.product'].sudo().browse(int(product_id)).name_get()
        elif booking_type.assignation_method == 'chosen':
            suggested_products = booking_type.sudo().product_ids.name_get()
        return request.render("website_calendar_product_resource.index", {
            'booking_type': booking_type,
            'suggested_booking_types': suggested_booking_types,
            'selected_product_id': product_id and int(product_id),
            'suggested_products': suggested_products,
        })

    @http.route(['/website/calendar/get_product_booking_info'], type='json', auth="public", methods=['POST'],
                website=True)
    def get_booking_info(self, booking_id, prev_product=False, **kwargs):
        booking_type_id = request.env['calendar.booking.type'].browse(int(booking_id)).sudo()
        result = {
            'message_intro': booking_type_id.message_intro,
            'assignation_method': booking_type_id.assignation_method,
        }
        if result['assignation_method'] == 'chosen':
            selection_template = http.request.env.ref('website_calendar_product_resource.product_select')
            data = {
                'booking_type': booking_type_id,
                'suggested_products': booking_type_id.product_ids.name_get(),
                'selected_product_id': prev_product and int(prev_product),
            }
            # TODO: I dislike using private function here, although no other function seems to work
            #       as I need it to work.
            result['product_selection_html'] = selection_template._render(data)
        return result

    @http.route(['/website/calendar/product/<model("calendar.booking.type"):booking_type>/booking'], type='http',
                auth="public", website=True)
    def calendar_booking(self, booking_type=None, product_id=None, failed=False, **kwargs):
        if product_id:
            product_obj = request.env['product.product'].sudo().browse(int(product_id)) if product_id else None
        else:
            product_obj = booking_type.product_ids[0]

        session = request.session
        timezone = session.get('timezone')
        if not timezone:
            timezone = session.context.get('tz')
        slot_ids = booking_type.sudo()._get_paginated_product_booking_slots(timezone, product_obj)
        return request.render("website_calendar_product_resource.booking", {
            'booking_type': booking_type,
            'product_id': product_obj,
            'timezone': timezone,
            'failed': failed,
            'slots': slot_ids,
            'description': _(
                "Fill your personal information in the form below, and confirm the booking. We'll send an invite to "
                "your email address"),
            'title': _("Book meeting"),
        })

    @http.route(['/booking/product/slots'], type='json', auth="public", website=True)
    def toggle_booking_product_slots(self, booking_type=None, product_id=None, month=0, description=None, title=None,
                                     **kwargs):
        booking_type = request.env['calendar.booking.type'].sudo().browse(int(booking_type)) if booking_type else None
        request.session['timezone'] = booking_type.booking_tz
        product_product_id = request.env['product.product'].sudo().browse(int(product_id)) if product_id else None
        slot_ids = booking_type.sudo()._get_paginated_product_booking_slots(
            request.session['timezone'], product_product_id, int(month))

        if slot_ids:
            return request.env['ir.ui.view']._render_template("website_calendar_product_resource.booking_calendar", {
                'booking_type': booking_type,
                'product_id': product_product_id,
                'timezone': request.session['timezone'],
                'slots': slot_ids,
                'description': description if description else _(
                    "Fill your personal information in the form below, and confirm the booking. We'll send an invite "
                    "to your email address"),
                'title': title if title else _("Book meeting"),
            })
        else:
            return False

    @http.route(['/website/calendar/<model("calendar.booking.type"):booking_type>/product/info'], type='http',
                auth="public",
                website=True)
    def calendar_booking_product_form(self, booking_type, product_id, start_date, end_date=None, description=None,
                                      title=None,
                                      **kwargs):
        partner_data = {}
        if request.env.user.partner_id != request.env.ref('base.public_partner'):
            partner_data = request.env.user.partner_id.read(fields=['name', 'mobile', 'country_id', 'email'])[0]
        start_day_name = format_datetime(datetime.strptime(start_date, dtf), 'EEE', locale=get_lang(request.env).code)
        start_date_formatted = format_datetime(datetime.strptime(start_date, dtf), locale=get_lang(request.env).code)

        vals = {
            'partner_data': partner_data,
            'booking_type': booking_type,
            'start_datetime': start_date,
            'start_datetime_locale': start_day_name + ' ' + start_date_formatted,
            'start_datetime_str': start_date,
            'product_id': product_id,
            'countries': request.env['res.country'].search([]),
            'description': description if description else _(
                "Fill your personal information in the form below, and confirm the booking. We'll send an invite to "
                "your email address"),
            'title': title if title else _("Book meeting"),
        }
        if end_date:
            end_day_name = format_datetime(datetime.strptime(end_date, dtf), 'EEE', locale=get_lang(request.env).code)
            end_date_formatted = format_datetime(datetime.strptime(end_date, dtf), locale=get_lang(request.env).code)
            vals.update({
                'end_datetime': end_date,
                'end_datetime_locale': end_day_name + ' ' + end_date_formatted,
                'end_datetime_str': end_date,
            })

        # product = request.env['product.product'].sudo().browse(int(product_id))
        # if employee.user_id and employee.user_id.partner_id:
        #     if not employee.user_id.partner_id.calendar_verify_availability(fields.Datetime.from_string(start_date),
        #                                                                     fields.Datetime.from_string(end_date)):
        #         return request.redirect('/website/calendar/%s/booking?failed=employee' % booking_type.id)
        #
        # if end_date and (datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S") > datetime.strptime(end_date, "%Y-%m-%d "
        #                                                                                                   "%H:%M:%S")):
        #     return request.redirect('/website/calendar/%s/booking?failed=datetime' % booking_type.id)

        return request.render("website_calendar_product_resource.booking_form", vals)

    @http.route(['/website/calendar/product/<model("calendar.booking.type"):booking_type>/submit'], type='http',
                auth="public",
                website=True, methods=["POST"])
    def calendar_booking_product_submit(self, booking_type, start_datetime_str, product_id, name, phone, email,
                                        end_datetime_str=None, country_id=False, comment=False, company=False,
                                        description=False, title=_("Book meeting"), **kwargs):
        timezone = request.session['timezone']
        tz_session = pytz.timezone(timezone)
        date_start = tz_session.localize(fields.Datetime.from_string(start_datetime_str)).astimezone(pytz.utc)
        if end_datetime_str:
            date_end = tz_session.localize(fields.Datetime.from_string(end_datetime_str)).astimezone(pytz.utc)
        else:
            date_end = date_start + relativedelta(hours=booking_type.booking_duration)

        # check availability of the employee again (in case someone else booked while the client was entering the form)
        product_product_id = request.env['product.product'].sudo().browse(int(product_id))
        # if product_product_id.user_id and product_product_id.user_id.partner_id:
        #     if not hr_employee_id.user_id.partner_id.calendar_verify_availability(date_start, date_end):
        #         return request.redirect('/website/calendar/%s/booking?failed=employee' % booking_type.id)

        country_id = int(country_id) if country_id else None
        country_name = country_id and request.env['res.country'].browse(country_id).name or ''
        partner = request.env['res.partner'].sudo().search([('email', '=like', email)], limit=1)
        if partner:
            if not product_product_id.calendar_verify_product_availability(partner, date_start, date_end):
                return request.redirect('/website/calendar/product/%s/booking?failed=product' % booking_type.id)
            if not partner.mobile or len(partner.mobile) <= 5 and len(phone) > 5:
                partner.write({'mobile': phone})
            if not partner.country_id:
                partner.country_id = country_id
        else:
            partner = partner.create({
                'name': name,
                'country_id': country_id,
                'mobile': phone,
                'email': email,
            })

        record_description = (_('Country: %s') + '\n\n' +
                              _('Mobile: %s') + '\n\n' +
                              _('Email: %s') + '\n\n') % (country_name, phone, email)
        for question in booking_type.question_ids:
            key = 'question_' + str(question.id)
            if question.question_type == 'checkbox':
                answers = question.answer_ids.filtered(lambda x: (key + '_answer_' + str(x.id)) in kwargs)
                record_description += question.name + ': ' + ', '.join(answers.mapped('name')) + '\n'
            elif kwargs.get(key):
                if question.question_type == 'text':
                    record_description += '\n* ' + question.name + ' *\n' + kwargs.get(key, False) + '\n\n'
                else:
                    record_description += question.name + ': ' + kwargs.get(key) + '\n\n'
        if company:
            record_description += _("Company: ") + company
        if comment:
            record_description += _("\n\nComment: ") + comment
        if description:
            record_description += _("\n\nDescription: ") + description
        if title:
            record_description += _("\n\nTitle: ") + title

        categ_id = request.env.ref('website_calendar_ce.calendar_event_type_data_online_booking')
        alarm_ids = booking_type.reminder_ids and [(6, 0, booking_type.reminder_ids.ids)] or []
        # partner_ids = list(set([request.env.user.partner_id.id] + [partner.id]))

        data = {
            'state': 'open',
            'name': _('%s with %s') % (booking_type.name, name),
            'start_date': date_start.strftime(dtf),
            'start': date_start.strftime(dtf),
            'stop': date_end.strftime(dtf),
            'allday': False,
            'duration': booking_type.booking_duration,
            'description': '',  # record_description,
            'alarm_ids': alarm_ids,
            'location': f"https://{booking_type.meeting_base_url}/{str(uuid.uuid1())}",
            'partner_ids': [(4, partner.id, False)],
            'categ_ids': [(4, categ_id.id, False)],
            'booking_type_id': booking_type.id,
            'user_id': request.env.user.id,
            'meeting_url': f"https://{booking_type.meeting_base_url}/{str(uuid.uuid1())}",
            'product_id': product_product_id.id,
        }
        if end_datetime_str:
            data.update({
                # 'allday': True,
                'stop_date': date_end.strftime(dtf)
            })
        event = request.env['calendar.event'].sudo().with_context(
            allowed_company_ids=request.env.user.company_ids.ids).create(data)
        # event.attendee_ids.filtered(lambda attendee: attendee.partner_id.id == partner.id).write({'public_user': True})
        # event.attendee_ids.write({'state': 'accepted'})
        return request.redirect('/website/calendar/view/' + event.access_token + '?message=new' + '&title=' + title)
