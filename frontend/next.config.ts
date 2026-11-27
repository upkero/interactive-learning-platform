import path from "node:path";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/shared/i18n/request.ts");

const API_INTERNAL_URL =
  process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: process.env.NEXT_STANDALONE === "1" ? "standalone" : undefined,
  outputFileTracingRoot: path.resolve(__dirname, ".."),
  transpilePackages: ["@grasp/primitives"],
  experimental: {
    // External API rewrites buffer the 50 MiB upload plus multipart overhead.
    middlewareClientMaxBodySize: "55mb",
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL_URL}/api/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
