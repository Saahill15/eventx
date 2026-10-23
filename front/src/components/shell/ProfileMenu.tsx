"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

/**
 * The profile pill and its menu: a teal circle with the first initial, the first name and a small arrow; opens a menu with the
 * person's name, email and role, then the links it is given (View the site and Manage users for an admin) and Log out. Styled by the .pm classes in globals.css.
 */
export function ProfileMenu({ name, email, role = "Admin", links = [{ href: "/", label: "View the site" }, { href: "/admin/users", label: "Manage users" }] }: { name: string; email: string; role?: string; links?: { href: string; label: string }[] }) {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);

  // Close on a click anywhere else, or on Escape
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !(e.target as HTMLElement).closest(".pm") && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("click", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("click", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  // Log out: logout() sends POST /api/auth/logout with this person's token and forgets it here. Then the home page with a full
  // reload (a refresh too), which also gets ahead of the admin pages' own "please sign in" redirect.
  function signOut() {
    setOpen(false);
    logout();
    window.location.assign("/");
  }

  return (
    <div className="pm">
      <button type="button" className="pm-btn" aria-expanded={open} aria-haspopup="menu" aria-label="Account menu" onClick={() => setOpen((v) => !v)}>
        <span className="pm-av">{name.charAt(0).toUpperCase()}</span>
        <b>{name.split(" ")[0]}</b>
        <i aria-hidden="true">▾</i>
      </button>
      {open ? (
        <div className="pm-menu" role="menu">
          <div className="pm-who">
            <strong>{name}</strong>
            <small>{email}</small>
            <em>{role}</em>
          </div>
          {links.map((l) => <Link key={l.href + l.label} href={l.href} role="menuitem" onClick={() => setOpen(false)}>{l.label}</Link>)}
          <button type="button" role="menuitem" onClick={signOut}>Log out</button>
        </div>
      ) : null}
    </div>
  );
}
