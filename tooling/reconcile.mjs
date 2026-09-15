import fs from "node:fs";
import YAML from "yaml";
let raw = fs.readFileSync("openapi.yaml", "utf8");
// Remove the duplicate empty schema key in the supplied NotFound response.
raw = raw.replace(/(\s+schema:)\n\s+schema:/g, "$1");
const doc = YAML.parse(raw);
doc.info.version = "0.2.0";
doc.info.description +=
  "\nVersion 0.2 describes the local development service. Native transport metrics may be null until measured. Workspaces execute trusted local code and are not security sandboxes.";
const schemas = doc.components.schemas;
for (const name of ["WorkspaceStatus", "RuntimeMetrics"]) {
  schemas[name].properties.executor_mode.enum = [
    "normal",
    "soft_rt",
    "hard_rt",
  ];
  schemas[name].properties.executor_mode.description =
    "Actual scheduling mode; normal means SCHED_FIFO is not active.";
}
for (const field of [
  "avg_latency_us",
  "p99_latency_us",
  "total_messages",
  "messages_per_second",
  "missed_deadlines",
  "shm_pool",
]) {
  const p = schemas.RuntimeMetrics.properties[field];
  p.type = [p.type, "null"];
}
for (const field of ["estop_triggered", "heartbeat_latency_us"]) {
  const p = schemas.RuntimeMetrics.properties.safety_monitor.properties[field];
  p.type = [p.type, "null"];
}
for (const field of ["cpu_percent", "memory_mb"]) {
  const p = schemas.NodeInfo.properties[field];
  p.type = [p.type, "null"];
}
schemas.RunRequest.properties.target.description =
  "Python file, built executable, or ros2:package:executable. Native node loading is not implemented and is rejected.";
schemas.RunRequest.properties.restart = {
  type: "string",
  enum: ["never", "on-failure", "always"],
  default: "never",
};
schemas.RunRequest.properties.max_restarts = {
  type: "integer",
  minimum: 0,
  maximum: 100,
  default: 0,
};
schemas.RunRequest.properties.background.description =
  "Reserved for CLI compatibility. The service supervises runs asynchronously in all cases.";
schemas.RuntimeMetrics.properties.measurement_status = { type: "string" };
schemas.RuntimeMetrics.properties.safety_monitor.properties.simulated = {
  type: "boolean",
};
schemas.RuntimeMetrics.properties.safety_monitor.properties.scope = {
  type: "string",
};
doc.paths["/api/v1/workspace"] = {
  get: {
    tags: ["Workspace"],
    summary: "List persisted workspaces",
    operationId: "listWorkspaces",
    responses: {
      200: {
        description: "Workspace list",
        content: {
          "application/json": {
            schema: {
              type: "object",
              required: ["workspaces"],
              properties: {
                workspaces: {
                  type: "array",
                  items: { $ref: "#/components/schemas/Workspace" },
                },
              },
            },
          },
        },
      },
      401: { $ref: "#/components/responses/Unauthorized" },
    },
  },
};
const logs = doc.paths["/api/v1/workspace/{id}/logs"].get;
logs.description =
  "Authenticated WebSocket stream, with GET JSON polling fallback. Send a subscribe message with workspace_id. Browser clients supply token in the first WebSocket message, never in the URL. Same-origin connections only. Authentication must complete within 5 seconds. Supported client messages: subscribe, unsubscribe. restart_node commands are not implemented; use the REST stop/run endpoints.";
logs.responses = {
  101: {
    description:
      "WebSocket connection upgraded; authenticate using the first subscribe message",
  },
  200: {
    description: "Polling log snapshot",
    content: {
      "application/json": {
        schema: {
          type: "object",
          properties: { logs: { type: "array", items: { type: "object" } } },
        },
      },
    },
  },
  401: { $ref: "#/components/responses/Unauthorized" },
};
fs.writeFileSync("openapi.yaml", YAML.stringify(doc));
