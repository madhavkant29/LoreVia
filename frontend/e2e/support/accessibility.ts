import type { Page } from "@playwright/test"
import axe from "axe-core"

type AxeViolation = {
  help: string
  id: string
  impact: string | null
  nodes: Array<{ target: string[] }>
}

export async function criticalAccessibilityViolations(
  page: Page,
  selector?: string,
): Promise<string[]> {
  await page.addScriptTag({ content: axe.source })
  const violations = await page.evaluate(async (contextSelector) => {
    const runner = (window as unknown as Window & {
      axe: {
        run: (
          context: Document | Element,
          options: Record<string, unknown>,
        ) => Promise<{ violations: AxeViolation[] }>
      }
    }).axe
    const context = contextSelector ? document.querySelector(contextSelector) : document
    if (!context) throw new Error(`Accessibility context not found: ${contextSelector}`)
    const results = await runner.run(context, {
      resultTypes: ["violations"],
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
      },
    })
    return results.violations
      .filter((violation) => violation.impact === "critical" || violation.impact === "serious")
      .map((violation) =>
        `${violation.id} (${violation.impact}): ${violation.help}; ${violation.nodes
          .map((node) => node.target.join(" "))
          .join(", ")}`,
      )
  }, selector)
  return violations
}
