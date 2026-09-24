import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { mapDirectoryResources } from "../scripts/installer_resource_map.mjs";

test("installer PostgreSQL mapping preserves bin, lib, and nested share paths", async () => {
  const fixture = await mkdtemp(join(tmpdir(), "raventech-installer-resource-map-"));
  const configRoot = join(fixture, "desktop", "src-tauri");
  const source = join(fixture, "desktop", "dist-native", "windows-x86_64", "postgresql");
  try {
    await mkdir(configRoot, { recursive: true });
    await mkdir(join(source, "bin"), { recursive: true });
    await mkdir(join(source, "lib"), { recursive: true });
    await mkdir(join(source, "share", "timezones"), { recursive: true });
    await writeFile(join(source, "manifest.json"), "{}");
    await writeFile(join(source, "bin", "postgres.exe"), "postgres");
    await writeFile(join(source, "lib", "dict_snowball.dll"), "module");
    await writeFile(join(source, "share", "timezones", "UTC"), "timezone");

    const mapping = await mapDirectoryResources({
      resourceRoot: configRoot,
      sourceDirectory: source,
      destinationDirectory: "native-runtime/postgresql",
    });

    assert.equal(
      mapping["../dist-native/windows-x86_64/postgresql/bin/postgres.exe"],
      "native-runtime/postgresql/bin/postgres.exe",
    );
    assert.equal(
      mapping["../dist-native/windows-x86_64/postgresql/lib/dict_snowball.dll"],
      "native-runtime/postgresql/lib/dict_snowball.dll",
    );
    assert.equal(
      mapping["../dist-native/windows-x86_64/postgresql/share/timezones/UTC"],
      "native-runtime/postgresql/share/timezones/UTC",
    );
    assert.equal(
      mapping["../dist-native/windows-x86_64/postgresql/manifest.json"],
      "native-runtime/postgresql/manifest.json",
    );
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("installer resource mapping rejects unsafe targets and empty sources", async () => {
  const fixture = await mkdtemp(join(tmpdir(), "raventech-installer-resource-safe-"));
  const source = join(fixture, "source");
  try {
    await mkdir(source, { recursive: true });
    await writeFile(join(source, "runtime.bin"), "runtime");
    await assert.rejects(
      mapDirectoryResources({
        resourceRoot: fixture,
        sourceDirectory: source,
        destinationDirectory: "../escape",
      }),
      /safe relative path/,
    );
    const empty = join(fixture, "empty");
    await mkdir(empty);
    await assert.rejects(
      mapDirectoryResources({
        resourceRoot: fixture,
        sourceDirectory: empty,
        destinationDirectory: "safe",
      }),
      /source directory is empty/,
    );
    const linked = join(fixture, "linked-source");
    await symlink(source, linked, process.platform === "win32" ? "junction" : "dir");
    await assert.rejects(
      mapDirectoryResources({
        resourceRoot: fixture,
        sourceDirectory: linked,
        destinationDirectory: "safe",
      }),
      /real directory/,
    );
    const linkedChild = join(source, "linked-child");
    await symlink(source, linkedChild, process.platform === "win32" ? "junction" : "dir");
    await assert.rejects(
      mapDirectoryResources({
        resourceRoot: fixture,
        sourceDirectory: source,
        destinationDirectory: "safe",
      }),
      /symbolic links/,
    );
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("installer backend and worker mappings preserve nested PyInstaller files", async () => {
  const fixture = await mkdtemp(join(tmpdir(), "raventech-installer-pyinstaller-map-"));
  const configRoot = join(fixture, "desktop", "src-tauri");
  const backend = join(fixture, "desktop", "dist-native", "windows-x86_64", "backend");
  const worker = join(fixture, "desktop", "dist-native", "windows-x86_64", "worker");
  try {
    await mkdir(configRoot, { recursive: true });
    await mkdir(join(backend, "pydantic_core"), { recursive: true });
    await mkdir(join(worker, "native_handlers"), { recursive: true });
    await writeFile(join(backend, "RavenTechBackend.exe"), "backend");
    await writeFile(join(backend, "pydantic_core", "_pydantic_core.pyd"), "extension");
    await writeFile(join(worker, "RavenTechWorker.exe"), "worker");
    await writeFile(join(worker, "native_handlers", "registry.pyc"), "handler");

    const backendMapping = await mapDirectoryResources({
      resourceRoot: configRoot,
      sourceDirectory: backend,
      destinationDirectory: "native-runtime/backend",
    });
    const workerMapping = await mapDirectoryResources({
      resourceRoot: configRoot,
      sourceDirectory: worker,
      destinationDirectory: "native-runtime/worker",
    });

    assert.equal(
      backendMapping["../dist-native/windows-x86_64/backend/pydantic_core/_pydantic_core.pyd"],
      "native-runtime/backend/pydantic_core/_pydantic_core.pyd",
    );
    assert.equal(
      workerMapping["../dist-native/windows-x86_64/worker/native_handlers/registry.pyc"],
      "native-runtime/worker/native_handlers/registry.pyc",
    );
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});
