odoo.define('one_page_website_calendar.one_page_booking_slot', function (require) {
    'use strict';

    var core = require('web.core');
    var QWeb = core.qweb;
    var publicWidget = require('web.public.widget');


    publicWidget.registry.OnePageWebsiteCalendarWidget = publicWidget.Widget.extend({
        selector: '#one_page_start_booking',
        events: {
            'click #view_availability': '_onCheckAvailability',
        },

        init: function (parent, options) {
            this._super.apply(this, arguments);
        },

        start: function () {
            var defs = [];
            defs.push(this._super.apply(this, arguments));
            return Promise.all(defs);
        },

        _onCheckAvailability: async function (e) {
            // params to query the booking slots for the booking type and employee
            var employee_id = $(".o_website_appointment_form select[name='employee_id']").val()
            var booking_type_id = $(".o_website_appointment_form select[name='booking_type_id']").val()
            await this._getBookingSlots(booking_type_id, employee_id)

            // toggle to next tab
            $('#start_booking').hide()
            $('#time_slot').show()

        },

        _getBookingSlots: async function (booking_type_id, employee_id) {
            var self = this
            await this._rpc({
                route: "/website/calendar/booking/slots",
                params: {
                    booking_type: booking_type_id,
                    employee_id: employee_id,
                },
            }).then(res => {
                const data = Object.assign({}, res)
                $('#one_page_view_booking_availability').replaceWith(QWeb.render('BookingCalendarAvailability', data));
            })
        },
    })

    return publicWidget.registry.OnePageWebsiteCalendarWidget
})
