/**
 * QUEUE and QUEUE TOO: a read-only report of the current entry, and reset on edit.
 */

import { api } from "../../../scripts/api.js";
import { app } from "../../../scripts/app.js";
import { addTextDisplay, apiJovimetrix, widgetElement, TypeSlotEvent, TypeSlot } from "../util.js"
import { flashBackgroundColor } from '../fun.js'

const _id1 = "QUEUE (JOV) 🗃";
const _id2 = "QUEUE TOO (JOV) 🗃";
const _prefix = '❔';
const EVENT_JOVI_PING = "jovi-queue-ping";
const EVENT_JOVI_DONE = "jovi-queue-done";

app.registerExtension({
	name: 'jovimetrix.node.' + _id1,
	async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name != _id1 && nodeData.name != _id2) {
            return;
        }

        function update_report(self) {
            const total = self.data_total ?? self.data_all.length;
            self.widget_report.value = `[${self.data_index+1} / ${total}]\n${self.data_current}`;
            app.canvas.setDirty(true);
        }

        function update_list(self, value) {
            self.data_count = value.length;
            self.data_total = value.length;
            self.data_index = 1;
            self.data_current = "";
            update_report(self);
            apiJovimetrix(self.id, "reset");
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = async function () {
            const me = await onNodeCreated?.apply(this, arguments);
            const self = this;
            this.data_index = 1;
            this.data_current = "";
            this.data_all = [];
            this.widget_report = addTextDisplay(this, 'QUEUE IS EMPTY 🔜');

            const widget_queue = this.widgets.find(w => w.name == 'queue');
            const widget_batch = this.widgets.find(w => w.name == 'batch');
            const widget_hold = this.widgets.find(w => w.name == 'hold');
            const widget_reset = this.widgets.find(w => w.name == 'reset');

            widgetElement(widget_queue)?.addEventListener('input', function () {
                const value = String(widget_queue.value ?? "").split('\n');
                update_list(self, value);
            });

            widget_reset.callback = () => {
                widget_reset.value = false;
                apiJovimetrix(self.id, "reset");
            }

            async function python_queue_ping(event) {
                if (String(event.detail.id) != String(self.id)) {
                    return;
                }
                self.data_index = event.detail.i;
                self.data_all = Array.isArray(event.detail.l) ? event.detail.l : [];
                self.data_total = Number(event.detail.s) || self.data_all.length;
                self.data_current = String(event.detail.c ?? "");
                update_report(self);
            }

            async function python_queue_done(event) {
                const element = widgetElement(widget_queue);
                if (String(event.detail.id) != String(self.id) || !element) {
                    return;
                }
                await flashBackgroundColor(element, 650, 4, "#995242CC");
            }

            api.addEventListener(EVENT_JOVI_PING, python_queue_ping);
            api.addEventListener(EVENT_JOVI_DONE, python_queue_done);

            const onRemoved = this.onRemoved;
            this.onRemoved = function () {
                api.removeEventListener(EVENT_JOVI_PING, python_queue_ping);
                api.removeEventListener(EVENT_JOVI_DONE, python_queue_done);
                return onRemoved?.apply(this, arguments);
            };

            setTimeout(() => { widget_hold?.callback?.(); }, 5);
            setTimeout(() => { widget_batch?.callback?.(); }, 5);
            return me;
        }

        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (slotType, slot, event, link_info) {
            const me = onConnectionsChange?.apply(this, arguments);
            // A connection made by hand from the first output into a menu fills the queue with
            // the menu's entries; links restored while a workflow loads leave the queue as saved.
            if (app.configuringGraph || slotType != TypeSlot.Output || slot != 0 || !link_info
                    || event != TypeSlotEvent.Connect) {
                return me;
            }
            const node = app.graph?.getNodeById(link_info.target_id);
            const target = node?.inputs?.[link_info.target_slot];
            const widget = target ? node.widgets?.find(w => w.name == target.name) : undefined;
            const values = widget?.options?.values;
            if ((widget?.origType == "combo" || widget?.type == "combo" || widget?.type == "COMBO")
                    && Array.isArray(values)) {
                const widget_queue = this.widgets?.find(w => w.name == 'queue');
                if (widget_queue) {
                    widget_queue.value = values.join('\n');
                    update_list(this, values);
                }
            }
            return me;
        };
    }
})
