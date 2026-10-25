import { describe, expect, it } from "vitest";
import { safeHref } from "../url";

describe("safeHref", () => {
  it.each([
    "https://help.acme.com/refunds",
    "http://example.com/a?b=1#c",
    "mailto:support@acme.com",
  ])("allows %s", (url) => {
    expect(safeHref(url)).toBe(new URL(url).href);
  });

  it.each([
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    " javascript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "/relative/path",
    "//evil.example/x",
    "not a url",
    "",
    undefined,
    null,
  ])("rejects %s", (url) => {
    expect(safeHref(url as string | undefined)).toBeUndefined();
  });
});
