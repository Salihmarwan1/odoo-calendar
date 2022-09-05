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

{
    'name': 'Calendar ics-urls',
    'version': '14.0.0.1.0',
    'category': 'Tools',
    'summary': 'Subscription on calendar.ics-urls',
    'licence': 'AGPL-3',
    'description': """
Adds and updates calendar objects according to an ics-url

""",
    'author': 'Vertel AB',
    'website': 'http://www.vertel.se',
    'depends': ['calendar',],
    'external_dependencies': {
        'python': ['icalendar'],
    },
    'data': [
        'views/res_partner_view.xml',
        # 'views/calendar_view.xml',
        #'security/ir.model.access.csv',
        'data/res_partner_data.xml'
    ],
    'application': False,
    'installable': True,
    'demo': ['demo/calendar_ics_demo.xml',],
}
# vim:expandtab:smartindent:tabstop=4s:softtabstop=4:shiftwidth=4:
