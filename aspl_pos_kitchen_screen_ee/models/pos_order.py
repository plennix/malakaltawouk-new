# -*- coding: utf-8 -*-
#################################################################################
# Author      : Acespritech Solutions Pvt. Ltd. (<www.acespritech.com>)
# Copyright(c): 2012-Present Acespritech Solutions Pvt. Ltd.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
import pytz
import pytz
import psycopg2
import logging
from re import search
from functools import partial
from itertools import groupby
from odoo import models, fields, api, tools, _


line_state = {'Waiting': 1, 'Preparing': 2, 'Delivering': 3, 'Done': 4}


class PosOrder(models.Model):
    _inherit = "pos.order"

    order_state = fields.Selection(
        [("Start", "Start"), ("Done", "Done"), ("Deliver", "Deliver"), ("Complete", "Complete")], default="Start")
    send_to_kitchen = fields.Boolean('Send to Kitchen', readonly=True)
    line_cancel_reason_ids = fields.One2many('order.line.cancel.reason', 'pos_order_id', string="Line Cancel Reason")
    cancel_order_reason = fields.Text('Cancel Reason', readonly=True)

    def action_pos_order_paid(self):
        res = super(PosOrder, self).action_pos_order_paid()
        if res:
            self.cancel_or_delete_pos_order(self.id, '', 'paid')
        return res

    @api.model
    def cancel_or_delete_pos_order(self, order_id, cancel_reason, string):
        order_obj = self.browse(order_id)
        pos_reference = order_obj.pos_reference
        if string == 'cancel':
            order_obj.write({'state': 'cancel', 'cancel_order_reason': cancel_reason or ''})
        elif string == 'delete':
            order_obj.unlink()
        else:
            pass
        kitchen_user_ids = self.env['res.users'].search([('kitchen_screen_user', 'in', ['manager', 'waiter'])])
        notifications = []
        if kitchen_user_ids:
            for kitchen_user_id in kitchen_user_ids:
                notify_data = {'order_id': order_obj.id,
                               'remove_or_cancel': True,
                               'message': f"{pos_reference} [{string.upper()}]".format(pos_reference, string),
                               'is_remove': string}
                notifications.append([kitchen_user_id.partner_id, 'pos.order/kitchen_screen', notify_data])
        if notifications:
            self.env['bus.bus']._sendmany(notifications)
        self.broadcast_order_data(False)
        return True

    @api.model
    def get_table_draft_orders_for_payment(self, order_id):
        table_orders = self.search_read(
            domain=[('state', '=', 'draft'), ('id', '=', order_id)],
            fields=self._get_fields_for_draft_order())

        self._get_order_lines(table_orders)
        self._get_payment_lines(table_orders)

        for order in table_orders:
            order['pos_session_id'] = order['session_id'][0]
            order['uid'] = search(r"\d{5,}-\d{3,}-\d{4,}", order['pos_reference']).group(0)
            order['name'] = order['pos_reference']
            order['creation_date'] = order['create_date']
            order['server_id'] = order['id']
            if order['fiscal_position_id']:
                order['fiscal_position_id'] = order['fiscal_position_id'][0]
            if order['pricelist_id']:
                order['pricelist_id'] = order['pricelist_id'][0]
            if order['partner_id']:
                order['partner_id'] = order['partner_id'][0]
            if order['table_id']:
                order['table_id'] = order['table_id'][0]

            if not 'lines' in order:
                order['lines'] = []
            if not 'statement_ids' in order:
                order['statement_ids'] = []
            del order['id']
            del order['session_id']
            del order['pos_reference']
            del order['create_date']
        return table_orders

    def _get_fields_for_order_line(self):
        res = super(PosOrder, self)._get_fields_for_order_line()
        if isinstance(res, list):
            res.append('state')
            res.append('line_cid')
        return res

    def _get_fields_for_draft_order(self):
        res = super(PosOrder, self)._get_fields_for_draft_order()
        if isinstance(res, list):
            res.append('send_to_kitchen')
            res.append('order_state')
        return res

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        order_fields['order_state'] = ui_order.get('order_state', False)
        order_fields['send_to_kitchen'] = ui_order.get('send_to_kitchen', False)
        return order_fields

    @api.model
    def _process_order(self, order, draft, existing_order):
        res = super(PosOrder, self)._process_order(order, draft, existing_order)
        if order and order.get('data') and order.get('data').get('delete_product') and order.get('data').get('server_id') and order.get('data').get('cancel_product_reason'):
            order_id = self.browse(order.get('data').get('server_id'))
            reason = order.get('data').get('cancel_product_reason')
            order_id.write({
                'line_cancel_reason_ids': [(0, 0, {
                    'pos_order_id': order_id.id,
                    'product_id': reason.get('product'),
                    'reason': reason.get('reason_id'),
                    'description': reason.get('description'),
                })],
            })
        if order['data'].get('send_to_kitchen') or not order['data'].get('table_id'):
            self.broadcast_order_data(True)
        return res

    def convert_end_time(self, end_datetime):
        return pytz.utc.localize(end_datetime).isoformat()

    def get_broadcast_order_data(self):
        order_line_list = []
        order_line_time = 0
        for line in self.lines:
            order_line = {
                'id': line.id,
                'order_id': self.id,
                'line_cid': line.line_cid,
                'name': line.product_id.display_name,
                'full_product_name': line.full_product_name,
                'note': line.note,
                'qty': line.qty,
                'table': line.order_id.table_id.name,
                'floor': line.order_id.table_id.floor_id.name,
                'state': line.state,
                'categ_id': line.product_id.product_tmpl_id.pos_categ_id.id,
                'order_name': line.order_id.name,
                'user': line.create_uid.id,
                'route_id': line.product_id.product_tmpl_id.route_ids.active,
            }
            order_line_list.append(order_line)
        return {
            'order_id': self.id,
            'order_name': self.name,
            'pos_reference': self.pos_reference,
            'order_time': self.convert_end_time(self.date_order),
            'table': self.table_id.name,
            'floor': self.table_id.floor_id.name,
            'customer': self.partner_id.name,
            'order_lines': order_line_list,
            'total': self.amount_total,
            'note': self.note,
            'state': self.state,
            'user_id': self.user_id.id,
            'user_name': self.user_id.name,
            'guests': self.customer_count,
            'order_state': self.order_state,
        }

    @api.model
    def broadcast_order_data(self, new_order):
        pos_order = self.search([('lines.state', 'not in', ['cancel', 'done']),
                                 ('amount_total', '>', 0.00), ('send_to_kitchen', '=', True)])
        screen_table_data = []
        for order in pos_order:
            # if order.order_state != 'Complete':
            order_dict = order.get_broadcast_order_data()
            screen_table_data.append(order_dict)
        screen_table_data = screen_table_data[::-1]
        kitchen_user_ids = self.env['res.users'].search([('kitchen_screen_user', 'in', ['cook', 'manager', 'waiter'])])
        notifications = []
        order_sync_data = self.order_sync_data()
        notifications = []
        if kitchen_user_ids:
            for kitchen_user_id in kitchen_user_ids:
                notify_data = {
                    'screen_display_data': screen_table_data,
                    'new_order': new_order,
                    'order_sync_data': order_sync_data,
                    'manager': False if kitchen_user_id.kitchen_screen_user == 'cook' else True
                }
                notifications.append([kitchen_user_id.partner_id, 'pos.order/kitchen_screen', notify_data])
        if notifications:
            self.env['bus.bus']._sendmany(notifications)
        return order_sync_data

    @api.model
    def order_sync_data(self):
        pos_orders_obj = self.search([('state', '=', 'draft'), ('send_to_kitchen', '=', True),
                                      ('amount_total', '>', 0.0)])
        sync_order_data = []
        for order in pos_orders_obj:
            sync_order_data.append({
                'order_id': order.id,
                'pos_reference': order.pos_reference,
                'order_time': self.convert_end_time(order.date_order),
                'table': order.table_id.name,
                'floor': order.table_id.floor_id.name,
                'customer': order.partner_id.name,
                'total': order.amount_total,
                'state': order.state,
                'user_id': order.user_id.id,
                'user_name': order.user_id.name,
            })
        return sync_order_data


