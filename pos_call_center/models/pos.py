# -*- coding: utf-8 -*-


from odoo import fields, models,tools,api, _
import logging
from functools import partial
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError
import pytz

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    quotation_id = fields.Many2one("pos.quotation",string="Quotation Ref.",readonly=True)

    @api.model
    def _order_fields(self, ui_order):
        result = super(PosOrder, self)._order_fields(ui_order)
        if 'quotation_id' in ui_order and 'quot_id' in ui_order:
            result['quotation_id'] = ui_order['quot_id']
            quotation_obj = self.env['pos.quotation'].browse(ui_order['quot_id'])
            if quotation_obj:
                quotation_obj.state = 'done' 


        return result

class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    extra_note = fields.Char(string="Note")




class pos_quotation(models.Model):
    _name = 'pos.quotation'
    _order = "id desc"

    @api.model
    def _amount_line_tax(self, line, fiscal_position_id):
        taxes = line.tax_ids.filtered(lambda t: t.company_id.id == line.quotation_id.company_id.id)
        if fiscal_position_id:
            taxes = fiscal_position_id.map_tax(taxes, line.product_id, line.quotation_id.partner_id)
        price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        taxes = taxes.compute_all(price, line.quotation_id.pricelist_id.currency_id, line.qty, product=line.product_id, partner=line.quotation_id.partner_id or False)['taxes']
        return sum(tax.get('amount', 0.0) for tax in taxes)

    def _default_session(self):
        return self.env['pos.session'].search([('state', '=', 'opened'), ('user_id', '=', self.env.uid)], limit=1)

    def _default_pricelist(self):
        return self._default_session().config_id.pricelist_id

    @api.model
    def deliver_order(self, order_id):
        self.browse(order_id).state = "sent"
        return {'data':'sent'}

    @api.model
    def transfer_order(self, order_id,branch_id):
        self.browse(order_id).branch_id = branch_id
        return {'data':'sent'}

    @api.model
    def read_order_json(self,totalId,config_id):
        order_json_format = []
        total_ids = []
        for order in self.search([('state','=','confirm'),('id','not in',totalId),('branch_id','=',config_id)]):
            if order.id not in totalId:
                order_line = []
                for line in order.lines:
                    order_line.append({
                        'product_id':line.product_id.id,
                        'qty':line.qty,
                        'note':line.extra_note,
                        'order_line_status':'0',
                        'price_unit':line.price_unit,
                        'discount':line.discount,
                        })
                total_ids.append(order.id)
                user_tz = self.env.user.tz
                order_json_format.append({
                    'id':order.id,
                    'is_hidden':True,
                    'order_priority': order.priority,
                    'delivery_date':datetime.strftime(pytz.utc.localize(datetime.strptime(str(order.delivery_date),DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(pytz.timezone(user_tz)),"%Y-%m-%dT%H:%M:%S") if self.env.user.tz else order.delivery_date,
                    'partner_id':order.partner_id.id,
                    'lines':order_line,
                    })
        return {'data':order_json_format,'total_ids':total_ids}

    @api.model
    def new_sent_order_json(self,totalId,config_id):
        order_json_format = []
        total_ids = []
        for order in self.search([('state','in',['sent','confirm'])]):
            # order.state = 'done'
            # if order.id not in totalId:
            order_json_format.append(order.read(['id','name','delivery_date','amount_total','stock_location','partner_id','lines','state','branch_id']))
        return {'data':order_json_format}

    @api.model
    def quotation_package_location(self,quot_id,location_name):
        self.browse(int(quot_id)).stock_location = location_name
        return {'data':True}

    delivery_date = fields.Datetime(string="Delivery Date")
    name = fields.Char(string='Name',required=True, readonly=True, copy=False, default='/')
    stock_location = fields.Char(string='Stock location')
    lines = fields.One2many('pos.quotation.line', 'quotation_id', string='POS Lines')
    partner_id = fields.Many2one('res.partner', string='Customer')
    order_id = fields.Many2one('pos.order', string='Order Ref.',readonly=True)
    session_id = fields.Many2one('pos.session', string='Session')
    config_id = fields.Many2one('pos.config', related='session_id.config_id', string="Point of Sale")
    amount_tax = fields.Float(compute='_compute_amount_all', string='Taxes', digits=0, readonly=1)
    amount_total = fields.Float(compute='_compute_amount_all', string='Total', digits=0, readonly=1)
    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('confirm','Confirm'),('sent', 'Sent'), ('done', 'Done')],
        'Status', readonly=True, copy=False, default='draft')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, default=_default_pricelist)
    note = fields.Text(string='Internal Notes')
    branch_id = fields.Many2one('pos.config',string="Branch")
    priority = fields.Integer()
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position', default=lambda self: self._default_session().config_id.default_fiscal_position_id)

    @api.depends('lines.price_subtotal_incl', 'lines.discount')
    def _compute_amount_all(self):
        for order in self:
            order.amount_tax = 0.0
            currency = order.pricelist_id.currency_id
            order.amount_tax = currency.round(sum(self._amount_line_tax(line, order.fiscal_position_id) for line in order.lines))
            amount_untaxed = currency.round(sum(line.price_subtotal for line in order.lines))
            order.amount_total = order.amount_tax + amount_untaxed


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.pricelist = self.partner_id.property_product_pricelist.id

    @api.model
    def _order_fields(self, ui_order):
        process_line = partial(self.env['pos.quotation.line']._order_line_fields)
        delivery_date = datetime.strptime(ui_order['delivery_date'], "%Y-%m-%d %H:%M:%S")
        delivery_date_str = delivery_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        print("Testng>>>>>>>>>>>>",[process_line(l) for l in ui_order['lines']] if ui_order['lines'] else False)

        return {
            'session_id':   ui_order['pos_session_id'],
            'lines':        [process_line(l) for l in ui_order['lines']] if ui_order['lines'] else False,
            'partner_id':   ui_order['partner_id'] or False,
            'fiscal_position_id': ui_order['fiscal_position_id'],
            'note':         ui_order['wv_note'],
            'delivery_date':delivery_date_str,
            'branch_id': ui_order['branch_id'],
            'state':'confirm',
            'priority':ui_order['priority']
        }
    @api.model
    def create_new_quotation(self,quotation):
        print("Testing>>>>>>>>>>>>>>>>>>",quotation)
        quotation_obj = self.create(self._order_fields(quotation))
        order_line = self.env['pos.quotation.line'].search_read([('quotation_id','=',quotation_obj.id)],[])
        return {'result':quotation_obj.read([])}


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].get('pos.quotation')
        return super(pos_quotation, self).create(vals)

    @api.model
    def quotation_fetch_line(self, quotation_id):
        quotation_obj = self.browse(int(quotation_id))
        if quotation_obj:
            return {
                'partner_id':quotation_obj.partner_id.id,
                'name':quotation_obj.name,
                'orderline':quotation_obj.lines.read(['product_id','price_unit','qty','discount','tax_ids']),
            }
        return False

    def wv_order_cancel(self):
        self.state = 'cancel'

    def wv_order_confirm(self):
        self.state = 'confirm'

    def wv_order_sent(self):
        self.state = 'sent'

    def wv_order_done(self):
        self.state = 'done'


