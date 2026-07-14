"use client"

import { ManuscriptPageLayout } from "./manuscriptPage.layout"
import { ManuscriptEditorSkeleton } from "./manuscriptPage.loading"
import { useManuscriptActionBindings } from "./manuscriptPage.actionBindings"
import { useManuscriptDocumentBindings } from "./manuscriptPage.documentBindings"
import { buildManuscriptRenderProps } from "./manuscriptPage.renderProps"
import { useManuscriptRuntimeEffects } from "./manuscriptPage.runtimeEffects"
import { useManuscriptPageSetup } from "./manuscriptPage.setup"

export function ManuscriptPageInner() {
  const setup = useManuscriptPageSetup()
  const documentBindings = useManuscriptDocumentBindings(setup)

  useManuscriptRuntimeEffects(setup)

  const actionBindings = useManuscriptActionBindings({
    ...setup,
    ...documentBindings,
  })
  const renderProps = buildManuscriptRenderProps({
    ...setup,
    ...documentBindings,
    ...actionBindings,
  })

  if (setup.loading) {
    return <ManuscriptEditorSkeleton isDark={setup.isDark} />
  }

  return (
    <ManuscriptPageLayout
      analysisRailProps={renderProps.analysisRailProps}
      bookId={setup.bookId}
      desktopLayoutClass={renderProps.desktopLayoutClass}
      editorPanelProps={renderProps.editorPanelProps}
      editorStatusFooterProps={renderProps.editorStatusFooterProps}
      headerProps={renderProps.headerProps}
      isDark={setup.isDark}
      leftRailProps={renderProps.leftRailProps}
      leftRailVisible={renderProps.leftRailVisible}
      manuscriptSectionRef={setup.manuscriptSectionRef}
      nonWriteWorkspaceProps={renderProps.nonWriteWorkspaceProps}
      overlayStackProps={renderProps.overlayStackProps}
      planWorkspaceProps={renderProps.planWorkspaceProps}
      rightRailVisible={renderProps.rightRailVisible}
      selectionMenuProps={renderProps.selectionMenuProps}
      statusMessage={setup.statusMessage}
      workspaceTab={setup.workspaceTab}
      writeRailProps={renderProps.writeRailProps}
    />
  )
}
