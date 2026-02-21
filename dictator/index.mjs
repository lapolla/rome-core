#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "fs-extra";
import crypto from "crypto";
import { join, resolve } from "path";
import { exec as execCb } from "child_process";
import { promisify } from "util";

const exec = promisify(execCb);

const ROME_ROOT = resolve(process.env.ROME_ROOT || join(process.env.HOME, "projects/rome-core"));
const ARSENAL_PATH = join(ROME_ROOT, "arsenal/core_arsenal.json");

const WorkerOutputSchema = z.object({
  rome_v: z.string(),
  task_id: z.string(),
  result: z.object({
    status: z.enum(["COMPLETED", "FAILED", "RETRY"]),
    exit_code: z.number(),
    artifacts: z.array(z.object({
      path: z.string(),
      hash_sha256: z.string(),
      size_bytes: z.number()
    })),
    telemetry: z.record(z.any()).optional()
  }),
  errors: z.array(z.object({
    code: z.string(),
    message: z.string(),
    line: z.number().optional()
  })).optional()
});

async function calculateHash(path) {
  try {
    const buffer = await fs.readFile(path);
    return crypto.createHash("sha256").update(buffer).digest("hex");
  } catch (err) { return null; }
}

async function loadArsenal() {
  if (!(await fs.pathExists(ARSENAL_PATH))) return { capabilities: {} };
  return fs.readJson(ARSENAL_PATH);
}

const server = new McpServer({
  name: "ROME Dictator",
  version: "1.0.0"
});

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

    if (!cap) {
      return { content: [{ type: "text", text: `ERROR: Capability "${capability}" not found.` }], isError: true };
    }

    const taskDir = join(ROME_ROOT, "legions", task_id);
    await fs.ensureDir(taskDir);

    // Map input files
    for (const f of input_files) {
      const src = resolve(ROME_ROOT, f);
      const dest = join(taskDir, f);
      if (await fs.pathExists(src)) {
        await fs.ensureDir(join(taskDir, f, ".."));
        await fs.copy(src, dest);
      }
    }

    // Command construction: Inject task_id as the first argument to the wrapper
    const command = `${cap.exec} ${task_id} ${cap.args ? cap.args.join(" ") : ""} ${args.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(" ")}`;
    
    console.error(`[Dictator] Task ${task_id}: Executing ${capability}...`);

    try {
      const { stdout } = await exec(command, { 
        cwd: taskDir,
        env: { ...process.env, ROME_TASK_DIR: taskDir }
      });
      
      // Parse the Legion's ROME Protocol JSON from stdout
      const lastLine = stdout.trim().split('\n').pop();
      let protocolResult;
      try {
        protocolResult = JSON.parse(stdout); // Wrapper outputs full JSON
      } catch (e) {
        // Try to find JSON block in case of pollution
        const match = stdout.match(/\{[\s\S]*\}/);
        if (match) protocolResult = JSON.parse(match[0]);
        else throw new Error("No JSON payload found in Legion output");
      }

      const validResult = WorkerOutputSchema.parse(protocolResult);
      
      return {
        content: [{ type: "text", text: JSON.stringify(validResult, null, 2) }]
      };
    } catch (err) {
      return { content: [{ type: "text", text: `Legion Execution Failed: ${err.message}` }], isError: true };
    }
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ROME Dictator initialized. Protocol v1.0 active.");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
