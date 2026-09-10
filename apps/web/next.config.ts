import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@bible-strong/avatar-react", "@bible-strong/avatar-core"],
};

export default nextConfig;
