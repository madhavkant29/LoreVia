import { describe, expect, it } from "vitest"

import { validateRegisterPassword, validateRegisterUsername } from "./registerValidation"

describe("registerValidation", () => {
  it("rejects passwords shorter than 12 characters", () => {
    expect(validateRegisterPassword("Short1!", "writer@example.com")).toEqual({
      isValid: false,
      message: "Password must be at least 12 characters long.",
    })
  })

  it("rejects passwords without uppercase and lowercase letters", () => {
    expect(validateRegisterPassword("lowercase123!", "writer@example.com").message).toBe(
      "Password must include both uppercase and lowercase letters."
    )
  })

  it("rejects passwords without a number", () => {
    expect(validateRegisterPassword("LongPassword!", "writer@example.com").message).toBe(
      "Password must include at least one number."
    )
  })

  it("rejects passwords without a symbol", () => {
    expect(validateRegisterPassword("LongPassword12", "writer@example.com").message).toBe(
      "Password must include at least one symbol."
    )
  })

  it("rejects passwords that contain the email local part", () => {
    expect(validateRegisterPassword("WriterPass12!", "writer@example.com").message).toBe(
      "Password cannot contain the name from your email address."
    )
  })

  it("rejects passwords with repeated characters", () => {
    expect(validateRegisterPassword("AAAsecure12!", "writer@example.com").message).toBe(
      "Password cannot contain the same character repeated three or more times in a row."
    )
  })

  it("accepts a strong password that meets every rule", () => {
    expect(validateRegisterPassword("Orbit!Frame92", "writer@example.com")).toEqual({
      isValid: true,
      message: null,
    })
  })

  it("rejects usernames shorter than 3 characters", () => {
    expect(validateRegisterUsername("ab")).toBe("Username must be at least 3 characters long.")
  })

  it("accepts usernames within the supported range", () => {
    expect(validateRegisterUsername("lore_writer")).toBeNull()
  })
})
