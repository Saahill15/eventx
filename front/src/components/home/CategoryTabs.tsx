import Link from "next/link";
import { CalendarDays, Sparkles, Tent, Ticket, Gift } from "lucide-react";

const TABS = [
  { label: "For you", href: "/", icon: Sparkles, active: true },
  { label: "Fests", href: "/fests", icon: Tent },
  { label: "Events", href: "/events", icon: Ticket },
  { label: "This week", href: "/events", icon: CalendarDays },
  { label: "Free", href: "/events?free=1", icon: Gift },
];

/** Icon tabs under the search bar. The selected one is tinted; the rest stay quiet. */
export function CategoryTabs() {
  return (
    <nav aria-label="Browse" className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:justify-center sm:px-0">
      {TABS.map(({ label, href, icon: Icon, active }) => (
        <Link key={label} href={href} aria-current={active ? "page" : undefined} className={`flex shrink-0 flex-col items-center gap-1.5 rounded-2xl px-5 py-3 text-sm font-semibold transition ${active ? "bg-tint text-tint-ink ring-1 ring-brand/40" : "text-ink hover:bg-wash"}`}>
          <Icon className={`h-6 w-6 ${active ? "text-brand" : "text-ink"}`} strokeWidth={1.6} />
          {label}
        </Link>
      ))}
    </nav>
  );
}
