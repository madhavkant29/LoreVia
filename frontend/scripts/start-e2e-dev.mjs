import { spawn } from "node:child_process"
import { rmSync } from "node:fs"
import path from "node:path"

const distDir = ".next"
const outputPath = path.resolve(process.cwd(), distDir)
const expectedOutputPath = path.join(process.cwd(), distDir)

if (outputPath !== expectedOutputPath) {
  throw new Error("Refusing to clean an unexpected E2E build directory.")
}

rmSync(outputPath, { force: true, recursive: true })

const nextBin = path.resolve("node_modules/next/dist/bin/next")
const child = spawn(process.execPath, [nextBin, "dev", "-p", "3001", "--hostname", "localhost"], {
  env: {
    ...process.env,
  },
  stdio: "inherit",
})

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal))
}

child.on("exit", (code) => {
  process.exit(code ?? 1)
})
