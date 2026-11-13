/**
 * GRAPH: a growing set of inputs, each link coloured like its line in the chart, and a reset.
 */

import { app } from "../../../scripts/app.js"
import { apiJovimetrix, nodeAddDynamic } from "../util.js"

const _id = "GRAPH (JOV) 📈"
const _prefix = '❔'

const LINE_COLORS = ["#d62728", "#2ca02c", "#1f77b4", "#17becf", "#bcbd22", "#9467bd", "#808080"];

app.registerExtension({
    name: 'jovimetrix.node.' + _id,
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== _id) {
            return;
        }

        await nodeAddDynamic(nodeType, _prefix);

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = async function () {
            const me = await onNodeCreated?.apply(this, arguments);
            const self = this;
            const widget_reset = this.widgets?.find(w => w.name == 'reset');
            if (widget_reset) {
                widget_reset.callback = async () => {
                    widget_reset.value = false;
                    apiJovimetrix(self.id, "reset");
                }
            }
            return me;
        }

        const onConnectionsChange = nodeType.prototype.onConnectionsChange
        nodeType.prototype.onConnectionsChange = function () {
            const me = onConnectionsChange?.apply(this, arguments);
            let count = 0;
            (this.inputs || []).forEach((input, i) => {
                if (!/^\d+_/.test(input.name)) {
                    return;
                }
                const link = this.getInputLink(i);
                if (link) {
                    link.color = LINE_COLORS[count % LINE_COLORS.length];
                    count += 1;
                }
            });
            app.graph.setDirtyCanvas(true, true);
            return me;
        }
    }
})
