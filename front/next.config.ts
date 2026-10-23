import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async redirects() {
    // The people page is /admin/people; /admin/users is kept as an alias that links and bookmarks can use
    return [{ source: "/admin/users", destination: "/admin/people", permanent: false }];
  },
};

export default nextConfig;
