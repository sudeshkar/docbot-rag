import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReactMarkdown from "react-markdown";
import { describe, expect, it } from "vitest";
import { markdownComponents } from "../markdown";

// Answers are LLM output shaped by crawled documents, so treat them as attacker-controlled.
function render(md: string) {
  return renderToStaticMarkup(createElement(ReactMarkdown, { components: markdownComponents(new Map()) }, md));
}

describe("chat markdown rendering", () => {
  it("shows raw HTML as text instead of executing it", () => {
    const html = render('<script>alert(1)</script> <img src=x onerror="alert(1)">');
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<img");
  });

  it("never renders a clickable javascript: link", () => {
    const html = render("[click me](javascript:alert(document.cookie))");
    expect(html).not.toMatch(/javascript:/i);
    expect(html).toContain("click me");
  });

  it("keeps safe links, opening in a new tab without referrer or opener", () => {
    const html = render("[docs](https://help.acme.com)");
    expect(html).toContain('href="https://help.acme.com/"');
    expect(html).toContain('rel="noopener noreferrer nofollow"');
  });

  it("does not render images (no tracking pixels or data: payloads)", () => {
    expect(render("![x](https://evil.example/pixel.png)")).not.toContain("<img");
  });
});
