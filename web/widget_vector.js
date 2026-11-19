/**
 * The VEC2, VEC3 and VEC4 widget: one field per component, typed, dragged or picked as a colour.
 *
 * The same behaviour is installed on the widget a subgraph shows when a vector input inside it
 * is wired to a subgraph input, so the vector stays editable from outside the subgraph.
 */

import { app } from "../../scripts/app.js"
/** @import { IWidget, LGraphCanvas } from '../../types/litegraph/litegraph.d.ts' */

/**
 * Evaluate arithmetic typed into a field: numbers, + - * /, parentheses and unary minus.
 *
 * @param {string} text - The typed text.
 * @returns {number} The value, or NaN when the text is not arithmetic.
 */
function evaluateArithmetic(text) {
    const tokens = String(text).match(/\d+\.?\d*(?:e[+-]?\d+)?|\.\d+(?:e[+-]?\d+)?|[-+*/()]|\S/gi) || [];
    let pos = 0;
    const peek = () => tokens[pos];
    const take = () => tokens[pos++];

    function primary() {
        const token = take();
        if (token === "(") {
            const value = sum();
            if (take() !== ")") return NaN;
            return value;
        }
        if (token === "-") return -primary();
        if (token === "+") return primary();
        const value = Number(token);
        return Number.isFinite(value) ? value : NaN;
    }
    function product() {
        let value = primary();
        while (peek() === "*" || peek() === "/") {
            value = take() === "*" ? value * primary() : value / primary();
        }
        return value;
    }
    function sum() {
        let value = product();
        while (peek() === "+" || peek() === "-") {
            value = take() === "+" ? value + product() : value - product();
        }
        return value;
    }

    if (tokens.length === 0 || tokens.length > 256) return NaN;
    const result = sum();
    return pos === tokens.length && Number.isFinite(result) ? result : NaN;
}

const VECTOR_TYPES = new Set(["VEC1", "VEC2", "VEC3", "VEC4"]);

/**
 * A vector value as a new array, so no two widgets, and no widget and its node definition's
 * default, ever hold the same object.
 *
 * @param {Array|Object|undefined} value - The value, as an array or an {0: x, 1: y} object.
 * @param {Array} [fallback] - Used when value is missing.
 * @returns {Array} The components.
 */
function vectorCopy(value, fallback = []) {
    const source = value ?? fallback;
    if (Array.isArray(source)) return [...source];
    return source && typeof source == "object" ? Object.values(source) : [...fallback];
}

/**
 * Give a widget a new value, then tell the node: property binding and callback.
 *
 * @param {Object} node - The node the widget sits on.
 * @param {IWidget} widget - The vector widget.
 * @param {Array} values - The new components.
 * @param {Array} [pos] - Pointer position, passed on to the callback.
 * @param {Event} [event] - Pointer event, passed on to the callback.
 */
function applyValue(node, widget, values, pos = undefined, event = undefined) {
    const options = widget.options ?? {};
    const convert = (options.rgb || options.int) ? Number : parseFloat;
    widget.value = vectorCopy(values).map((v) => convert(v));
    if (
        widget.options &&
        widget.options.property &&
        node.properties?.[widget.options.property] !== undefined
        ) {
            node.setProperty(widget.options.property, widget.value)
        }
    widget.callback?.(widget.value, app.canvas, node, pos, event);
}

