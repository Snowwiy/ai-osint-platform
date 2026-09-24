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

async function validateTree(root, { postgresqlRuntime = false } = {}) {
  const prohibited = /(^|\/)(\.env(?:\..*)?|backups?|uploads?|logs?)(\/|$)/i;
  const postgresDataFiles = new Set([
    "pg_version", "pg_control", "postmaster.pid", "postmaster.opts",
    "postgresql.conf", "postgresql.auto.conf", "pg_hba.conf", "pg_ident.conf",
    "pgpass", ".pgpass", "pgpass.conf", "database.secret", "ownership.json",
  ]);
  const postgresDataDirectories = new Set([
    "base", "global", "pg_commit_ts", "pg_dynshmem", "pg_logical",
    "pg_multixact", "pg_notify", "pg_replslot", "pg_serial", "pg_snapshots",
    "pg_stat", "pg_stat_tmp", "pg_subtrans", "pg_tblspc", "pg_twophase",
    "pg_wal", "pg_xact",
  ]);
  const rootPath = resolve(root);
  const isWithinRoot = (path) => {
    const fromRoot = pathRelative(rootPath, path);
    return fromRoot === "" || (fromRoot !== ".." && !fromRoot.startsWith(`..${sep}`));
  };
  const walk = async (directory, relative = "") => {
    const output = [];
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const childRelative = relative ? `${relative}/${entry.name}` : entry.name;
      const loweredName = entry.name.toLowerCase();
      if (postgresqlRuntime && (
        postgresDataFiles.has(loweredName)
        || postgresDataDirectories.has(loweredName)
      )) throw new Error(`PostgreSQL data, credentials, or cluster configuration is prohibited: ${childRelative}`);
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

export async function validatePostgresqlRuntimeTree(root) {
  const files = await validateTree(root, { postgresqlRuntime: true });
  const manifestPath = resolve(root, "manifest.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const directories = manifest.os === "linux"
    ? { bin: "lib/postgresql/16/bin", share: "share/postgresql/16", library: "lib/postgresql/16/lib" }
    : { bin: "bin", share: "share", library: "lib" };
  const moduleSuffix = manifest.os === "windows" ? ".dll" : ".so";
  if (!["windows", "linux"].includes(manifest.os)
    || manifest.bin_directory !== undefined && manifest.bin_directory !== directories.bin
    || manifest.share_directory !== undefined && manifest.share_directory !== directories.share
    || manifest.library_directory !== undefined && manifest.library_directory !== directories.library
    || manifest.os === "linux" && (!manifest.bin_directory || !manifest.share_directory || !manifest.library_directory)) {
    throw new Error("PostgreSQL runtime directory metadata is invalid.");
  }
  const filePaths = new Set(files.map(({ path }) => path));
  const required = [];
  for (const extension of ["pgcrypto", "pg_trgm"]) {
    const control = `${directories.share}/extension/${extension}.control`;
    const module = `${directories.library}/${extension}${moduleSuffix}`;
    const sqlFiles = files
      .map(({ path }) => path)
      .filter((path) => path.startsWith(`${directories.share}/extension/${extension}--`) && path.endsWith(".sql"));
    if (!filePaths.has(control) || !filePaths.has(module) || sqlFiles.length === 0) {
      throw new Error(`Required PostgreSQL extension resources are missing: ${extension}.`);
    }
    required.push(control, module, ...sqlFiles);
  }
  for (const path of required) {
    const bytes = await readFile(resolve(root, path));
    const record = manifest.files?.[path];
    if (!record || record.size_bytes !== bytes.length || record.sha256 !== createHash("sha256").update(bytes).digest("hex")) {
      throw new Error(`PostgreSQL extension checksum is missing or invalid: ${path}`);
    }
  }
  return files;
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
  const postgresDirectory = resolve(desktop, "dist-native", `${paths.os}-x86_64`, "postgresql");
  const postgresManifest = JSON.parse(await readFile(resolve(postgresDirectory, "manifest.json"), "utf8"));
  if (postgresManifest.component !== "postgresql" || postgresManifest.major_version !== 16 || postgresManifest.os !== paths.os || postgresManifest.architecture !== "x86_64" || postgresManifest.compatible_raventech_version !== VERSION) {
    throw new Error("The managed PostgreSQL manifest does not match this desktop target.");
  }
  const postgresBinDirectory = postgresManifest.bin_directory ?? "bin";
  const postgresShareDirectory = postgresManifest.share_directory ?? "share";
  const postgresLibraryDirectory = postgresManifest.library_directory ?? "lib";
  const postgresFiles = {};
  for (const name of [paths.os === "windows" ? "postgres.exe" : "postgres", paths.os === "windows" ? "initdb.exe" : "initdb", paths.os === "windows" ? "psql.exe" : "psql", paths.os === "windows" ? "pg_isready.exe" : "pg_isready", paths.os === "windows" ? "pg_ctl.exe" : "pg_ctl"]) {
    const path = resolve(postgresDirectory, postgresBinDirectory, name);
    const bytes = await readFile(path);
    const sha256 = createHash("sha256").update(bytes).digest("hex");
    const relativePath = `${postgresBinDirectory}/${name}`;
    if (postgresManifest.files?.[relativePath]?.sha256 !== sha256 || postgresManifest.files?.[relativePath]?.size_bytes !== bytes.length) throw new Error(`PostgreSQL runtime checksum mismatch: ${name}`);
    postgresFiles[name] = { sha256, sizeBytes: bytes.length };
  }
  const postgresVersion = spawnSync(resolve(postgresDirectory, postgresBinDirectory, paths.os === "windows" ? "postgres.exe" : "postgres"), ["--version"], { cwd: postgresDirectory, shell: false, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  if (postgresVersion.error || postgresVersion.status !== 0 || !postgresVersion.stdout.includes("PostgreSQL) 16.")) throw new Error("The bundled PostgreSQL executable failed its version check.");
  const sharePath = resolve(postgresDirectory, postgresShareDirectory);
  if (!(await stat(sharePath)).isDirectory() || (await readdir(sharePath)).length === 0) throw new Error("The bundled PostgreSQL share resources are missing.");
  const moduleName = paths.os === "windows" ? "dict_snowball.dll" : "dict_snowball.so";
  const modulePath = resolve(postgresDirectory, postgresLibraryDirectory, moduleName);
  const moduleBytes = await readFile(modulePath);
  const moduleManifest = postgresManifest.files?.[`${postgresLibraryDirectory}/${moduleName}`];
  if (!moduleManifest || moduleManifest.sha256 !== createHash("sha256").update(moduleBytes).digest("hex") || moduleManifest.size_bytes !== moduleBytes.length) throw new Error("The PostgreSQL runtime shared-module resource is missing or invalid.");
  const postgresTree = await validatePostgresqlRuntimeTree(postgresDirectory);
  for (const file of postgresTree) {
    if (file.path === "manifest.json") continue;
    const bytes = await readFile(resolve(postgresDirectory, file.path));
    const expected = postgresManifest.files?.[file.path];
    if (!expected || expected.sha256 !== createHash("sha256").update(bytes).digest("hex") || expected.size_bytes !== bytes.length) throw new Error(`PostgreSQL runtime resource checksum mismatch: ${file.path}`);
  }
  const postgresTotalBytes = postgresTree.reduce((sum, file) => sum + file.size, 0);
  return { ...paths, components, postgresql: { directory: postgresDirectory, version: postgresVersion.stdout.trim(), manifest: postgresManifest, files: postgresFiles, totalBytes: postgresTotalBytes }, packagingEngine: "PyInstaller", requiredExternalDependencies: paths.os === "linux" ? ["Linux shared libraries listed in the PostgreSQL runtime manifest"] : [] };
}
