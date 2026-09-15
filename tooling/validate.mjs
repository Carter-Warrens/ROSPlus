import fs from "node:fs";
import YAML from "yaml";
import SwaggerParser from "@apidevtools/swagger-parser";
const file = new URL("../openapi.yaml", import.meta.url);
const doc = YAML.parse(fs.readFileSync(file, "utf8"), { uniqueKeys: true });
await SwaggerParser.validate(doc);
console.log(
  `OpenAPI ${doc.openapi}: valid, ${Object.keys(doc.paths).length} paths`,
);
