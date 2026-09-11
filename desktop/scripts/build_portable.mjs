import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const frontend = resolve(repository, "frontend");

if (process.platform !== "win32") {
  throw new Error("The portable workflow must run on Windows.");
}

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    env: process.env,
    shell: false,
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}.`);
  }
}

console.log("Validating the isolated desktop source...");
run(process.execPath, [resolve(desktop, "scripts", "validate.mjs")], desktop);
run(process.execPath, [
  "--test",
  resolve(desktop, "tests", "portable-scripts.test.mjs"),
  resolve(desktop, "tests", "runtime.test.mjs"),
], desktop);
run(process.execPath, [resolve(desktop, "scripts", "build.mjs")], desktop);

console.log("Confirming the existing browser frontend still builds...");
run(process.execPath, [resolve(frontend, "node_modules", "typescript", "bin", "tsc"), "--noEmit"], frontend);
run(process.execPath, [resolve(frontend, "node_modules", "vite", "bin", "vite.js"), "build"], frontend);

console.log("Building the portable Tauri executable without installer bundling...");
run("cargo", [
  "build",
  "--manifest-path", resolve(desktop, "src-tauri", "Cargo.toml"),
  "--release",
  "--locked",
  "--offline",
], desktop);

run(process.execPath, [resolve(desktop, "scripts", "package_portable.mjs")], desktop);
run(process.execPath, [resolve(desktop, "scripts", "validate_portable.mjs")], desktop);
console.log("Windows portable desktop build completed. No installer was created.");
