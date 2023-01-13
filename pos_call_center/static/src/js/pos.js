odoo.define('pos_call_center.pos_call_center', function(require){
    
    const models = require('point_of_sale.models');
    const ReceiptScreen = require('point_of_sale.ReceiptScreen');
    const PosComponent = require('point_of_sale.PosComponent');
    const { useListener } = require('web.custom_hooks');
    const Registries = require('point_of_sale.Registries');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
    const { useState, useRef } = owl.hooks;
    const { posbus } = require('point_of_sale.utils');
    const { debounce } = owl.utils;

    models.load_models({
        model: 'pos.config',
        fields: ['id','name'],
        domain: function(self){ return [['is_branch','=',true]]; },
        loaded: function(self, pos_config){
            self.kitchens = pos_config;
        },
    });

	models.load_models({
	    model: 'pos.quotation',
	    fields: ['id','name','delivery_date','amount_total','stock_location','partner_id','lines','state','branch_id'],
	    domain: function(self){ return [['state','in',['sent','confirm']]]; },
	    loaded: function(self,quotations){
	    	self.quotations = quotations;
	    },
	});


	var _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        initialize: function() {
            _super_order.initialize.apply(this,arguments);
            this.wv_note = "";
            this.save_to_db();
            this.quotation_id = "";
            this.quot_id = false;
        },
        export_as_JSON: function() {
            var json = _super_order.export_as_JSON.apply(this,arguments);
            json.wv_note = this.wv_note;
            json.delivery_date = this.delivery_date;
            json.branch_id = this.branch_id;
            json.priority = this.priority;
            json.quotation_id = this.quotation_id;
            json.quot_id = this.quot_id;
            return json;
        },
        init_from_JSON: function(json) {
            _super_order.init_from_JSON.apply(this,arguments);
            this.wv_note = json.wv_note;
            this.quotation_id = json.quotation_id;
            this.quot_id = json.quot_id;
        },
    });
    var _super_orderline = models.Orderline.prototype;
    models.Orderline = models.Orderline.extend({
        initialize: function(attr, options) {
            _super_orderline.initialize.call(this,attr,options);
            this.extra_note = this.extra_note || "";
        },
        set_extra_note: function(extra_note){
            this.extra_note = extra_note;
            this.trigger('change',this);
        },
        get_extra_note: function(){
            return this.extra_note;
        },
        export_as_JSON: function(){
            var json = _super_orderline.export_as_JSON.call(this);
            json.extra_note = this.extra_note;
            return json;
        },
        init_from_JSON: function(json){
            _super_orderline.init_from_JSON.apply(this,arguments);
            this.extra_note = json.extra_note;
        },
        export_for_printing: function(){
            var data = _super_orderline.export_for_printing.apply(this, arguments);
            data.extra_note = this.extra_note || "";
            return data;
        }
    });

    class CreateQuotationButton extends PosComponent {
        constructor() {
            super(...arguments);
            useListener('click', this.onClick);
        }
        async onClick() {
            var self = this;
            await this.showPopup('CreateQuotationPopupWidget');
        }
    }
    CreateQuotationButton.template = 'CreateQuotationButton';

    ProductScreen.addControlButton({
        component: CreateQuotationButton,
        condition: function() {
            return this.env.pos.config.is_call_center;
        },
    });

    Registries.Component.add(CreateQuotationButton);

    class PosExtNotePopupWidget extends AbstractAwaitablePopup {
        constructor() {
            super(...arguments);
            this.state = useState({ inputValue: this.props.startingValue });
            this.inputRef = useRef('input');
        }
        mounted() {
            this.inputRef.el.focus();
        }
        getPayload() {
            return this.state.inputValue;
        }
        shortcut_button(event){
            const value = event.target.innerHTML;
            this.state.inputValue += (" "+value)  
        }
    }
    PosExtNotePopupWidget.template = 'PosExtNotePopupWidget';
    Registries.Component.add(PosExtNotePopupWidget);

   	class OrderlineNoteExButton extends PosComponent {
        constructor() {
            super(...arguments);
            useListener('click', this.onClick);
        }
        get selectedOrderline() {
            return this.env.pos.get_order().get_selected_orderline();
        }
        async onClick() {
            if (!this.selectedOrderline) return;

            const { confirmed, payload: inputNote } = await this.showPopup('PosExtNotePopupWidget', {
                startingValue: this.selectedOrderline.get_extra_note(),
                title: this.env._t('Add Note'),
                wv_order_note:this.env.pos.wv_order_note,
            });

            if (confirmed) {
                this.selectedOrderline.set_extra_note(inputNote);
            }
        }
    }
    OrderlineNoteExButton.template = 'OrderlineNoteExButton';

    ProductScreen.addControlButton({
        component: OrderlineNoteExButton,
        condition: function() {
            return this.env.pos.config.is_call_center;
        },
    });

    Registries.Component.add(OrderlineNoteExButton);

    class CreateQuotationPopupWidget extends AbstractAwaitablePopup {
        constructor() {
            super(...arguments);
            this.state = useState({ inputValue: this.props.startingValue });
            // this.inputRef = useRef('input');
        }
        getPayload() {
            return this.state.inputValue;
        }
        async transfer_order(){
        	var order =this.env.pos.get('selectedOrder');
            if(order.get_client() != null){
            	order.wv_note = $(".wv_note").val();
            	var sDate = new Date(Date.parse($(".delivery_date").val(),"dd/MM/yyyy T HH:mm"));
            	order.branch_id = parseInt($(".order_kitchen").val());
            	order.priority = parseInt($(".order_priorty").val());
            	order.delivery_date = sDate.getFullYear()+"-"+(sDate.getMonth()+1)+"-"+sDate.getDate()+" "+sDate.getHours()+":"+sDate.getMinutes()+":"+sDate.getSeconds();
            	await this.save_order();
                await this.trigger('close-popup');
            }
            else{
             	alert("Customer is required for sale order. Please select customer first !!!!");
            }
        }
        save_order(){
            var self = this;
            var order = self.env.pos.get_order();
            var data = order.export_as_JSON();

            return  self.rpc({
                      model: 'pos.quotation',
                      method: 'create_new_quotation',
                      args: [data],
            }).then(function (quotation_data) {
                while(order.get_orderlines().length > 0){
                    var line = order.get_selected_orderline();
                    order.remove_orderline(line);
                }
                order.set_client(null);
                // self.env.pos.quotations.push(quotation_data['result'][0]);
            });
        }

        async print_transfer_order(){
            var order =this.env.pos.get('selectedOrder');
            if(order.get_client() != null){
                order.wv_note = $(".wv_note").val();
                var sDate = new Date(Date.parse($(".delivery_date").val(),"dd/MM/yyyy T HH:mm"));
                order.branch_id = parseInt($(".order_kitchen").val());
                order.priority = parseInt($(".order_priorty").val());
                order.delivery_date = sDate.getFullYear()+"-"+(sDate.getMonth()+1)+"-"+sDate.getDate()+" "+sDate.getHours()+":"+sDate.getMinutes()+":"+sDate.getSeconds();
                await this.save_order2();
                await this.trigger('close-popup');
            }
            else{
                alert("Customer is required for sale order. Please select customer first !!!!");
            }
        }

        save_order2(){
            var self = this;
            var order = self.env.pos.get_order();
            var data = order.export_as_JSON();

            return  self.rpc({
                      model: 'pos.quotation',
                      method: 'create_new_quotation',
                      args: [data],
            }).then(function (quotation_data) {
                    self.env.pos.quotations.push(quotation_data['result'][0]);
                    order.order_ref = quotation_data['result'];
                    order.quotation_id = quotation_data['result'][0].name;
                    self.showTempScreen('QuotationBillScreenWidget')
            });
        }


    }
    CreateQuotationPopupWidget.template = 'CreateQuotationPopupWidget';
    Registries.Component.add(CreateQuotationPopupWidget);

    const QuotationBillScreenWidget = (ReceiptScreen) => {
        class QuotationBillScreenWidget extends ReceiptScreen {
            confirm() {
                var order = this.env.pos.get_order();
                while(order.get_orderlines().length > 0){
                    var line = order.get_selected_orderline();
                    order.remove_orderline(line);
                }
                order.set_client(null);
                this.props.resolve({ confirmed: true, payload: null });
                this.trigger('close-temp-screen');
            }
        }
        QuotationBillScreenWidget.template = 'QuotationBillScreenWidget';
        return QuotationBillScreenWidget;
    };

    Registries.Component.addByExtending(QuotationBillScreenWidget, ReceiptScreen); 

    class QuotationListButton extends PosComponent {
        constructor() {
            super(...arguments);
            useListener('click', this.onClick);
        }
        async onClick() {
            var self = this;
            var available_qt = []
            var config_id = self.env.pos.config.id

            self.rpc({
              model: 'pos.quotation',
              method: 'new_sent_order_json',
              args: [available_qt,config_id],
                }).then(function (quotation_data) {
                     self.env.pos.quotations = [];
                     var quot_data = quotation_data['data']
                     for(var k=0;k<quot_data.length;k++){
                         self.env.pos.quotations.push(quot_data[k][0]);
                     }
                     self.showTempScreen('QuotationListScreenWidget')
                });
            }
    }
    QuotationListButton.template = 'QuotationListButton';

    ProductScreen.addControlButton({
        component: QuotationListButton,
        condition: function() {
            return this.env.pos.config.is_call_center;
        },
    });

    Registries.Component.add(QuotationListButton);

    class QuotationListScreenWidget extends PosComponent {
        constructor() {
            super(...arguments);
            this.state = {
                query: null,
                selectedClient: this.props.client,
                detailIsShown: false,
                isEditMode: false,
                editModeProps: {
                    partner: {
                        country_id: this.env.pos.company.country_id,
                        state_id: this.env.pos.company.state_id,
                    }
                },
            };
            this.updateClientList = debounce(this.updateClientList, 70);
        }

        back() {
            this.trigger('close-temp-screen');
        }


        get currentOrder() {
            return this.env.pos.get_order();
        }
        perform_search(query){
        var quotations = this.env.pos.quotations;
        var results = [];
            for(var i = 0; i < quotations.length; i++){
                var res = this.search_quotations(query, quotations[i]);
                if(res != false){
                    results.push(res);
                }
            }
            return results;
        }
        search_quotations(query,quotations){
            try {
                query = query.replace(/[\[\]\(\)\+\*\?\.\-\!\&\^\$\|\~\_\{\}\:\,\\\/]/g,'.');
                query = query.replace(' ','.+');
                var re = RegExp("([0-9]+):.*?"+query,"gi");
            }catch(e){
                return [];
            }
            var results = [];
            var r = re.exec(this._quotations_search_string(quotations));
            if(r){
                var id = Number(r[1]);
                return this.get_quotations_by_id(id);
            }
            return false;
        }
        get_quotations_by_id(id){
            var quotations = this.env.pos.quotations;
            for(var i=0;i<quotations.length;i++){
                if(quotations[i].id == id){
                    return quotations[i];
                }
            }
        }
        _quotations_search_string(quotations){
            var str =  quotations.name;
            if(quotations.partner_id){
                str += '|' + quotations.partner_id[1];
            }
            str = '' + quotations.id + ':' + str.replace(':','') + '\n';
            return str;
         }
        get clients() {
            if (this.state.query && this.state.query.trim() !== '') {
                return this.perform_search(this.state.query.trim());
            } else {
                return this.env.pos.quotations;
            }
        }
        updateClientList(event) {
            this.state.query = event.target.value;
            this.render();
        }

    }
    QuotationListScreenWidget.template = 'QuotationListScreenWidget';

    Registries.Component.add(QuotationListScreenWidget);

    class QuotationLine extends PosComponent {

    }
    QuotationLine.template = 'QuotationLine';

    Registries.Component.add(QuotationLine);

    class ReceivedorderButton extends PosComponent {
        constructor() {
            super(...arguments);
            useListener('click', this.onClick);
        }
        async onClick() {
            var self = this;
            var available_qt = []
            var config_id = self.env.pos.config.id;

            self.rpc({
              model: 'pos.quotation',
              method: 'read_order_json',
              args: [available_qt,config_id],
                }).then(function (quotation_data) {
                     self.env.pos.branch_quotations = [];
                     var quot_data = quotation_data['data']
                     for(var k=0;k<quot_data.length;k++){
                         self.env.pos.branch_quotations.push(quot_data[k]);
                     }
                     self.showTempScreen('KitchenScreenWidget');
                });
            }
    }
    ReceivedorderButton.template = 'ReceivedorderButton';

    ProductScreen.addControlButton({
        component: ReceivedorderButton,
        condition: function() {
            return this.env.pos.config.is_branch;
        },
    });

    Registries.Component.add(ReceivedorderButton);

    class KitchenScreenWidget extends PosComponent {
        constructor() {
            super(...arguments);
            this.state = {
                arrangement: 'ascending',
                order_prior: 'all',
            };
        }
        back() {
            this.trigger('close-temp-screen');
        }
        order_arrangement(event){
            this.state.arrangement = event.target.value;
            this.render();
        }
        order_prior(event){
            this.state.order_prior = event.target.value;
            this.render();
        }
        get branch_quotations() {
            var self = this;
            var order_arrangement = this.state.arrangement;
            var order_prior = this.state.order_prior;
            var kitchen_data = [].concat(self.env.pos.branch_quotations);
            var receipt =[];
            var new_order_list = [];
            for(var i=0;i<kitchen_data.length-1;i++){
              var smallest_date = new Date(Date.parse(kitchen_data[i].delivery_date,"YYYY-MM-DD HH:mm:ss"));
              var new_order = kitchen_data[i];
              for(var j=i+1;j<kitchen_data.length;j++){
                  var sec_date = new Date(Date.parse(kitchen_data[j].delivery_date,"YYYY-MM-DD HH:mm:ss"));
                  if(order_arrangement == 'ascending'){
                    if(smallest_date - sec_date > 0){
                      var sec_ord = kitchen_data[j];
                      kitchen_data[j] = kitchen_data[i];
                      kitchen_data[i] = sec_ord;
                    }
                  }
                  else{
                    if(smallest_date - sec_date < 0){
                      var sec_ord = kitchen_data[j];
                      kitchen_data[j] = kitchen_data[i];
                      kitchen_data[i] = sec_ord;
                    }
                  }
              }
            }
            for(var i=0;i<kitchen_data.length;i++){
                if(order_prior == '0'){
                  if(kitchen_data[i].order_priority == 0){
                    receipt.push(kitchen_data[i]);
                  }
                }
                else if(order_prior == '1'){
                  if(kitchen_data[i].order_priority == 1){
                    receipt.push(kitchen_data[i]);
                  }
                }
                else if(order_prior == '2'){
                  if(kitchen_data[i].order_priority == 2){
                    receipt.push(kitchen_data[i]);
                  }
                }
                else{
                    receipt.push(kitchen_data[i]);
                }
            }
            return receipt;
        }

        kitchen_order(index){
            var self = this;
            var id = 0;
            var kitchen_data = this.env.pos.branch_quotations;
            for(var i=0;i<kitchen_data.length;i++){
                  if(kitchen_data[i].id == index){
                    id = i;
                }
            }
            if(kitchen_data[id].is_hidden){
                for(var i=0;i<kitchen_data.length;i++){
                  kitchen_data[i].is_hidden = true;
                }
                kitchen_data[id].is_hidden = false;
            }
            else{
                for(var i=0;i<kitchen_data.length;i++){
                  kitchen_data[i].is_hidden = true;
                }
                kitchen_data[id].is_hidden = true;
            }
            self.render();
        }

        wv_transfer_order(event){
            var self = this;
            var id = parseInt($(event.target).data('id'));
            var kitchen_id = parseInt($(event.target).closest('td').find('.transfer_order_kitchen').val());
            if(kitchen_id == 0){
              alert("Please select kitchen first.");
            }
            else{
                self.rpc({
                  model: 'pos.quotation',
                  method: 'transfer_order',
                  args: [id,kitchen_id],
                }).then(function (quotation_data) {
                    var kitchen = self.env.pos.branch_quotations;
                    for(var t=0;t<kitchen.length;t++){
                        if(kitchen[t].id == id){
                            self.env.pos.branch_quotations.splice(t, 1);
                            break;
                        }
                    }
                    self.render();
                    self.render();
                });
            }
        }
        order_deliver(id){
            var self = this;
            self.rpc({
                    model: 'pos.quotation',
                    method: 'deliver_order',
                    args: [id],
                }).then(function(quotation_data){
                    var kitchen = self.env.pos.branch_quotations;
                    for(var t=0;t<kitchen.length;t++){
                        if(kitchen[t].id == id){
                            self.env.pos.branch_quotations.splice(t, 1);
                            break;
                        }
                    }
                    var order = self.env.pos.get_order();
                    var orderlines = order.get_orderlines();
                    if(orderlines.length == 0){
                    self.rpc({
                            model: 'pos.quotation',
                            method: 'quotation_fetch_line',
                            args: [id],
                        }).then(function(result){
                            order.set('client',undefined);
                            order.quotation_id = result['name'];
                            order.quot_id = id;
                            if(result['partner_id']){
                                order.set_client(self.env.pos.db.get_partner_by_id(result['partner_id']));
                            }
                            var quotation_data = result['orderline'];
                            for(var i=0;i<quotation_data.length;i++){
                                var product = self.env.pos.db.get_product_by_id(quotation_data[i]['product_id'][0]);
                                order.add_product(product,{'quantity':quotation_data[i]['qty'],'discount':quotation_data[i]['discount']});
                            }
                            self.back();
                        });

                }
                else{

                    alert(_t('Please remove all products from cart and try again.'));
                }
            });
        }
    }

    KitchenScreenWidget.template = 'KitchenScreenWidget';
    Registries.Component.add(KitchenScreenWidget);
});
