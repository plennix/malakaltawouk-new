# -*- coding: utf-8 -*-

{
    'name': 'Pos Call Center',
    'version': '1.0',
    'category': 'Point of Sale',
    'sequence': 6,
    'author': 'Webveer',
    'summary': 'Pos Call center module allows you to create call centers and branches.',
    'description': """

=======================

Pos Call center module allows you to create call centers and branches.

""",
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/sequence.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'pos_call_center/static/src/css/pos.css',
            'pos_call_center/static/src/js/pos.js',
        ],
        'web.assets_qweb': [
            'pos_call_center/static/src/xml/**/*',
        ],
    },
    'images': [
        'static/description/transfer.jpg',
    ],
    'installable': True,
    'website': '',
    'auto_install': False,
    'price': 199,
    'currency': 'USD',
}

