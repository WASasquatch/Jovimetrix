/**
 * AKASHIC: a growing set of inputs, and one read-only text box per input after each run.
 */

import { app } from "../../../scripts/app.js"
import { addTextDisplay, nodeAddDynamic, nodeFitHeight } from "../util.js"

const _prefix = '📥'
const _id = "AKASHIC (JOV) 📓"

app.registerExtension({
    name: 'jovimetrix.node.' + _id,
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== _id) {
            return
        }

        await nodeAddDynamic(nodeType, _prefix);

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = async function (message) {
            const me = onExecuted?.apply(this, arguments);
            for (const widget of [...(this.widgets || [])]) {
                this.removeWidget(widget);
            }

            const texts = Array.isArray(message?.text) ? message.text : [];
            const inputs = (this.inputs || []).slice(0, -1);
            inputs.forEach((input, i) => {
                let raw = String(texts[i] ?? "").replace(/\\n/g, '\n').replace(/"/g, '');
                try {
                    raw = JSON.parse('"' + raw.replace(/"/g, '\\"') + '"');
                } catch (e) {
                    console.debug("[Jovimetrix] AKASHIC text shown undecoded:", e.message);
                }
                addTextDisplay(this, input.name, `${input.name} ${raw}`);
            });
            nodeFitHeight(this);
            return me;
        }
    }
})
