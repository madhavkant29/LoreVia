// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  click,
  firstField,
  flush,
  queryClientMock,
  renderElement,
  searchParamsMock,
  setFieldValue,
  socialApiMock,
  text,
  unmountCurrentRoot,
} from "./runtime-zero-components.test-utils"

import { ChatsPanel } from "@/components/layout/ChatsPanel"

describe("chats panel runtime coverage", () => {
  it("hydrates conversations, searches users, sends requests, and posts messages", async () => {
    searchParamsMock.set("username", "lina")
    await renderElement(<ChatsPanel mode="page" enabled />)

    expect(text()).toContain("Private chats")
    expect(text()).toContain("@theo")
    expect(socialApiMock.listConversationsPage).toHaveBeenCalled()
    expect(socialApiMock.listMessagesPage.mock.calls[0]?.[0]).toBe("conversation-1")
    setFieldValue(firstField<HTMLTextAreaElement>('textarea[aria-label="Message"]'), "I can read it tonight.")
    await click("Send")
    expect(socialApiMock.sendMessage).toHaveBeenCalledWith("conversation-1", "I can read it tonight.")

    setFieldValue(firstField<HTMLInputElement>('input[aria-label="Search usernames"]'), "lina")
    await act(flush)
    expect(socialApiMock.searchUsers).toHaveBeenCalledWith("lina")

    unmountCurrentRoot()
    queryClientMock.getQueryData.mockImplementation((key: string[]) =>
      key.includes("conversations") ? { items: [] } : null,
    )
    socialApiMock.listConversationsPage.mockResolvedValueOnce({
      items: [],
      next_cursor: null,
      has_more: false,
    })
    await renderElement(<ChatsPanel mode="sidebar" enabled />)
    setFieldValue(firstField<HTMLInputElement>('input[aria-label="Search usernames"]'), "lina")
    await act(flush)
    await click("@lina")
    await click("Send friend request")
    expect(socialApiMock.sendFriendRequest).toHaveBeenCalledWith("user-3")
  })
})
