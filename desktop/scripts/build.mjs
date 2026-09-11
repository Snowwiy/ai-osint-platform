import { spawnSync } from "node:child_process";
import { access, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(root, "..");
const frontend = resolve(repository, "frontend");
const source = resolve(root, "ui");
const output = resolve(root, "dist");
const embedded = resolve(output, "app");
const assets = ["index.html", "app.css", "app.js"];

function run(command, args, cwd, env = process.env) {
  const result = spawnSync(command, args, { cwd, env, shell: false, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}.`);
}

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
for (const asset of assets) {
  await access(resolve(source, asset));
  await writeFile(resolve(output, asset), await readFile(resolve(source, asset)));
}
run(process.execPath, [resolve(frontend, "node_modules", "typescript", "bin", "tsc"), "--noEmit"], frontend);
run(
  process.execPath,
  [resolve(frontend, "node_modules", "vite", "bin", "vite.js"), "build", "--mode", "desktop", "--base", "./", "--outDir", embedded, "--emptyOutDir"],
  frontend,
  {
    ...Object.fromEntries(
      Object.entries(process.env).filter(([name]) => !name.toUpperCase().startsWith("VITE_")),
    ),
    VITE_API_BASE_URL: "http://localhost:8000/api/v1",
    VITE_ROUTER_BASENAME: "/app",
  },
);
await access(resolve(embedded, "index.html"));
console.log(`Desktop shell and embedded React frontend copied to ${output}`);
