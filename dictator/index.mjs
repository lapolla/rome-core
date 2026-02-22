#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "fs-extra";
import crypto from "crypto";
import { join, resolve } from "path";
import { exec as execCb, spawn } from "child_process";
import { promisify } from "util";
import { readFile, writeFile, mkdir, stat, readdir } from "fs/promises";

const exec = promisify(execCb);

// ROME Environment Paths
const ROME_ROOT = resolve(process.env.ROME_ROOT || "/home/paul-kane/projects/rome-core");
const ARSENAL_PATH = join(ROME_ROOT, "arsenal/core_arsenal.json");
const SKYRIM_STATE_FILE = "/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json";
const ROOT_DIR = resolve("/var/www/ftk_lms");
const GIT_ROOT = resolve("/home/paul-kane/projects/Drupal11");

const server = new McpServer({
  name: "asshole",
  version: "2.0.0"
});

// --- Helper Functions ---

function textResult(obj) {
  return { content: [{ type: "text", text: JSON.stringify(obj, null, 2) }] };
}

async function loadArsenal() {
  if (!(await fs.pathExists(ARSENAL_PATH))) return { capabilities: {} };
  return fs.readJson(ARSENAL_PATH);
}

async function focusSkyrim() {
  try {
    const { stdout } = await exec('xdotool search --name "Skyrim Special Edition"');
    const ids = stdout.trim().split("\n").filter(Boolean);
    for (const id of ids) {
      const { stdout: name } = await exec(`xdotool getwindowname ${id}`);
      if (!name.includes("Mod Organizer")) {
        await exec(`xdotool windowactivate --sync ${id} windowfocus --sync ${id}`);
        return id;
      }
    }
  } catch {}
  return null;
}

// --- ROME Core Tools ---

server.tool(
  "execute_legion",
  {
    task_id: z.string().describe("Unique identifier for the task"),
    capability: z.string().describe("The required capability from the Arsenal"),
    args: z.array(z.string()).describe("Arguments for the worker"),
    input_files: z.array(z.string()).optional().default([]).describe("List of files the worker can access")
  },
  async ({ task_id, capability, args, input_files }) => {
    const arsenal = await loadArsenal();
    const cap = arsenal.capabilities[capability];
    if (!cap) return { content: [{ type: "text", text: `ERROR: Capability "${capability}" not found.` }], isError: true };

    const taskDir = join(ROME_ROOT, "legions", task_id);
    await fs.ensureDir(taskDir);

    for (const f of input_files) {
      const src = resolve(ROME_ROOT, f);
      const dest = join(taskDir, f);
      if (await fs.pathExists(src)) {
        await fs.ensureDir(join(taskDir, f, ".."));
        await fs.copy(src, dest);
      }
    }

    const command = `${cap.exec} ${task_id} ${Date.now() / 1000} ${cap.args ? cap.args.join(" ") : ""} ${args.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(" ")}`;
    
    try {
      const { stdout } = await exec(command, { cwd: taskDir, env: { ...process.env, ROME_TASK_DIR: taskDir } });
      return { content: [{ type: "text", text: stdout }] };
    } catch (err) {
      return { content: [{ type: "text", text: `Legion Execution Failed: ${err.message}` }], isError: true };
    }
  }
);

// --- Inherited Asshole Tools ---

server.tool(
  "list_directory",
  {
    dir_path: z.string(),
    recursive: z.boolean().optional().default(false),
  },
  async ({ dir_path, recursive }) => {
    try {
      const absPath = resolve(dir_path);
      let entries = [];
      const walk = async (currentDir) => {
        const dirents = await readdir(currentDir, { withFileTypes: true });
        for (const dirent of dirents) {
          const fullPath = join(currentDir, dirent.name);
          entries.push({ name: dirent.name, path: fullPath, type: dirent.isDirectory() ? "directory" : "file" });
          if (recursive && dirent.isDirectory()) await walk(fullPath);
        }
      };
      if (recursive) await walk(absPath);
      else {
        const dirents = await readdir(absPath, { withFileTypes: true });
        entries = dirents.map(d => ({ name: d.name, path: join(absPath, d.name), type: d.isDirectory() ? "directory" : "file" }));
      }
      return textResult({ ok: true, dir_path, entries });
    } catch (err) { return textResult({ ok: false, message: err.message }); }
  }
);

server.tool(
  "shell_exec",
  { command: z.string() },
  async ({ command }) => {
    try {
      const { stdout, stderr } = await exec(command, { cwd: ROOT_DIR, maxBuffer: 10 * 1024 * 1024 });
      return textResult({ ok: true, stdout, stderr });
    } catch (err) { return textResult({ ok: false, message: err.message, stdout: err.stdout, stderr: err.stderr }); }
  }
);

server.tool(
  "read_anywhere",
  { path: z.string() },
  async ({ path }) => {
    try {
      const data = await readFile(resolve(path), "utf8");
      return { content: [{ type: "text", text: data }] };
    } catch (err) { return { content: [{ type: "text", text: err.message }], isError: true }; }
  }
);

server.tool(
  "write_anywhere",
  { path: z.string(), content: z.string() },
  async ({ path, content }) => {
    try {
      await writeFile(resolve(path), content, "utf8");
      return textResult({ ok: true, message: `Wrote ${content.length} bytes to ${path}` });
    } catch (err) { return textResult({ ok: false, message: err.message }); }
  }
);

server.tool(
  "music_play",
  {
    query: z.string(),
    fade_ms: z.number().default(500)
  },
  async ({ query, fade_ms }) => {
    try {
      const isUrl = query.startsWith("http");
      const ytdlQuery = isUrl ? query : `ytsearch:${query}`;
      const { stdout } = await exec(`yt-dlp --no-download --print webpage_url ${JSON.stringify(ytdlQuery)}`);
      const url = stdout.trim();
      const child = spawn("mpv", [url, "--no-video", `--volume=100`], { detached: true, stdio: "ignore" });
      child.unref();
      return textResult({ ok: true, url, pid: child.pid });
    } catch (err) { return textResult({ ok: false, message: err.message }); }
  }
);

// --- Skyrim Tools (Simplified for Suture) ---

server.tool(
  "skyrim_read_state",
  { path: z.string().optional() },
  async ({ path: jsonPath }) => {
    try {
      const raw = await readFile(SKYRIM_STATE_FILE, "utf8");
      const state = JSON.parse(raw);
      if (jsonPath) {
        const keys = jsonPath.split(".");
        let value = state;
        for (const key of keys) { value = value[key]; }
        return textResult({ ok: true, path: jsonPath, value });
      }
      return textResult({ ok: true, ...state });
    } catch (err) { return textResult({ ok: false, message: err.message }); }
  }
);

server.tool(
  "skyrim_console",
  { commands: z.array(z.string()) },
  async ({ commands }) => {
    try {
      await focusSkyrim();
      await exec(`xdotool key grave`);
      for (const cmd of commands) {
        await exec(`xdotool type --delay 12 -- ${JSON.stringify(cmd)}`);
        await exec(`xdotool key Return`);
      }
      await exec(`xdotool key grave`);
      return textResult({ ok: true, commands });
    } catch (err) { return textResult({ ok: false, message: err.message }); }
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("MCP server crashed:", err);
  process.exit(1);
});
