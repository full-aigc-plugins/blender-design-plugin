#!/usr/bin/env node
/** Launch the Python MCP bootstrap with a portable interpreter lookup.
 *
 * Codex, ZCode, and Kimi all run plugin MCP commands through Node-capable
 * hosts, while the name of a system Python executable differs by platform.
 * This launcher keeps that platform decision out of the plugin manifests and
 * forwards stdio byte-for-byte to the official-SDK Python runtime.
 */

import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const bootstrap = path.join(pluginRoot, "scripts", "mcp_bootstrap.py");
const requested = process.env.PARTME_BLENDER_MCP_PYTHON;

const candidates = [
  ...(requested ? [{ command: requested, args: [] }] : []),
  { command: "python3.13", args: [] },
  { command: "python3.12", args: [] },
  { command: "python3.11", args: [] },
  { command: "python3", args: [] },
  { command: "python", args: [] },
  { command: "py", args: ["-3.13"] },
  { command: "py", args: ["-3.12"] },
  { command: "py", args: ["-3.11"] },
];

function supportsRuntime(candidate) {
  const probe = spawnSync(
    candidate.command,
    [...candidate.args, "-c", "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"], windowsHide: true },
  );
  if (probe.error || probe.status !== 0) return false;
  const match = /^(\d+)\.(\d+)$/.exec(probe.stdout.trim());
  if (!match) return false;
  const version = [Number(match[1]), Number(match[2])];
  return version[0] === 3 && version[1] >= 11 && version[1] < 14;
}

const python = candidates.find(supportsRuntime);
if (!python) {
  process.stderr.write(
    "PartMe Blender MCP requires Python 3.11, 3.12, or 3.13. " +
    "Set PARTME_BLENDER_MCP_PYTHON to a compatible interpreter.\n",
  );
  process.exit(1);
}

const child = spawn(
  python.command,
  [...python.args, bootstrap, ...process.argv.slice(2)],
  { cwd: pluginRoot, env: process.env, stdio: "inherit", windowsHide: true },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (!child.killed) child.kill(signal);
  });
}

child.on("error", (error) => {
  process.stderr.write(`PartMe Blender MCP launcher failed: ${error.message}\n`);
  process.exitCode = 1;
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.stderr.write(`PartMe Blender MCP stopped by ${signal}.\n`);
    process.exitCode = 1;
    return;
  }
  process.exitCode = code ?? 1;
});
