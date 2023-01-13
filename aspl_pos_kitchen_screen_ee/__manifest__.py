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
{
    'name': 'POS Kitchen screen (Enterprise)',
    'version': '1.0.1',
    'category': 'Point of Sale',
    'website': 'http://www.acespritech.com',
    'price': 120.0,
    'currency': 'EUR',
    'summary': "A Screen for kitchen staff.",
    'description': "POS kitchen Screen shows orders and their state to Cook and Manager and Waiter",
    'author': "Acespritech Solutions Pvt. Ltd.",
    'website': "www.acespritech.com",
    'depends': ['point_of_sale', 'bus', 'pos_restaurant'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_config.xml',
        'views/res_users_view.xml',
        'views/remove_product_resion_view.xml',
        'views/pos_order_view.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'aspl_pos_kitchen_screen_ee/static/src/**/*'
        ],
        'web.assets_qweb': [
            'aspl_pos_kitchen_screen_ee/static/src/xml/**/*'
        ],
    },
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
