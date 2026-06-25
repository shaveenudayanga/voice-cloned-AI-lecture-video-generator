// SPDX-License-Identifier: Apache-2.0
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    typedRoutes: true,
  },
};

export default nextConfig;
