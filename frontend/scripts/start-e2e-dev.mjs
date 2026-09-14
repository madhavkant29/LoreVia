import { spawn } from "node:child_process"
import { readFileSync, rmSync, writeFileSync } from "node:fs"
import path from "node:path"

const port = process.env.E2E_PORT || "3001"
const distDir = process.env.E2E_NEXT_DIST_DIR || `.next-e2e-${port}`
if (!/^\.next-e2e-\d+$/.test(distDir)) {
  throw new Error("Refusing to use an unexpected E2E build directory.")
}

const outputPath = path.resolve(process.cwd(), distDir)
const expectedOutputPath = path.join(process.cwd(), distDir)
const filesToRestore = ["tsconfig.json", "next-env.d.ts"].map((filename) => {
  const filePath = path.resolve(process.cwd(), filename)
  return { filePath, original: readFileSync(filePath, "utf8") }
})

if (outputPath !== expectedOutputPath) {
  throw new Error("Refusing to clean an unexpected E2E build directory.")
}

rmSync(outputPath, { force: true, recursive: true })

function restoreGeneratedConfig() {
  for (const file of filesToRestore) {
    writeFileSync(file.filePath, file.original)
  }
}

const nextBin = path.resolve("node_modules/next/dist/bin/next")
const child = spawn(process.execPath, [nextBin, "dev", "-p", port, "--hostname", "localhost"], {
  env: {
    ...process.env,
    E2E_NEXT_DIST_DIR: distDir,
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
    taskkill.on("close", () => {
      restoreGeneratedConfig()
      process.exit(0)
    })
    setTimeout(() => {
      restoreGeneratedConfig()
      process.exit(0)
    }, 2_000).unref()
    return
  }

  child.kill(signal)
  setTimeout(() => {
    restoreGeneratedConfig()
    process.exit(0)
  }, 2_000).unref()
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => shutdown(signal))
}

child.on("exit", (code) => {
  restoreGeneratedConfig()
  process.exit(code ?? 1)
})
