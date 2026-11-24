import { mkdir, copyFile } from "node:fs/promises";

const destino = new URL("../src/painel_indicadores/estaticos/", import.meta.url);
await mkdir(new URL("vendor/", destino), { recursive: true });
await copyFile(new URL("../frontend/painel.js", import.meta.url), new URL("painel.js", destino));
await copyFile(new URL("../node_modules/plotly.js-dist-min/plotly.min.js", import.meta.url), new URL("vendor/plotly.min.js", destino));
await copyFile(new URL("../node_modules/plotly.js-dist-min/LICENSE", import.meta.url), new URL("vendor/plotly.LICENSE", destino));
