"use client";

import { usePathname } from "next/navigation";
import { Footer } from "./Footer";

/** The public footer is left out of the admin and committee areas, which are workspaces rather than pages to browse. */
export function SiteFooter() {
  const pathname = usePathname();
  return pathname.startsWith("/admin") || pathname.startsWith("/dashboard") ? null : <Footer />;
}
