import { describe, expect, it } from "vitest";
import { parseSSE, readSSE } from "../sse";

describe("parseSSE", () => {
  it("parses complete events and keeps the partial tail", () => {
    const { events, rest } = parseSSE(
      'event: meta\ndata: {"conversation_id":"c1"}\n\nevent: token\ndata: "Hel',
    );
    expect(events).toEqual([{ event: "meta", data: { conversation_id: "c1" } }]);
    expect(rest).toBe('event: token\ndata: "Hel');
  });

  it("handles CRLF line endings and ignores malformed blocks", () => {
    const { events } = parseSSE('event: token\r\ndata: "a"\r\n\r\nevent: token\ndata: {bad json\n\n');
    expect(events).toEqual([{ event: "token", data: "a" }]);
  });
});

describe("readSSE", () => {
  it("yields events across arbitrary network chunk boundaries", async () => {
    const body = 'event: token\ndata: "Hello "\n\nevent: token\ndata: "world"\n\nevent: done\ndata: {"answered":true}\n\n';
    const enc = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (let i = 0; i < body.length; i += 7) controller.enqueue(enc.encode(body.slice(i, i + 7)));
        controller.close();
      },
    });
    const out = [];
    for await (const ev of readSSE(stream)) out.push(ev);
    expect(out).toEqual([
      { event: "token", data: "Hello " },
      { event: "token", data: "world" },
      { event: "done", data: { answered: true } },
    ]);
  });
});
