"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LayoutDashboard, LogOut, Menu, Ticket, User as UserIcon, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "./ui/Button";

const LINKS = [
  { href: "/fests", label: "College fests" },
  { href: "/events", label: "Events" },
];

export function Navbar() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setOpen(false); setMenu(false); }, [pathname]);
  useEffect(() => {
    const onClick = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/") || (href === "/fests" && pathname.startsWith("/fest/"));
  const initial = user?.name?.trim().charAt(0).toUpperCase() ?? "?";

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-3 pt-3 sm:px-6">
      <nav className="glass-strong mx-auto flex h-14 max-w-6xl items-center justify-between rounded-full pl-5 pr-2 sm:h-16" aria-label="Main">
        <Link href="/" aria-label="HiveOut home" className="flex shrink-0 items-center">
          <Image src="/logo.png" alt="HiveOut" width={116} height={28} priority className="h-6 w-auto max-w-none sm:h-7" />
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={`rounded-full px-4 py-2 text-sm font-medium transition ${isActive(l.href) ? "bg-black/5 text-ink" : "text-neutral-600 hover:bg-black/5"}`}>
              {l.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {loading ? (
            <div className="h-10 w-24 rounded-full" />
          ) : user ? (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenu((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={menu}
                className="flex h-10 items-center gap-2 rounded-full bg-black/5 pl-1 pr-3 text-sm font-semibold transition hover:bg-black/10"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-hive text-ink">{initial}</span>
                <span className="hidden max-w-[8rem] truncate sm:block">{user.name.split(" ")[0]}</span>
              </button>
              {menu && (
                <div role="menu" className="glass-strong absolute right-0 mt-2 w-56 overflow-hidden rounded-2xl p-1.5">
                  <MenuLink href="/my-passes" icon={<Ticket className="h-4 w-4" />}>My passes</MenuLink>
                  <MenuLink href="/committee" icon={<LayoutDashboard className="h-4 w-4" />}>Committee dashboard</MenuLink>
                  <MenuLink href="/profile" icon={<UserIcon className="h-4 w-4" />}>Profile</MenuLink>
                  <button
                    role="menuitem"
                    onClick={() => { logout(); router.push("/"); }}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-700 hover:bg-black/5"
                  >
                    <LogOut className="h-4 w-4" /> Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Link href="/login" className="hidden rounded-full px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-black/5 sm:block">Sign in</Link>
              <Button href="/signup" size="sm" className="whitespace-nowrap">Get started</Button>
            </>
          )}
          <button onClick={() => setOpen((v) => !v)} className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-black/5 md:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      {open && (
        <div className="glass-strong mx-auto mt-2 max-w-6xl rounded-3xl p-2 md:hidden">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="block rounded-2xl px-4 py-3 font-medium hover:bg-black/5">{l.label}</Link>
          ))}
          {!user && <Link href="/login" className="block rounded-2xl px-4 py-3 font-medium hover:bg-black/5">Sign in</Link>}
        </div>
      )}
    </header>
  );
}

function MenuLink({ href, icon, children }: { href: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link href={href} role="menuitem" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-700 hover:bg-black/5">
      {icon} {children}
    </Link>
  );
}
