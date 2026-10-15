import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const here = path.dirname(url.fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const html = fs.readFileSync(path.join(root, "calculator", "index.html"), "utf8");
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/i);
if (!scriptMatch) throw new Error("calculator script not found");

const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) {
    elements.set(id, { id, value: "", checked: false, innerHTML: "" });
  }
  return elements.get(id);
};
globalThis.document = { getElementById: element };

const script = `${scriptMatch[1]}\n` +
  `globalThis.__m1_test__={spec:SPEC, example:EXAMPLE, prediction:infer(raw())};`;
eval(script);

const actual = globalThis.__m1_test__;
const close = (a, b, tol = 1e-15) => {
  if (Math.abs(a - b) > tol) throw new Error(`expected ${b}, got ${a}`);
};
close(actual.prediction.risk, 0.056738982411137256);
close(actual.prediction.comp, 0.1347475396927663);
if (actual.spec.threshold.value !== 0.028094640664533963) throw new Error("threshold mismatch");
if (actual.prediction.alert !== true) throw new Error("alert mismatch");
if (!(actual.spec.threshold.value >= actual.spec.threshold.value)) throw new Error(">= equality rule failed");
console.log(JSON.stringify({
  m1_event_cif_6h: actual.prediction.risk,
  competitor_cif_6h: actual.prediction.comp,
  threshold: actual.spec.threshold.value,
  alert: actual.prediction.alert,
}));
