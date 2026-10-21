import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/api";

export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: "/", disallow: ["/my-passes", "/profile", "/committee", "/login", "/signup"] }, sitemap: `${SITE_URL}/sitemap.xml` };
}