class pos_quotation_line(models.Model):
    _name = 'pos.quotation.line'

    def _order_line_fields(self, line):
        line2 = [0,0,{}]
        if line and 'tax_ids' not in line[2]:
            product = self.env['product.product'].browse(line[2]['product_id'])
            line2[2]['tax_ids'] = [(6, 0, [x.id for x in product.taxes_id])]
        line2[2]['product_id'] = line[2]['product_id']
        line2[2]['qty'] = line[2]['qty']
        line2[2]['price_unit'] = line[2]['price_unit']
        line2[2]['discount'] = line[2]['discount']
        line2[2]['price_subtotal'] = line[2]['price_subtotal']
        line2[2]['extra_note'] = line[2]['extra_note']
        return line2

    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    notice = fields.Char(string='Discount Notice')
    extra_note = fields.Char(string="Note")
    product_id = fields.Many2one('product.product', string='Product', required=True, change_default=True)
    quotation_id = fields.Many2one('pos.quotation')
    price_unit = fields.Float(string='Unit Price', digits=0)
    qty = fields.Float('Quantity', default=1)
    price_subtotal = fields.Float(compute='_compute_amount_line_all',digits=0, string='Subtotal w/o Tax')
    price_subtotal_incl = fields.Float(compute='_compute_amount_line_all',digits=0, string='Subtotal')
    discount = fields.Float(string='Discount (%)', digits=0, default=0.0)
    create_date = fields.Datetime(string='Creation Date', readonly=True)
    tax_ids = fields.Many2many('account.tax', string='Taxes', readonly=True)


    @api.depends('price_unit', 'tax_ids', 'qty', 'discount', 'product_id')
    def _compute_amount_line_all(self):
        for line in self:
            currency = line.quotation_id.pricelist_id.currency_id
            taxes = line.tax_ids.filtered(lambda tax: tax.company_id.id == line.quotation_id.company_id.id)
            fiscal_position_id = line.quotation_id.fiscal_position_id
            if fiscal_position_id:
                taxes = fiscal_position_id.map_tax(taxes, line.product_id, line.quotation_id.partner_id)
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.price_subtotal = line.price_subtotal_incl = price * line.qty
            if taxes:
                taxes = taxes.compute_all(price, currency, line.qty, product=line.product_id, partner=line.quotation_id.partner_id or False)
                line.price_subtotal = taxes['total_excluded']
                line.price_subtotal_incl = taxes['total_included']

            line.price_subtotal = currency.round(line.price_subtotal)
            line.price_subtotal_incl = currency.round(line.price_subtotal_incl)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if not self.quotation_id.pricelist_id:
                raise UserError(
                    _('You have to select a pricelist in the sale form !\n'
                      'Please set one before choosing a product.'))
            price = self.quotation_id.pricelist_id.get_product_price(
                self.product_id, self.qty or 1.0, self.quotation_id.partner_id)
            self._onchange_qty()
            self.price_unit = price
            self.tax_ids = self.product_id.taxes_id

    @api.onchange('qty', 'discount', 'price_unit', 'tax_ids')
    def _onchange_qty(self):
        if self.product_id:
            if not self.quotation_id.pricelist_id:
                raise UserError(_('You have to select a pricelist in the sale form !'))
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
            self.price_subtotal = self.price_subtotal_incl = price * self.qty
            if (self.product_id.taxes_id):
                taxes = self.product_id.taxes_id.compute_all(price, self.quotation_id.pricelist_id.currency_id, self.qty, product=self.product_id, partner=False)
                self.price_subtotal = taxes['total_excluded']
                self.price_subtotal_incl = taxes['total_included']


class pos_config(models.Model):
    _inherit = 'pos.config' 
    
    is_call_center = fields.Boolean(string='Is Call Center')
    is_branch = fields.Boolean(string='Is a branch')

    