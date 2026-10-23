"use client";

import { usePathname } from "next/navigation";
import { Footer } from "./Footer";
import { TopBar } from "./TopBar";

/**
 * The public site has a top bar and a footer. The admin area and the organiser dashboard are workspaces with their own
 * sidebar, so they get neither, and a flatter, denser look of their own.
 */
export function SiteChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname.startsWith("/admin") || pathname.startsWith("/dashboard")) return <div className="workspace">{children}</div>;
  return (
    <>
      <TopBar />
      <main className="pt-24">{children}</main>
      <Footer />
    </>
  );
}
