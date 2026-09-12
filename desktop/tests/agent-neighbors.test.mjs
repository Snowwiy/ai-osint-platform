import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const agent = await readFile(
  resolve(desktop, "../scripts/local/local_monitor_agent.ps1"),
  "utf8",
);

test("ServerHost collects only bounded read-only private neighbor observations", () => {
  assert.match(agent, /Get-NetNeighbor -AddressFamily IPv4/);
  assert.match(agent, /Get-SafeHostNeighborObservations/);
  assert.match(agent, /Test-PrivateHost \$_\.IPAddress/);
  assert.match(agent, /Select-Object -First 256/);
  assert.match(agent, /source = "host_neighbor_table"/);
  assert.match(agent, /if \(\$Mode -eq "ServerHost"\)/);
  assert.doesNotMatch(agent, /Set-Net|Remove-Net|New-NetRoute|route\.exe|arp\.exe|Invoke-Expression|ScriptBlock::Create/i);
});

test("agent output is sanitized and both modes self-register without persistence", () => {
  assert.match(agent, /LAN asset registered:/);
  assert.match(agent, /neighbor observations sent:/);
  assert.match(agent, /Endpoint asset registered/);
  assert.match(agent, /asset_type = "lan_endpoint"/);
  assert.match(agent, /Paste a current local admin access token/);
  assert.doesNotMatch(agent, /Write-Host[^\r\n]*(secretValue|X-LAN-Agent-Token|Authorization)/i);
  assert.doesNotMatch(agent, /New-Service|Set-Service|schtasks|Startup\\|RunOnce|Register-ScheduledTask/i);
});