function colorHex2RGB(hex) {
    hex = hex.replace(/^#/, '');
    const bigint = parseInt(hex, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return [r, g, b];
}

function colorRGB2Hex(input) {
    const rgbArray = typeof input == 'string' ? input.match(/\d+/g) : input;
    if (rgbArray.length < 3) {
        throw new Error('input not 3 or 4 values');
    }
    const hexValues = rgbArray.map((value, index) => {
        if (index == 3 && !value) return 'ff';
        const hex = parseInt(value).toString(16);
        return hex.length == 1 ? '0' + hex : hex;
    });
    return '#' + hexValues.slice(0, 3).join('') + (hexValues[3] || '');
}

/**
 * Settle the display settings of a vector input: precision, step and, for colours, the 0 to
 * 255 range and channel labels.
 *
 * @param {Object} options - The widget's own copy of the input's options.
 * @returns {Object} The options.
 */
function vectorOptions(options) {
    options.precision = options.precision || 2;
    options.step = options.step || 0.1;
    if (options.rgb || options.int) {
        options.step = 1;
        options.precision = 0;
    }
    if (options.rgb) {
        options.maj = 255;
        options.mij = 0;
        options.label = ['🟥', '🟩', '🟦', 'ALPHA'];
    }
    return options;
}

/**
 * Keep a component inside the input's range and precision.
 *
 * @param {IWidget} widget - The vector widget.
 * @param {number} v - The component.
 * @returns {number} The kept value.
 */
function clampComponent(widget, v) {
    const options = widget.options ?? {};
    v = Math.min(v, options.maj !== undefined ? options.maj : v);
    v = Math.max(v, options.mij !== undefined ? options.mij : v);
    return (options.precision == 0) ? Number(v) : parseFloat(parseFloat(v).toFixed(options.precision));
}

const offset_y = 4;
const widget_padding_left = 13;
const widget_padding = 30;
const label_full = 72;
const label_center = label_full / 2;

/**
 * Give a widget object the vector behaviour: drawing, typing, dragging, colour picking and
 * serialising. Works on the widget this file creates and on the widget a subgraph shows for a
 * promoted vector input, whose value lives in the frontend's widget store.
 *
 * @param {IWidget} widget - The widget; it needs name, type, options and a value.
 * @returns {IWidget} The same widget.
 */
function installVector(widget) {
    /** @type {HTMLInputElement} */
    let picker;

    widget.draw = function(ctx, node, width, Y, height) {
        if ((app.canvas.ds.scale < 0.50) || (!String(widget.type).startsWith("VEC"))) return;
        const label = String(widget.label ?? widget.name ?? "");
        const options = widget.options ?? {};
        ctx.save()
        ctx.beginPath()
        ctx.lineWidth = 1
        ctx.fillStyle = LiteGraph.WIDGET_OUTLINE_COLOR
        ctx.roundRect(widget_padding_left+2, Y, width - widget_padding, height, 15)
        ctx.stroke()
        ctx.lineWidth = 1
        ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR
        ctx.roundRect(widget_padding_left+2, Y, width - widget_padding, height, 15)
        ctx.fill()

        // label
        ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR
        ctx.fillText(label, label_center - (label.length * 1.5), Y + height / 2 + offset_y)
        let x = label_full + 1

        const values = vectorCopy(widget.value);
        let count = values.length;
        if (options.rgb) {
            count += 0.23;
        }
        const element_width = (width - label_full - widget_padding) / count;
        const element_width2 = element_width / 2;

        let converted = [];
        for (let idx = 0; idx < values.length; idx++) {
            ctx.save()
            ctx.beginPath()
            ctx.fillStyle = LiteGraph.WIDGET_OUTLINE_COLOR
            // separation bar
            ctx.moveTo(x, Y)
            ctx.lineTo(x, Y+height)
            ctx.stroke();

            // value
            ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR
            const it = values[idx];
            let value = (options.precision == 0) ? Number(it) : parseFloat(it).toFixed(options.precision);
            converted.push(value);
            const text = value.toString();
            ctx.fillText(text, x + element_width2 - text.length * 3.3, Y + height/2 + offset_y);
            ctx.restore();
            x += element_width;
        }

        if (options.rgb && converted.length > 2) {
            try {
                ctx.fillStyle = colorRGB2Hex(converted);
            } catch (e) {
                console.error(converted, e);
                ctx.fillStyle = "#FFF";
            }
            ctx.roundRect(width-1.17 * widget_padding, Y+1, 19, height-2, 16);
            ctx.fill()
        }
        ctx.restore()
    }

    /**
     * Click a field to type a value, drag across it to step it, click the label with shift to
     * reset, and click the swatch of a colour widget to pick a colour.
     */
    widget.onPointerDown = function (pointer, node, canvas) {
        const e = pointer.eDown
        const x = e.canvasX - node.pos[0] - label_full;
        const size = vectorCopy(widget.value).length;
        const element_width = (node.size[0] - label_full - widget_padding * 1.25) / size;
        const index = Math.floor(x / element_width);

        pointer.onClick = (eUp) => {
            const options = widget.options ?? {};
            /* if click on header, reset to defaults */
            if (index == -1 && eUp.shiftKey) {
                applyValue(node, widget, vectorCopy(options.default, vectorCopy(widget.value)));
                return;
            }
            else if (index >= 0 && index < size) {
                const pos = [eUp.canvasX - node.pos[0], eUp.canvasY - node.pos[1]]
                const old_value = vectorCopy(widget.value);
                const label = options.label ? widget.name + '➖' + options.label[index] : widget.name;

                (canvas ?? app.canvas).prompt(label, old_value[index], function(v) {
                    const parsed = evaluateArithmetic(v);
                    v = Number.isNaN(parsed) ? old_value[index] : parsed;

                    if (old_value[index] != v) {
                        setTimeout(function () {
                            const next = vectorCopy(widget.value);
                            next[index] = clampComponent(widget, v);
                            applyValue(node, widget, next, pos, eUp);
                        }, 5)
                    }
                }, eUp);
                return;
            }
            if (!options.rgb) return;

            const rgba = vectorCopy(widget.value);
            const color = colorRGB2Hex(rgba.slice(0, 3));

            if (index != size && (x < 0 && rgba.length > 2)) {
                const inverted = rgba.slice(0, 3).map((item) => 255 - item);
                applyValue(node, widget, [...inverted, ...rgba.slice(3)]);
                return
            }

            if (!picker) {
                picker = document.createElement("input");
                picker.type = "color";
                Object.assign(picker.style, {
                    position: "fixed",
                    left: `${eUp.clientX}px`,
                    top: `${eUp.clientY}px`,
                    height: "0px",
                    width: "0px",
                    padding: "0px",
                    opacity: 0,
                });
                document.body.appendChild(picker);
                picker.addEventListener('blur', () => picker.style.display = 'none')
                picker.addEventListener('input', () => {
                    if (!picker.value) return;
                    // The alpha is read now, not when the picker was first opened.
                    const current = vectorCopy(widget.value);
                    applyValue(node, widget, [...colorHex2RGB(picker.value), ...current.slice(3)]);
                    (canvas ?? app.canvas).setDirty(true)
                })
            } else {
                picker.style.display = 'revert'
                picker.style.left = `${eUp.clientX}px`
                picker.style.top = `${eUp.clientY}px`
            }
            picker.value = color;
            requestAnimationFrame(() => {
                picker.showPicker()
                picker.focus()
            })
        }

        pointer.onDrag = (eMove) => {
            if (!eMove.deltaX || !(index > -1)) return;
            if (index >= size) return;
            const next = vectorCopy(widget.value);
            const step = (widget.options ?? {}).step || 0.1;
            next[index] = clampComponent(widget, parseFloat(next[index]) + step * Math.sign(eMove.deltaX));
            applyValue(node, widget, next);
        }
    }

    widget.serializeValue = async () => {
        const funct = (widget.options ?? {}).int ? Number : parseFloat;
        return vectorCopy(widget.value).map(v => funct(v));
    };

    Object.defineProperty(widget, "joviVector", { value: true, configurable: true });
    return widget;
}

const VectorWidget = (app, inputName, options, initial) => {
    // Each widget gets its own options: VALUE, LERP and the OP nodes retype their vector
    // widget by writing into its options, which must not reach other nodes of the type.
    const settings = vectorOptions({ ...(options[1] ?? {}) });
    /** @type {IWidget} */
    const widget = {
        name: inputName,
        type: options[0],
        y: 0,
        value: vectorCopy(settings.default, initial),
        options: settings,
    }
    return installVector(widget);
}

/**
 * Install the vector behaviour on the widgets a subgraph node shows for promoted vector inputs.
 *
 * @param {Object} node - A subgraph node.
 */
function adoptPromotedVectors(node) {
    for (const input of node.inputs ?? []) {
        const widget = input._widget;
        if (widget && !widget.joviVector && VECTOR_TYPES.has(widget.type)) {
            installVector(widget);
        }
    }
}

app.registerExtension({
    name: "jovi.widget.spinner",
    async getCustomWidgets(app) {
        return {
            VEC2: (node, inputName, inputData, app) => ({
                widget: node.addCustomWidget(VectorWidget(app, inputName, inputData, [0, 0])),
            }),
            VEC3: (node, inputName, inputData, app) => ({
                widget: node.addCustomWidget(VectorWidget(app, inputName, inputData, [0, 0, 0])),
            }),
            VEC4: (node, inputName, inputData, app) => ({
                widget: node.addCustomWidget(VectorWidget(app, inputName, inputData, [0, 0, 0, 0])),
            })
        }
    },
    nodeCreated(node) {
        // A subgraph node replaces a promoted input's widget with a plain projection that has
        // no drawing or pointer handling; give it the vector's own.
        const events = node.subgraph?.events;
        if (!events?.addEventListener) return;
        adoptPromotedVectors(node);
        const controller = new AbortController();
        events.addEventListener("widget-promoted", () => adoptPromotedVectors(node),
                                { signal: controller.signal });
        const onRemoved = node.onRemoved;
        node.onRemoved = function () {
            controller.abort();
            return onRemoved?.apply(this, arguments);
        };
    },
})
