import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // The organiser area used to live under /committee: keep old links and bookmarks working
  async redirects() {
    return [
      { source: "/committee", destination: "/dashboard", permanent: true },
      { source: "/committee/fests", destination: "/dashboard/fests", permanent: true },
      { source: "/committee/city-events", destination: "/dashboard/city-events", permanent: true },
      { source: "/committee/:slug", destination: "/dashboard/fests/:slug", permanent: true },
    ];
  },
};

export default nextConfig;
