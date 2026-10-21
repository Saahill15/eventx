"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { Compass, Ticket, Tent, User } from "lucide-react";
import { useAuth } from "@/lib/auth";

/** App-style tab bar for phones. */
export function Dock() {
  const pathname = usePathname();
  const { user } = useAuth();
  const items = [
    { href: "/", label: "Discover", icon: Compass, on: pathname === "/" },
    { href: "/fests", label: "Fests", icon: Tent, on: pathname.startsWith("/fest") },
    { href: "/my-passes", label: "Passes", icon: Ticket, on: pathname.startsWith("/my-passes") },
    { href: user ? "/profile" : "/login", label: user ? "Me" : "Sign in", icon: User, on: pathname.startsWith("/profile") || pathname.startsWith("/login") || pathname.startsWith("/signup") },
  ];
  if (pathname.startsWith("/committee") || pathname.startsWith("/admin")) return null;
  return (
    <nav aria-label="Tabs" className="pointer-events-none fixed inset-x-0 bottom-0 z-50 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:hidden">
      <div className="glass pointer-events-auto mx-auto flex max-w-sm items-center justify-between rounded-full p-1.5 shadow-[var(--shadow-pop)]">
        {items.map(({ href, label, icon: Icon, on }) => (
          <Link key={label} href={href} aria-current={on ? "page" : undefined} className="relative flex flex-1 flex-col items-center gap-0.5 rounded-full py-2 text-[11px] font-semibold">
            {on && <motion.span layoutId="dock-pill" className="absolute inset-0 rounded-full bg-ink" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
            <Icon className={`relative h-5 w-5 ${on ? "text-white" : "text-mute"}`} />
            <span className={`relative ${on ? "text-white" : "text-mute"}`}>{label}</span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
