import { describe, expect, it } from "vitest";
import { linkCitations } from "../citations";

describe("linkCitations", () => {
  it("turns [n] into markdown links for known sources only", () => {
    expect(linkCitations("Refunds take 5 days [1][2]. See [9].", [1, 2])).toBe(
      "Refunds take 5 days [1](#cite-1)[2](#cite-2). See [9].",
    );
  });

  it("does not touch existing markdown links", () => {
    expect(linkCitations("[docs](https://x.com) [1]", [1])).toBe("[docs](https://x.com) [1](#cite-1)");
  });
});
