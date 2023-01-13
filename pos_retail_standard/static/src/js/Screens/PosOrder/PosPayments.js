odoo.define('pos_retail_standard.PosPayments', function (require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');

    class PosPayments extends PosComponent {
        constructor() {
            super(...arguments);
        }
    }

    PosPayments.template = 'PosPayments';

    Registries.Component.add(PosPayments);

    return PosPayments;
});
