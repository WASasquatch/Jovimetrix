/**
 * Jovimetrix frontend entry. The per-node extensions live in nodes/ and the vector widget in
 * widget_vector.js; this file only names the pack to the frontend.
 */

import { app } from "../../scripts/app.js"

app.registerExtension({
    name: "jovimetrix",
});
