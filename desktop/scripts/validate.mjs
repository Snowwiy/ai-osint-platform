import { access, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const required = [
  "package.json",
  "ui/index.html",
  "ui/app.css",
  "ui/app.js",
  "src-tauri/Cargo.toml",
  "src-tauri/tauri.conf.json",
  "src-tauri/capabilities/default.json",
  "src-tauri/src/main.rs",
];
for (const path of required) await access(resolve(desktop, path));

const config = JSON.parse(await readFile(resolve(desktop, "src-tauri/tauri.conf.json"), "utf8"));
const capability = JSON.parse(await readFile(resolve(desktop, "src-tauri/capabilities/default.json"), "utf8"));
const cargo = await readFile(resolve(desktop, "src-tauri/Cargo.toml"), "utf8");
const rust = await readFile(resolve(desktop, "src-tauri/src/main.rs"), "utf8");
const html = await readFile(resolve(desktop, "ui/index.html"), "utf8");

if (config.version !== "5.0.0-rc4") throw new Error("Desktop version must match RC4.");
if (config.build.frontendDist !== "../ui") throw new Error("Desktop UI must remain isolated.");
if (capability.permissions.length !== 0) throw new Error("Prototype capability must grant no plugin permissions.");
if (/tauri-plugin-(shell|fs)|shell:|fs:/i.test(`${cargo}\n${JSON.stringify(capability)}`)) {
  throw new Error("Shell or filesystem capability detected.");
}
if (!rust.includes("127.0.0.1") || rust.includes("std::process::Command")) {
  throw new Error("Health bridge must be loopback-only and must not execute commands.");
}
if (!html.includes('lang="en"') || !html.includes("Español")) {
  throw new Error("Desktop help screen must retain English/Spanish controls.");
}

for (const doc of [
  "DESKTOP_TAURI_PROTOTYPE.md",
  "DESKTOP_APP_STRATEGY.md",
  "DESKTOP_PACKAGING_TODO.md",
  "README.md",
  "KNOWN_LIMITATIONS.md",
  "FINAL_QA_CHECKLIST.md",
]) await access(resolve(repository, doc));

console.log("Desktop prototype safety checks passed.");
