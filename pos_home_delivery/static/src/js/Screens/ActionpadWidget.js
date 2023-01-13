odoo.define('pos_home_delivery.ActionpadWidget', function(require) {
	"use strict";

	let core = require('web.core');
	let _t = core._t;
	const ProductScreen = require('point_of_sale.ProductScreen'); 

	const BiProductScreen = (ProductScreen) =>
	class extends ProductScreen {
		constructor() {
			super(...arguments);
		}

		async _clickProduct(event) { 
			var self = this;
			var delivery = this.env.pos.get_order().delivery;
			if(delivery == false){
				super._clickProduct(event);
			}else{
				self.showPopup('ErrorPopup', {
					'title': _t('Add New Product'),
					'body': _t('This order already create home delivery , you can not add new product.'),
				});
			}
		}
	};
});