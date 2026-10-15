import { execFileSync } from "node:child_process"

function findListeningPids(port) {
  // Next binds localhost on IPv6 on Windows; `-p tcp` omits that listener.
  const output = execFileSync("netstat", ["-ano"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  })

  const pids = new Set()
  for (const line of output.split(/\r?\n/)) {
    if (!line.includes("LISTENING")) {
      continue
    }

    const columns = line.trim().split(/\s+/)
    const localAddress = columns[1] ?? ""
    const pid = columns[columns.length - 1]
    if (localAddress.endsWith(`:${port}`) && /^\d+$/.test(pid)) {
      pids.add(pid)
    }
  }

  return [...pids]
}

class WindowsExitReporter {
  failed = false
  finished = 0
  total = 0

  onBegin(_, suite) {
    this.total = suite.allTests().length
  }

  onTestEnd(_, result) {
    this.finished += 1
    if (result.status !== "passed" && result.status !== "skipped") {
      this.failed = true
    }

    if (this.finished < this.total) {
      return
    }

    const exitCode = this.failed ? 1 : 0
    const port = process.env.E2E_PORT ?? "3001"

    if (process.platform !== "win32") {
      process.exitCode = exitCode
      return
    }

    setTimeout(() => {
      try {
        for (const pid of findListeningPids(port)) {
          // Stop the owned listener directly; taskkill /T requires process-tree
          // enumeration that restricted Windows sessions may not permit.
          process.kill(Number(pid))
        }
      } catch {
        process.exitCode = exitCode
      }

      process.exit(exitCode)
    }, 5_000).unref()
  }
}

export default WindowsExitReporter
