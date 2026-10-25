// Before sessions moved to an httpOnly cookie, the bearer token was kept here, readable by any script.
const LEGACY_KEY = "docbot_token";

/** Delete a token left in localStorage by older versions. Storage can throw (private mode); ignore that. */
export function removeLegacyToken(
  storage: Pick<Storage, "removeItem"> | undefined = typeof localStorage === "undefined" ? undefined : localStorage,
): void {
  try {
    storage?.removeItem(LEGACY_KEY);
  } catch {
    /* storage unavailable: nothing to clean */
  }
}
