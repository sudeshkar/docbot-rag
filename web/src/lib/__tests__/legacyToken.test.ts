import { describe, expect, it } from "vitest";
import { removeLegacyToken } from "../legacyToken";

function memoryStorage(entries: Record<string, string>) {
  const data = new Map(Object.entries(entries));
  return {
    getItem: (k: string) => data.get(k) ?? null,
    removeItem: (k: string) => void data.delete(k),
    keys: () => [...data.keys()],
  };
}

describe("removeLegacyToken", () => {
  it("deletes the bearer token older versions kept in localStorage, and nothing else", () => {
    const storage = memoryStorage({ docbot_token: "eyJ...", theme: "dark" });
    removeLegacyToken(storage);
    expect(storage.keys()).toEqual(["theme"]);
  });

  it("never throws when storage is unavailable (private mode, blocked storage)", () => {
    const broken = {
      removeItem: () => {
        throw new Error("SecurityError");
      },
    };
    expect(() => removeLegacyToken(broken)).not.toThrow();
    expect(() => removeLegacyToken(undefined)).not.toThrow();
  });
});