class PosOrderLines(models.Model):
    _inherit = "pos.order.line"

    state = fields.Selection(
        selection=[("Waiting", "Waiting"), ("Preparing", "Preparing"), ("Delivering", "Delivering"),
                   ("Done", "Done")], default="Waiting")
    line_cid = fields.Char('Line cid')

    @api.model
    def update_orderline_state(self, vals):
        order_line = self.browse(vals['order_line_id'])
        order = self.env['pos.order'].browse(vals['order_id'])
        if line_state[vals['state']] >= line_state[order_line.state]:
            order_line.sudo().write({
                'state': vals['state']
            })
            vals['pos_reference'] = order_line.order_id.pos_reference
            state_list = [line.state for line in order.lines]
            if 'Waiting' in state_list:
                order_state = 'Start'
                order.sudo().write({'order_state': order_state})
            elif 'Preparing' in state_list:
                order_state = 'Done'
                order.sudo().write({'order_state': order_state})
            else:
                order_state = 'Deliver'
                order.sudo().write({'order_state': order_state})
            order.broadcast_order_data(False)
            vals.update({'server_id': order_line.id, 'line_cid': order_line.line_cid})
            notify_data = {'order_line_state': vals}
            kitchen_user_ids = self.env['res.users'].search([('kitchen_screen_user', '=', 'manager')])
            notifications = []
            if kitchen_user_ids:
                for kitchen_user_id in kitchen_user_ids:
                    notifications.append([kitchen_user_id.partner_id, 'pos.order/kitchen_screen', notify_data])
            if notifications:
                self.env['bus.bus']._sendmany(notifications)
        return True

    @api.model
    def update_all_orderline_state(self, vals):
        order = self.env['pos.order'].browse(vals['order_id'])
        order.sudo().write({'order_state': vals['order_state']})
        for line in order.lines:
            if line_state[vals['line_state']] >= line_state[line.state]:
                notifications = []
                line.sudo().write({'state': vals['line_state']})
                vals['pos_reference'] = line.order_id.pos_reference
                vals['server_id'] = line.id
                vals['state'] = vals['line_state']
                vals['line_cid'] = line.line_cid
                notify_data = {'order_line_state': vals}
                kitchen_user_ids = self.env['res.users'].search([('kitchen_screen_user', '=', 'manager')])
                notifications = []
                if kitchen_user_ids:
                    for kitchen_user_id in kitchen_user_ids:
                        notifications.append([kitchen_user_id.partner_id, 'pos.order/kitchen_screen', notify_data])
                if notifications:
                    self.env['bus.bus']._sendmany(notifications)
        order.broadcast_order_data(False)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
