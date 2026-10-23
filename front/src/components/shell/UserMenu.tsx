"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, ChevronDown, LogOut, User as UserIcon } from "lucide-react";
import { useAuth } from "@/lib/auth";

/** Top-right of a workspace: a link back to the public site and the signed-in person's menu. */
export function UserMenu({ signOutTo, links = [] }: { signOutTo: string; links?: { href: string; label: string; icon?: React.ReactNode }[] }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onEsc);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onEsc); };
  }, []);

  const item = "flex h-8 w-full items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium hover:bg-black/[0.05]";
  const initial = (user?.first_name || user?.name || "?").charAt(0).toUpperCase();
  return (
    <div className="ml-auto flex items-center gap-3">
      <Link href="/" className="flex items-center gap-1 text-[14px] font-medium text-neutral-600 hover:text-ink">View site <ArrowUpRight className="h-3.5 w-3.5" /></Link>
      <div className="relative" ref={ref}>
        <button onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open} className="flex h-8 items-center gap-2 rounded-full border border-black/[0.1] bg-white py-0.5 pl-0.5 pr-2.5 text-[13px] font-medium transition hover:bg-black/[0.03]">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--ws-accent)] text-[12px] font-semibold text-white">{initial}</span>
          {user?.first_name || user?.name?.split(" ")[0]}
          <ChevronDown className="h-3.5 w-3.5 text-mute" />
        </button>
        {open && (
          <div role="menu" className="absolute right-0 top-10 z-40 w-60 rounded-lg border border-black/[0.1] bg-white p-1 shadow-[0_12px_32px_rgba(0,0,0,0.12)]">
            <div className="px-2.5 py-2"><p className="truncate text-[13px] font-semibold">{user?.name}</p><p className="truncate text-xs text-mute">{user?.email}</p></div>
            {links.map((l) => <Link key={l.href} role="menuitem" href={l.href} onClick={() => setOpen(false)} className={item}>{l.icon}{l.label}</Link>)}
            <Link role="menuitem" href="/profile" onClick={() => setOpen(false)} className={item}><UserIcon className="h-4 w-4 shrink-0" /> Profile and security</Link>
            <button role="menuitem" onClick={() => { logout(); router.push(signOutTo); }} className={item}><LogOut className="h-4 w-4 shrink-0" /> Sign out</button>
          </div>
        )}
      </div>
    </div>
  );
}
