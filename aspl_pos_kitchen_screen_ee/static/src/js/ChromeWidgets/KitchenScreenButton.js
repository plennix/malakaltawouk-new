odoo.define('aspl_pos_kitchen_screen_ee.KitchenScreenButton', function(require) {
    'use strict';

    const { useState } = owl;
    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');


    class KitchenScreenButton extends PosComponent {
        constructor() {
            super(...arguments);
        }
        onClick() {
            this.trigger('click-kitchen-screen');
        }
    }
    KitchenScreenButton.template = 'KitchenScreenButton';

    Registries.Component.add(KitchenScreenButton);

    return KitchenScreenButton;
});
