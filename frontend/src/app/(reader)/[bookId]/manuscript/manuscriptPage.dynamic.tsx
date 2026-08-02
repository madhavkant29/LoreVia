"use client"

import dynamic from "next/dynamic"

import { DeferredPanelLoadingState } from "./manuscriptPage.loading"

export const WhatsTheWordPanel = dynamic(
  () => import("@/components/intelligence/WhatsTheWordPanel").then((module) => module.WhatsTheWordPanel),
  {
    loading: () => <DeferredPanelLoadingState label="Loading word finder..." />,
  }
)

export const EditorToolbar = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.EditorToolbar),
)

export const RichTextEditor = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.RichTextEditor),
)

export const ManuscriptPagedPreview = dynamic(
  () => import("@/components/reader/ManuscriptPagedPreview").then((module) => module.ManuscriptPagedPreview),
  {
    loading: () => <DeferredPanelLoadingState label="Preparing preview..." />,
  }
)

export const ManuscriptPlanWorkspace = dynamic(
  () => import("@/components/reader/ManuscriptPlanWorkspace").then((module) => module.ManuscriptPlanWorkspace),
  {
    loading: () => <DeferredPanelLoadingState label="Loading planning workspace..." />,
  }
)

export const ManuscriptNonWriteWorkspace = dynamic(
  () => import("@/components/reader/ManuscriptNonWriteWorkspace").then((module) => module.ManuscriptNonWriteWorkspace),
  {
    loading: () => <DeferredPanelLoadingState label="Loading analysis workspace..." />,
  }
)

export const ManuscriptOverlayDialogs = dynamic(
  () => import("@/components/reader/ManuscriptOverlayDialogs").then((module) => module.ManuscriptOverlayDialogs),
  {
    loading: () => null,
  }
)

export const ManuscriptWriteRightRail = dynamic(
  () => import("@/components/reader/ManuscriptWriteRightRail").then((module) => module.ManuscriptWriteRightRail),
  {
    loading: () => <DeferredPanelLoadingState label="Loading writing tools..." />,
  }
)
