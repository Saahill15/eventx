"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { LayoutDashboard, LogOut, Menu, Search, ShieldCheck, Ticket, User as UserIcon, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "../ui/Button";
import { SearchPalette } from "./SearchPalette";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/fests", label: "College fests" },
  { href: "/events", label: "Events" },
];

export function TopBar() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [search, setSearch] = useState(false);
  const [menu, setMenu] = useState(false);
  const [sheet, setSheet] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setMenu(false); setSheet(false); }, [pathname]);
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
  const round = "flex h-11 w-11 items-center justify-center rounded-2xl bg-white shadow-[var(--shadow-card)] transition hover:bg-wash active:scale-95";

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50 px-4 pt-4 sm:px-6">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
          <Link href="/" aria-label="HiveOut home" className="flex h-11 items-center rounded-2xl bg-white/90 px-4 shadow-[var(--shadow-card)] backdrop-blur-xl transition hover:bg-white">
            <Image src="/logo.png" alt="HiveOut" width={116} height={28} priority className="h-5 w-auto max-w-none" />
          </Link>

          <nav aria-label="Main" className="relative hidden rounded-full bg-white/80 p-1 shadow-[var(--shadow-card)] backdrop-blur-xl md:flex">
            {NAV.map((l) => (
              <Link key={l.href} href={l.href} className={`relative rounded-full px-5 py-2 text-sm font-medium transition-colors ${active(l.href) ? "text-chip-ink" : "text-mute hover:text-ink"}`}>
                {active(l.href) && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-full bg-chip" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
                <span className="relative">{l.label}</span>
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <button onClick={() => setSearch(true)} aria-label="Search" className={round}><Search className="h-[18px] w-[18px]" /></button>
            {loading ? <div className="h-11 w-11" /> : user ? (
              <div className="relative hidden md:block" ref={menuRef}>
                <button onClick={() => setMenu((v) => !v)} aria-haspopup="menu" aria-expanded={menu} aria-label="Account menu" className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand text-sm font-semibold text-on-brand shadow-[var(--shadow-glow)] transition active:scale-95">{user.name.trim().charAt(0).toUpperCase()}</button>
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
              <div className="hidden items-center gap-2 md:flex">
                <Link href="/login" className="px-3 text-sm font-medium text-mute hover:text-ink">Sign in</Link>
                <Button href="/signup" size="sm">Join free</Button>
              </div>
            )}
            <button onClick={() => setSheet((v) => !v)} aria-label={sheet ? "Close menu" : "Open menu"} aria-expanded={sheet} className={`${round} md:hidden`}>{sheet ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
          </div>
        </div>

        <AnimatePresence>
          {sheet && (
            <motion.div initial={{ opacity: 0, y: -10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -10, scale: 0.98 }} transition={{ duration: 0.2 }} className="glass mx-auto mt-3 max-w-7xl rounded-3xl p-3 shadow-[var(--shadow-pop)] md:hidden">
              {NAV.map((l) => <Link key={l.href} href={l.href} className={`block rounded-2xl px-4 py-3.5 text-lg font-medium ${active(l.href) ? "bg-chip text-chip-ink" : ""}`}>{l.label}</Link>)}
              <div className="my-2 border-t border-black/5" />
              {user ? (
                <>
                  <Link href="/my-passes" className="block rounded-2xl px-4 py-3.5 text-lg font-medium">My passes</Link>
                  <Link href="/committee" className="block rounded-2xl px-4 py-3.5 text-lg font-medium">Committee</Link>
                  {user.role === "admin" && <Link href="/admin" className="block rounded-2xl px-4 py-3.5 text-lg font-medium">Admin</Link>}
                  <Link href="/profile" className="block rounded-2xl px-4 py-3.5 text-lg font-medium">Profile</Link>
                  <button onClick={() => { logout(); router.push("/"); }} className="block w-full rounded-2xl px-4 py-3.5 text-left text-lg font-medium text-mute">Sign out</button>
                </>
              ) : (
                <div className="flex gap-2 p-1"><Button href="/login" variant="outline" className="flex-1">Sign in</Button><Button href="/signup" className="flex-1">Join free</Button></div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </header>
      <SearchPalette open={search} onClose={() => setSearch(false)} />
    </>
  );
}

function Item({ href, icon, children }: { href: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <Link href={href} role="menuitem" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-700 hover:bg-black/5">{icon} {children}</Link>;
}
