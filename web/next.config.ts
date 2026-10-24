import type { NextConfig } from "next";

const common = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        // Dashboard and auth pages must never be framed (clickjacking).
        source: "/((?!embed/).*)",
        headers: [...common, { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" }],
      },
      {
        // The chat iframe is meant to be embedded on customers' sites.
        source: "/embed/:path*",
        headers: [...common, { key: "Content-Security-Policy", value: "frame-ancestors *" }],
      },
      {
        source: "/widget.js",
        headers: [{ key: "Cache-Control", value: "public, max-age=300" }],
      },
    ];
  },
};

export default nextConfig;
