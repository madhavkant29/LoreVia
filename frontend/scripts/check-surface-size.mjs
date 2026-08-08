import fs from "node:fs"
import path from "node:path"
import process from "node:process"

const root = process.cwd()
const sourceRoot = path.join(root, "src")
const allowlistPath = path.join(root, "scripts", "surface-size-allowlist.json")
const allowlist = JSON.parse(fs.readFileSync(allowlistPath, "utf8"))

const rules = [
  {
    name: "page orchestrator",
    target: 500,
    matches: (relativePath) => relativePath.startsWith("src/app/") && relativePath.endsWith("/page.tsx"),
  },
  {
    name: "complex shared workspace",
    target: 800,
    matches: (relativePath) => relativePath.startsWith("src/") && /workspace|RelationshipGraph/i.test(path.basename(relativePath)) && relativePath.endsWith(".tsx"),
  },
]

function normalizePath(filePath) {
  return filePath.split(path.sep).join("/")
}

function listFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  return entries.flatMap((entry) => {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      return listFiles(fullPath)
    }
    return [fullPath]
  })
}

function countLines(filePath) {
  const content = fs.readFileSync(filePath, "utf8")
  if (content.length === 0) return 0
  return content.replace(/\r\n|\r|\n$/, "").split(/\r\n|\r|\n/).length
}

const violations = []
const staleAllowlist = []
const checkedAllowlistKeys = new Set()

for (const filePath of listFiles(sourceRoot)) {
  const relativePath = normalizePath(path.relative(root, filePath))
  const rule = rules.find((candidate) => candidate.matches(relativePath))
  if (!rule) continue

  const lines = countLines(filePath)
  const allowed = allowlist[relativePath]
  if (allowed) checkedAllowlistKeys.add(relativePath)

  if (lines <= rule.target) {
    if (allowed) staleAllowlist.push({ relativePath, lines, target: rule.target })
    continue
  }

  if (!allowed) {
    violations.push({
      relativePath,
      lines,
      limit: rule.target,
      message: `exceeds ${rule.name} target`,
    })
    continue
  }

  if (typeof allowed.maxLines !== "number" || lines > allowed.maxLines) {
    violations.push({
      relativePath,
      lines,
      limit: allowed.maxLines ?? rule.target,
      message: `exceeds allowlisted cap`,
    })
  }
}

for (const key of Object.keys(allowlist)) {
  if (!checkedAllowlistKeys.has(key) && !fs.existsSync(path.join(root, key))) {
    staleAllowlist.push({ relativePath: key, lines: 0, target: 0 })
  }
}

if (violations.length > 0) {
  console.error("Surface size check failed:")
  for (const violation of violations) {
    console.error(`- ${violation.relativePath}: ${violation.lines} lines, limit ${violation.limit} (${violation.message})`)
  }
  console.error("Split the surface or add a specific allowlist entry with a current-line cap and reason.")
  process.exit(1)
}

if (staleAllowlist.length > 0) {
  console.warn("Surface size allowlist has entries that can be tightened or removed:")
  for (const entry of staleAllowlist) {
    console.warn(`- ${entry.relativePath}: ${entry.lines} lines, target ${entry.target}`)
  }
}

console.log("Surface size check passed.")
