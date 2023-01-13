odoo.define('aspl_pos_kitchen_screen_ee.ProductScreen', function(require) {
    'use strict';

    const ProductScreen = require('point_of_sale.ProductScreen')
    const PosComponent = require('point_of_sale.PosComponent');
    const ControlButtonsMixin = require('point_of_sale.ControlButtonsMixin');
    const NumberBuffer = require('point_of_sale.NumberBuffer');
    const { useListener } = require('web.custom_hooks');
    const Registries = require('point_of_sale.Registries');
    const { onChangeOrder, useBarcodeReader } = require('point_of_sale.custom_hooks');
    const { useState } = owl.hooks;


    const AsplKitchenProductScreen = ProductScreen =>
        class extends ProductScreen {
            constructor() {
                super(...arguments);
                useListener('set-order-type-mode', this._setOrderTypeMode);
            }
            _setOrderTypeMode(event) {
                const { mode } = event.detail;
                this.state.orderTypeMode = mode;
            }
            async _setValue(val){
                let line = this.currentOrder.get_selected_orderline();
                if(line === undefined){
                    super._setValue(...arguments);
                    return;
                }
                if(line.state != 'Waiting' && this.state.numpadMode === 'quantity'){
                    this.showNotification('You can not change the quantity!')
                }else{
                    super._setValue(...arguments);
                }
            }
            async _onClickPay() {
                if(this.env.pos.user.kitchen_screen_user === "manager"){
                    await super._onClickPay();
                }else{
                    return;
                }
            }
        };

    Registries.Component.extend(ProductScreen, AsplKitchenProductScreen);

    return ProductScreen;
});
