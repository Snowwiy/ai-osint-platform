import { createHash } from "node:crypto";
import { readFile, readdir, realpath, readlink, stat } from "node:fs/promises";
import { isAbsolute, relative as pathRelative, resolve, sep } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const VERSION = "5.0.0-rc6";
export const DESKTOP = resolve(fileURLToPath(new URL("..", import.meta.url)));

export function nativeSourceRoots(desktop = DESKTOP, platform = process.platform) {
  if (platform === "win32") return {
    os: "windows", architecture: "x86_64",
    backend: resolve(desktop, "dist-native", "windows-x86_64", "backend"),
    worker: resolve(desktop, "dist-native", "windows-x86_64", "worker"),
    backendBinary: "RavenTechBackend.exe", workerBinary: "RavenTechWorker.exe",
  };
  if (platform === "linux") return {
    os: "linux", architecture: "x86_64",
    backend: resolve(desktop, "dist-native", "linux-x86_64", "backend"),
    worker: resolve(desktop, "dist-native", "linux-x86_64", "worker"),
    backendBinary: "raventech-backend", workerBinary: "raventech-worker",
  };
  throw new Error("Native runtime packaging supports x86_64 Windows and Linux only.");
}

async function validateTree(root) {
  const prohibited = /(^|\/)(\.env(?:\..*)?|backups?|uploads?|logs?)(\/|$)/i;
  const rootPath = resolve(root);
  const isWithinRoot = (path) => {
    const fromRoot = pathRelative(rootPath, path);
    return fromRoot === "" || (fromRoot !== ".." && !fromRoot.startsWith(`..${sep}`));
  };
  const walk = async (directory, relative = "") => {
    const output = [];
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const childRelative = relative ? `${relative}/${entry.name}` : entry.name;
      if (prohibited.test(childRelative) || /\.(key|pfx|p12|db|sqlite|dump|log)$/i.test(childRelative)) throw new Error(`Forbidden native runtime resource: ${childRelative}`);
      const path = resolve(directory, entry.name);
      if (entry.isSymbolicLink()) {
        const target = await readlink(path);
        if (isAbsolute(target)) throw new Error(`Native runtime symlink must be relative: ${childRelative}`);
        const resolvedTarget = await realpath(path);
        if (!isWithinRoot(resolvedTarget) || !(await stat(resolvedTarget)).isFile()) throw new Error(`Native runtime symlink must resolve to an internal file: ${childRelative}`);
        output.push({ path: childRelative, size: (await stat(path)).size });
      }
      else if (entry.isDirectory()) output.push(...await walk(path, childRelative));
      else if (entry.isFile()) {
        if (/\.pem$/i.test(childRelative)) {
          const prefix = (await readFile(path)).subarray(0, 4096).toString("utf8");
          if (/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/i.test(prefix)) throw new Error(`Private key material is prohibited in native runtime resources: ${childRelative}`);
        }
        output.push({ path: childRelative, size: (await stat(path)).size });
      }
      else throw new Error(`Unsupported native runtime resource: ${childRelative}`);
    }
    return output;
  };
  return walk(root);
}

export async function validateNativeRuntime({ desktop = DESKTOP, platform = process.platform } = {}) {
  const paths = nativeSourceRoots(desktop, platform);
  const components = {};
  for (const [name, directory, binaryName] of [
    ["backend", paths.backend, paths.backendBinary], ["worker", paths.worker, paths.workerBinary],
  ]) {
    const manifest = JSON.parse(await readFile(resolve(directory, "manifest.json"), "utf8"));
    if (manifest.version !== VERSION || manifest.component !== name || manifest.os !== paths.os || manifest.architecture !== paths.architecture || manifest.runtime_profile !== "desktop") {
      throw new Error(`The ${name} artifact manifest does not match this desktop target.`);
    }
    const binary = resolve(directory, binaryName);
    const bytes = await readFile(binary);
    const sha256 = createHash("sha256").update(bytes).digest("hex");
    if (manifest.binary_sha256 !== sha256 || manifest.binary_size_bytes !== bytes.length) {
      throw new Error(`The ${name} binary does not match its build manifest.`);
    }
    const version = spawnSync(binary, ["--version"], { cwd: directory, shell: false, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    if (version.error || version.status !== 0 || version.stdout.trim() !== VERSION) {
      throw new Error(`The ${name} executable did not report the expected release.`);
    }
    const files = await validateTree(directory);
    components[name] = { directory, binary: binaryName, sha256, sizeBytes: bytes.length, fileCount: files.length, totalBytes: files.reduce((sum, file) => sum + file.size, 0) };
  }
  return { ...paths, components, packagingEngine: "PyInstaller", requiredExternalDependencies: ["PostgreSQL", "external configuration"] };
}
