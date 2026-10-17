"use client"

import type { ComponentProps, RefObject } from "react"

import { ManuscriptAnalysisRail } from "./manuscriptPage.analysisRail"
import { ManuscriptAnnotationHighlightStyles } from "./manuscriptPage.annotationHighlightStyles"
import { WhatsTheWordPanel } from "./manuscriptPage.dynamic"
import { ManuscriptEditorPanel } from "./manuscriptPage.editorPanel"
import { ManuscriptEditorStatusFooter } from "./manuscriptPage.editorStatusFooter"
import { ManuscriptHeader } from "./manuscriptPage.header"
import { WorkspaceSidePanel } from "@/components/ui/WorkspaceSidePanel"
import { ManuscriptLeftRail } from "./manuscriptPage.leftRail"
import { ManuscriptNonWriteWorkspaceSection } from "./manuscriptPage.nonWriteWorkspace"
import { ManuscriptOverlayStack } from "./manuscriptPage.overlayStack"
import { ManuscriptPlanWorkspaceSection } from "./manuscriptPage.planWorkspace"
import { ManuscriptSelectionMenu } from "./manuscriptPage.selectionMenu"
import { ManuscriptWriteRail } from "./manuscriptPage.writeRail"
import type { WorkspaceTab } from "./manuscriptPage.constants"

export type ManuscriptSelectionMenuProps = ComponentProps<typeof ManuscriptSelectionMenu>
export type ManuscriptHeaderProps = ComponentProps<typeof ManuscriptHeader>
export type ManuscriptPlanWorkspaceSectionProps = ComponentProps<typeof ManuscriptPlanWorkspaceSection>
export type ManuscriptOverlayStackProps = ComponentProps<typeof ManuscriptOverlayStack>
export type ManuscriptLeftRailProps = ComponentProps<typeof ManuscriptLeftRail>
export type ManuscriptEditorPanelProps = ComponentProps<typeof ManuscriptEditorPanel>
export type ManuscriptEditorStatusFooterProps = ComponentProps<typeof ManuscriptEditorStatusFooter>
export type ManuscriptNonWriteWorkspaceSectionProps = ComponentProps<typeof ManuscriptNonWriteWorkspaceSection>
export type ManuscriptWriteRailProps = ComponentProps<typeof ManuscriptWriteRail>
export type ManuscriptAnalysisRailProps = ComponentProps<typeof ManuscriptAnalysisRail>

type ManuscriptPageLayoutProps = {
  analysisRailProps: ManuscriptAnalysisRailProps
  bookId: string
  desktopLayoutClass: string
  editorPanelProps: ManuscriptEditorPanelProps
  editorStatusFooterProps: ManuscriptEditorStatusFooterProps
  headerProps: ManuscriptHeaderProps
  isDark: boolean
  leftRailProps: ManuscriptLeftRailProps
  leftRailVisible: boolean
  manuscriptSectionRef: RefObject<HTMLDivElement | null>
  nonWriteWorkspaceProps: ManuscriptNonWriteWorkspaceSectionProps
  overlayStackProps: ManuscriptOverlayStackProps
  planWorkspaceProps: ManuscriptPlanWorkspaceSectionProps
  rightRailVisible: boolean
  selectionMenuProps: ManuscriptSelectionMenuProps
  statusMessage: string | null
  workspaceTab: WorkspaceTab
  writeRailProps: ManuscriptWriteRailProps
}

export function ManuscriptPageLayout({
  analysisRailProps,
  bookId,
  desktopLayoutClass,
  editorPanelProps,
  editorStatusFooterProps,
  headerProps,
  isDark,
  leftRailProps,
  leftRailVisible,
  manuscriptSectionRef,
  nonWriteWorkspaceProps,
  overlayStackProps,
  planWorkspaceProps,
  rightRailVisible,
  selectionMenuProps,
  statusMessage,
  workspaceTab,
  writeRailProps,
}: ManuscriptPageLayoutProps) {
  return (
    <div data-manuscript-workspace className={`min-h-screen overflow-x-clip ${isDark ? "bg-[#101416] text-slate-100" : "bg-[#f4f5f3] text-stone-950"}`}>
      <ManuscriptAnnotationHighlightStyles isDark={isDark} />
      <ManuscriptSelectionMenu {...selectionMenuProps} />
      <div className="pb-10">
        <ManuscriptHeader {...headerProps} />

        <div id="manuscript-workspace-panel" role="tabpanel" aria-labelledby={`manuscript-tab-${workspaceTab}`} tabIndex={0}>
        {workspaceTab === "plan" ? (
          <ManuscriptPlanWorkspaceSection {...planWorkspaceProps} />
        ) : null}
        {workspaceTab !== "plan" ? (
          <div className={`grid min-h-[calc(100vh-8.25rem)] min-w-0 ${desktopLayoutClass}`}>
            {leftRailVisible ? (
              <WorkspaceSidePanel title="Manuscript outline" side="left" onClose={() => headerProps.onOutlineOpenChange(false)}>
                <ManuscriptLeftRail {...leftRailProps} onSelectChapter={(chapterNumber) => {
                  leftRailProps.onSelectChapter(chapterNumber)
                  if (!window.matchMedia("(min-width: 1280px)").matches) headerProps.onOutlineOpenChange(false)
                }} />
              </WorkspaceSidePanel>
            ) : null}

            <section ref={manuscriptSectionRef} className={`min-w-0 border-r p-0 ${!leftRailVisible && !rightRailVisible ? "xl:mx-auto xl:max-w-[1040px]" : ""} ${isDark ? "border-white/10 bg-[#0b1114]" : "border-stone-200 bg-[#faf8f4]"}`}>
              {workspaceTab !== "write" ? (
                <ManuscriptNonWriteWorkspaceSection {...nonWriteWorkspaceProps} />
              ) : null}
              <WhatsTheWordPanel bookId={bookId} isDark={isDark} className="mx-auto w-full max-w-[1040px] px-4 py-3" />

              <ManuscriptEditorPanel {...editorPanelProps} />

              <ManuscriptEditorStatusFooter {...editorStatusFooterProps} />
              {statusMessage ? <p role="status" className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{statusMessage}</p> : null}
            </section>

            {rightRailVisible ? (
              <WorkspaceSidePanel title={workspaceTab === "write" ? "Writing inspector" : "Analysis inspector"} side="right" onClose={() => headerProps.onInspectorOpenChange(false)}>
                {workspaceTab === "write" ? <ManuscriptWriteRail {...writeRailProps} /> : <ManuscriptAnalysisRail {...analysisRailProps} />}
              </WorkspaceSidePanel>
            ) : null}

          </div>
        ) : null}

        </div>
        <ManuscriptOverlayStack {...overlayStackProps} />
      </div>
    </div>
  )
}
