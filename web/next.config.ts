import type { NextConfig } from "next";

const config: NextConfig = {
  // Page images are served straight off the API as PNGs. next/image would add
  // a remote-loader round trip for no benefit, so they render as plain <img>.
  reactStrictMode: true,
};

export default config;
