import { access, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, "ui");
const output = resolve(root, "dist");
const assets = ["index.html", "app.css", "app.js"];

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
for (const asset of assets) {
  await access(resolve(source, asset));
  await writeFile(resolve(output, asset), await readFile(resolve(source, asset)));
}
console.log(`Desktop UI validated and copied to ${output}`);
