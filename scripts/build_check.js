// Minimal build check for Cortex-HQ.
// The app itself is a Python/Streamlit app with no static build step, but
// Freebuff's hosting build image is Node.js-only, so this is the build
// command's sanity check: verify the app entry point and project metadata
// are present.
const fs = require("fs");

const required = ["explorer/knowledge_explorer.py", "pyproject.toml"];
for (const file of required) {
  if (!fs.existsSync(file)) {
    console.error(`build check failed: missing ${file}`);
    process.exit(1);
  }
}
console.log("build check ok");
