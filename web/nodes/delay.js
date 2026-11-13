/**
 * DELAY: while the node waits, offer this tab a prompt to continue now or cancel the run.
 */

import { api } from "../../../scripts/api.js";
import { app } from "../../../scripts/app.js";
import { apiJovimetrix } from "../util.js"
import { bubbles } from '../fun.js'

const _id = "DELAY (JOV) ✋🏽"
const EVENT_JOVI_DELAY = "jovi-delay-user";

/**
 * Show the continue / cancel prompt.
 *
 * @param {string} title - Heading text.
 * @param {number} timeout - Seconds before the prompt closes on its own.
 * @param {boolean} withBubbles - Animate bubbles behind the prompt.
 * @returns {Promise<boolean>} true to continue, false to cancel; rejects with "TIMEOUT".
 */
function showDelayPrompt(title, timeout, withBubbles) {
    return new Promise((resolve, reject) => {
        const overlay = document.createElement("div");
        Object.assign(overlay.style, {
            position: "fixed", inset: "0", zIndex: "10000",
            background: "rgba(0, 0, 0, 0.35)",
        });
        let stopBubbles = () => {};
        if (withBubbles) {
            const backdrop = document.createElement("canvas");
            Object.assign(backdrop.style, { position: "absolute", inset: "0", width: "100%", height: "100%" });
            overlay.appendChild(backdrop);
            stopBubbles = bubbles(backdrop);
        }

        const box = document.createElement("div");
        Object.assign(box.style, {
            position: "absolute", left: "50%", top: "50%", transform: "translate(-50%, -50%)",
            padding: "12px 18px", textAlign: "center",
            background: "var(--comfy-menu-bg, #222)", color: "var(--input-text, #ddd)",
            border: "2px solid rgb(95, 85, 75)", borderRadius: "6px",
        });

        const heading = document.createElement("h3");
        heading.textContent = title;
        heading.style.margin = "0 0 6px 0";
        const question = document.createElement("h4");
        question.textContent = "CANCEL OR CONTINUE RENDER?";
        question.style.margin = "0 0 10px 0";

        const row = document.createElement("div");
        row.style.display = "flex";
        row.style.gap = "12px";
        row.style.justifyContent = "center";

        let timer = null;
        const close = (value) => {
            if (timer) clearTimeout(timer);
            stopBubbles();
            overlay.remove();
            resolve(value);
        };

        for (const [label, value] of [["CONTINUE", true], ["CANCEL", false]]) {
            const button = document.createElement("button");
            button.textContent = label;
            button.style.padding = "4px 14px";
            button.addEventListener("click", () => close(value));
            row.appendChild(button);
        }

        box.append(heading, question, row);
        overlay.appendChild(box);
        document.body.appendChild(overlay);

        if (timeout) {
            timer = setTimeout(() => {
                stopBubbles();
                overlay.remove();
                reject(new Error("TIMEOUT"));
            }, timeout * 1000);
        }
    });
}

app.registerExtension({
    name: 'jovimetrix.node.' + _id,
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== _id) {
            return
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = async function () {
            const me = await onNodeCreated?.apply(this, arguments);
            const widget_enable = this.widgets?.find(w => w.name == 'enable');
            let showing = false;
            const self = this;

            async function python_delay_user(event) {
                if (showing || String(event.detail.id) != String(self.id)) {
                    return;
                }

                const time = Number(event.detail.timeout) || 0;
                showing = true;
                let value = false;
                try {
                    value = await showDelayPrompt(`DELAY NODE #${self.id}`, time, widget_enable?.value == true);
                } catch (e) {
                    if (e.message != "TIMEOUT") {
                        console.error("[Jovimetrix] delay prompt failed:", e);
                    }
                    value = true;
                }
                await apiJovimetrix(self.id, value);
                showing = false;
            }

            api.addEventListener(EVENT_JOVI_DELAY, python_delay_user);
            const onRemoved = this.onRemoved;
            this.onRemoved = function () {
                api.removeEventListener(EVENT_JOVI_DELAY, python_delay_user);
                return onRemoved?.apply(this, arguments);
            };
            return me;
        }
    }
})
