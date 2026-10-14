import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontendDirectory = fileURLToPath(new URL("../frontend/", import.meta.url));
const eslintCli = fileURLToPath(new URL("../frontend/node_modules/eslint/bin/eslint.js", import.meta.url));

if (!existsSync(eslintCli)) {
  console.error("Dependências do frontend ausentes. Execute npm ci na pasta frontend.");
  process.exit(1);
}

// Invoke Node directly so Git hooks also work on Windows without npm.cmd or a shell.
const result = spawnSync(process.execPath, [eslintCli, ".", "--max-warnings", "0", ...process.argv.slice(2)], {
  cwd: frontendDirectory,
  stdio: "inherit",
});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
