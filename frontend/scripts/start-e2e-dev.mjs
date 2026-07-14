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
const port = process.env.E2E_PORT || "3001"
const child = spawn(process.execPath, [nextBin, "dev", "-p", port, "--hostname", "localhost"], {
  env: {
    ...process.env,
  },
  stdio: "inherit",
})

let shuttingDown = false

function shutdown(signal) {
  if (shuttingDown) {
    return
  }

  shuttingDown = true

  if (process.platform === "win32" && child.pid) {
    const taskkill = spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
    })
    taskkill.on("close", () => process.exit(0))
    setTimeout(() => process.exit(0), 2_000).unref()
    return
  }

  child.kill(signal)
  setTimeout(() => process.exit(0), 2_000).unref()
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => shutdown(signal))
}

child.on("exit", (code) => {
  process.exit(code ?? 1)
})
