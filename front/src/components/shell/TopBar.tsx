"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { LayoutDashboard, LogOut, Search, ShieldCheck, Ticket, User as UserIcon } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "../ui/Button";
import { SearchPalette } from "./SearchPalette";

const NAV = [
  { href: "/", label: "Discover" },
  { href: "/fests", label: "Fests" },
  { href: "/events", label: "Events" },
];

export function TopBar() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [search, setSearch] = useState(false);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setMenu(false); }, [pathname]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName);
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) { e.preventDefault(); setSearch(true); }
    };
    const onClick = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false); };
    const onOpen = () => setSearch(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("hiveout:search", onOpen);
    document.addEventListener("mousedown", onClick);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("hiveout:search", onOpen); document.removeEventListener("mousedown", onClick); };
  }, []);

  const active = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href) || (href === "/fests" && pathname.startsWith("/fest/")));

  return (
    <>
      <header className="glass-bar sticky top-0 z-50">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-5 sm:px-8">
          <Link href="/" aria-label="HiveOut home" className="shrink-0"><Image src="/logo.png" alt="HiveOut" width={116} height={28} priority className="h-6 w-auto max-w-none" /></Link>

          <nav aria-label="Main" className="relative hidden rounded-full bg-wash p-1 md:flex">
            {NAV.map((l) => (
              <Link key={l.href} href={l.href} className={`relative rounded-full px-5 py-2 text-sm font-semibold transition-colors ${active(l.href) ? "text-ink" : "text-mute hover:text-ink"}`}>
                {active(l.href) && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-full bg-white shadow-[var(--shadow-soft)]" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
                <span className="relative">{l.label}</span>
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <button onClick={() => setSearch(true)} aria-label="Search" className="hairline flex h-10 items-center gap-2 rounded-full bg-white px-3 text-sm text-mute transition hover:bg-wash sm:px-4">
              <Search className="h-4 w-4" />
              <span className="hidden sm:inline">Search</span>
              <kbd className="hidden rounded bg-wash px-1.5 text-xs lg:inline">/</kbd>
            </button>
            {loading ? <div className="h-10 w-20" /> : user ? (
              <div className="relative" ref={menuRef}>
                <button onClick={() => setMenu((v) => !v)} aria-haspopup="menu" aria-expanded={menu} aria-label="Account menu" className="flex h-10 w-10 items-center justify-center rounded-full bg-ink text-sm font-bold text-white transition hover:bg-neutral-700">
                  {user.name.trim().charAt(0).toUpperCase()}
                </button>
                <AnimatePresence>
                  {menu && (
                    <motion.div role="menu" initial={{ opacity: 0, y: -6, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: 0.96 }} transition={{ duration: 0.15 }} style={{ transformOrigin: "top right" }} className="glass absolute right-0 mt-2 w-60 rounded-2xl p-1.5 shadow-[var(--shadow-pop)]">
                      <div className="px-3 py-2"><p className="truncate font-semibold">{user.name}</p><p className="truncate text-xs text-mute">{user.email}</p></div>
                      <Item href="/my-passes" icon={<Ticket className="h-4 w-4" />}>My passes</Item>
                      <Item href="/committee" icon={<LayoutDashboard className="h-4 w-4" />}>Committee</Item>
                      {user.role === "admin" && <Item href="/admin" icon={<ShieldCheck className="h-4 w-4" />}>Admin</Item>}
                      <Item href="/profile" icon={<UserIcon className="h-4 w-4" />}>Profile</Item>
                      <button role="menuitem" onClick={() => { logout(); router.push("/"); }} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-700 hover:bg-black/5"><LogOut className="h-4 w-4" /> Sign out</button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ) : (
              <>
                <Link href="/login" className="hidden px-3 text-sm font-semibold text-mute hover:text-ink sm:block">Sign in</Link>
                <Button href="/signup" size="sm">Join free</Button>
              </>
            )}
          </div>
        </div>
      </header>
      <SearchPalette open={search} onClose={() => setSearch(false)} />
    </>
  );
}

function Item({ href, icon, children }: { href: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <Link href={href} role="menuitem" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-700 hover:bg-black/5">{icon} {children}</Link>;
}
