import type { CanonOverride } from "@/types/world-building"

import { LabeledField, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import {
  badgeClass,
  inputClass,
  mutedTextClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "./WorldbuildingWorkspace.helpers"

export function CanonOverrideCard({
  isDark,
  canonName,
  canonAliases,
  canonOverrides,
  savingCanon,
  onCanonNameChange,
  onCanonAliasesChange,
  onSaveCanonOverride,
  onRefreshCanonOverrides,
}: {
  isDark: boolean
  canonName: string
  canonAliases: string
  canonOverrides: CanonOverride[]
  savingCanon: boolean
  onCanonNameChange: (value: string) => void
  onCanonAliasesChange: (value: string) => void
  onSaveCanonOverride: () => void
  onRefreshCanonOverrides: () => void
}) {
  return (
    <WorkspaceCard
      number="4"
      sectionLabel="Canon Overrides"
      title="Canon Overrides / Aliases"
      description="Map names and aliases to keep your canon consistent."
      isDark={isDark}
      action={(
        <button type="button" onClick={onRefreshCanonOverrides} className={secondaryButtonClass(isDark)}>
          Refresh
        </button>
      )}
    >
      <div className="space-y-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <LabeledField label="Canonical name" isDark={isDark}>
            <input
              value={canonName}
              onChange={(event) => onCanonNameChange(event.target.value)}
              className={inputClass(isDark)}
            />
          </LabeledField>
          <LabeledField label="Aliases" isDark={isDark}>
            <input
              value={canonAliases}
              onChange={(event) => onCanonAliasesChange(event.target.value)}
              className={inputClass(isDark)}
            />
          </LabeledField>
          <div className="flex items-end">
            <button
              type="button"
              onClick={onSaveCanonOverride}
              disabled={savingCanon || !canonName.trim()}
              className={primaryButtonClass("violet")}
            >
              {savingCanon ? "Saving..." : "Save override"}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {canonOverrides.map((item) => (
            <span key={item.id} className={badgeClass(isDark)}>
              {item.canonical_name}{item.aliases.length ? `: ${item.aliases.join(", ")}` : ""}
            </span>
          ))}
          {canonOverrides.length === 0 ? <p className={`text-sm ${mutedTextClass(isDark)}`}>No alias overrides yet.</p> : null}
        </div>
      </div>
    </WorkspaceCard>
  )
}
