"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "./api";
import { removeLegacyToken } from "./legacyToken";

/**
 * Client-side guard. The session cookie is httpOnly, so the page can't inspect it; ask the API instead.
 * Returns true once the session is confirmed; a 401 redirects to /login.
 */
export function useRequireAuth(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    removeLegacyToken();
    let active = true;
    api
      .me()
      .then(() => active && setReady(true))
      .catch(() => active && router.replace("/login"));
    return () => {
      active = false;
    };
  }, [router]);
  return ready;
}
