import fs from "node:fs";
import YAML from "yaml";
import Parser from "@apidevtools/swagger-parser";
import Ajv from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
const doc = await Parser.dereference(
  YAML.parse(
    fs.readFileSync(new URL("../openapi.yaml", import.meta.url), "utf8"),
  ),
);
const ajv = new Ajv({ strict: false });
addFormats(ajv);
const url = process.env.ROSPLUS_URL || "http://127.0.0.1:8080";
const token = process.env.ROSPLUS_API_TOKEN;
let count = 0;
async function call(method, path, contract, data, status = 200) {
  const r = await fetch(url + path, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const v = await r.json();
  if (r.status !== status)
    throw Error(`${method} ${path}: ${r.status} ${JSON.stringify(v)}`);
  const schema =
    doc.paths[contract][method.toLowerCase()].responses[String(status)]
      ?.content?.["application/json"]?.schema;
  if (schema && !ajv.validate(schema, v))
    throw Error(`${path}: ${JSON.stringify(ajv.errors)}`);
  count++;
  return v;
}
await call("GET", "/health", "/health");
const w = await call(
  "POST",
  "/api/v1/workspace/create",
  "/api/v1/workspace/create",
  { name: "contract_" + Date.now() },
  201,
);
const base = "/api/v1/workspace/" + w.id,
  pattern = "/api/v1/workspace/{id}";
try {
  await call("GET", "/api/v1/workspace", "/api/v1/workspace");
  await call("GET", base, pattern);
  await call("PUT", base + "/file/probe.py", pattern + "/file/{path}", {
    content:
      "import time\nprint('contract probe', flush=True)\ntime.sleep(5)\n",
  });
  await call("GET", base + "/file/probe.py", pattern + "/file/{path}");
  await call("GET", base + "/files", pattern + "/files");
  await call("POST", base + "/build", pattern + "/build", {});
  await call("POST", base + "/run", pattern + "/run", { target: "probe.py" });
  for (const tail of ["status", "metrics", "graph", "logs"])
    await call("GET", base + "/" + tail, pattern + "/" + tail);
  await call("POST", base + "/stop", pattern + "/stop", {});
} finally {
  await call("DELETE", base, pattern);
}
console.log(`${count} live API responses validated against OpenAPI`);
