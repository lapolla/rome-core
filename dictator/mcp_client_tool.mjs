#!/usr/bin/env node

import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { McpClient } from "@modelcontextprotocol/sdk/client/mcp.js";
import { z } from "zod";

async function main() {
  const argsSchema = z.object({
    tool_name: z.string(),
    tool_args: z.string().optional().default("{}").transform((str) => JSON.parse(str)),
  });

  const parsedArgs = argsSchema.parse({
    tool_name: process.argv[2],
    tool_args: process.argv[3],
  });

  const transport = new StdioClientTransport();
  const client = new McpClient(transport);
  await client.connect();

  const result = await client.toolCall(parsedArgs.tool_name, parsedArgs.tool_args);

  // MCP server responds with an array of content objects.
  // We need to extract the text content and print it for legion_wrapper to capture.
  if (result.content && result.content.length > 0) {
    for (const item of result.content) {
      if (item.type === "text") {
        console.log(item.text);
      }
      // Handle other types if necessary, though for now, we expect JSON text
    }
  } else if (result.error) {
    console.error(`MCP Client Error: ${result.error.message}`);
  }

  client.disconnect();
}

main().catch((error) => {
  console.error("MCP Client Wrapper crashed:", error);
  process.exit(1);
});
