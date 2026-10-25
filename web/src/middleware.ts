import { NextResponse, type NextRequest } from "next/server";
import { createFrameAncestorsResolver } from "@/lib/embedPolicy";

// Server-side calls go straight to the API: in production NEXT_PUBLIC_API_URL is the relative
// "/api" (same origin through Caddy), which a server can't fetch, so the stack sets INTERNAL_API_URL.
const publicUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
const apiUrl = process.env.INTERNAL_API_URL ?? (publicUrl.startsWith("http") ? publicUrl : "http://localhost:8000");

const resolveFrameAncestors = createFrameAncestorsResolver(apiUrl);

/** The chat iframe may only be framed by the bot's allowed sites, and the browser enforces it. */
export async function middleware(request: NextRequest) {
  const key = request.nextUrl.pathname.split("/")[2] ?? "";
  const response = NextResponse.next();
  response.headers.set("Content-Security-Policy", await resolveFrameAncestors(decodeURIComponent(key)));
  return response;
}

export const config = { matcher: "/embed/:key*" };
