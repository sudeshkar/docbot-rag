export type SSEEvent = { event: string; data: unknown };

/** Parse complete SSE blocks from a buffer; returns the unfinished tail to prepend to the next chunk. */
export function parseSSE(buffer: string): { events: SSEEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: SSEEvent[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) event = line.slice(7);
      else if (line.startsWith("data: ")) data.push(line.slice(6));
    }
    if (!data.length) continue;
    try {
      events.push({ event, data: JSON.parse(data.join("\n")) });
    } catch {
      /* skip malformed block */
    }
  }
  return { events, rest };
}

/** Yield SSE events from a streamed body, regardless of how the network splits it. */
export async function* readSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<SSEEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSSE(buffer);
      buffer = rest;
      yield* events;
    }
    const { events } = parseSSE(buffer + decoder.decode() + "\n\n");
    yield* events;
  } finally {
    reader.releaseLock();
  }
}
