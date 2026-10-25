import type { NextConfig } from "next";

const common = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  // Self-contained server bundle for the production Docker image.
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [
      {
        // Dashboard and auth pages must never be framed (clickjacking).
        source: "/((?!embed/).*)",
        headers: [...common, { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" }],
      },
      {
        // The chat iframe's frame-ancestors is per bot, set in src/middleware.ts.
        source: "/embed/:path*",
        headers: common,
      },
      {
        source: "/widget.js",
        headers: [{ key: "Cache-Control", value: "public, max-age=300" }],
      },
    ];
  },
};

export default nextConfig;
