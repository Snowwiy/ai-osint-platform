import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { copyFile, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(desktop, "..");
const source = resolve(repository, "scripts", "local", "apply_lan_monitoring_config.ps1");
const powershell = join(process.env.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe");

test("fixed LAN profile preserves secrets and creates a timestamped backup", async () => {
  const root = await mkdtemp(join(tmpdir(), "raventech-lan-config-"));
  try {
    await mkdir(resolve(root, "frontend"), { recursive: true });
    await mkdir(resolve(root, "desktop"), { recursive: true });
    await mkdir(resolve(root, "backend", "app"), { recursive: true });
    await mkdir(resolve(root, "scripts", "local"), { recursive: true });
    for (const file of ["docker-compose.yml", "pyproject.toml", "frontend/package.json", "desktop/package.json"]) {
      await writeFile(resolve(root, file), "{}\n", "utf8");
    }
    const script = resolve(root, "scripts", "local", "apply_lan_monitoring_config.ps1");
    await copyFile(source, script);
    const original = [
      "APP_SECRET_KEY=private-test-value",
      "UNKNOWN_OPERATOR_SETTING=preserve-me",
      "LAN_MONITORING_ENABLED=false",
      "LAN_ALLOWED_CIDRS=192.168.50.1/24",
      "LAN_SERVICE_CHECK_ENABLED=false",
    ].join("\n");
    await writeFile(resolve(root, ".env"), `${original}\n`, "utf8");

    const output = execFileSync(powershell, ["-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script], {
      cwd: root,
      encoding: "utf8",
      env: { ...process.env, RAVENTECH_VALIDATED_PROJECT_ROOT: root },
    });
    const updated = await readFile(resolve(root, ".env"), "utf8");
    const backups = (await readdir(root)).filter((name) => /^\.env\.backup-\d{8}-\d{9}$/.test(name));

    assert.equal(backups.length, 1);
    assert.equal(await readFile(resolve(root, backups[0]), "utf8"), `${original}\n`);
    assert.match(updated, /^APP_SECRET_KEY=private-test-value$/m);
    assert.match(updated, /^UNKNOWN_OPERATOR_SETTING=preserve-me$/m);
    assert.match(updated, /^LAN_MONITORING_ENABLED=true$/m);
    assert.match(updated, /^LAN_ALLOWED_CIDRS=192\.168\.50\.0\/24$/m);
    assert.match(updated, /^LAN_GATEWAY_HINT=192\.168\.50\.1$/m);
    assert.match(updated, /^LAN_AUTO_DISCOVERY_ON_START=false$/m);
    assert.match(updated, /^LAN_AUTO_SERVICE_CHECK_ON_START=false$/m);
    assert.match(output, /Restart required: yes/);
    assert.doesNotMatch(output, /private-test-value|preserve-me/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("fixed LAN script rejects public CIDRs and exposes no dynamic configuration input", async () => {
  const script = await readFile(source, "utf8");
  assert.match(script, /Public CIDRs are not permitted/);
  assert.match(script, /ConvertTo-AuthorizedPrivateCidr "192\.168\.50\.1\/24"/);
  assert.match(script, /LAN_ALLOWED_CIDRS = \$normalizedCidr/);
  assert.match(script, /param\(\)/);
  assert.doesNotMatch(script, /Read-Host|Invoke-Expression|iex\b|ScriptBlock::Create/i);
  assert.doesNotMatch(script, /DB_RESET|DATABASE_URL|APP_SECRET_KEY|SUPABASE/i);
});
