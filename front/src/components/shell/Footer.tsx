import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-28 overflow-hidden bg-wash">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 pb-10 pt-16 sm:grid-cols-[1.5fr_1fr_1fr_1fr] sm:px-8">
        <p className="max-w-xs text-lg font-semibold leading-snug tracking-tight">Every college fest in one place. Find what is on, register in seconds, walk in with a QR pass.</p>
        <FooterCol title="Explore" links={[["Discover", "/"], ["College fests", "/fests"], ["All events", "/events"]]} />
        <FooterCol title="Account" links={[["My passes", "/my-passes"], ["Sign in", "/login"], ["Join free", "/signup"]]} />
        <FooterCol title="Committees" links={[["Dashboard", "/committee"], ["Request access", "/profile"]]} />
      </div>
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <Image src="/logo.png" alt="" width={1166} height={285} aria-hidden className="mx-auto -mb-2 w-full max-w-5xl opacity-90" />
      </div>
      <p className="py-5 text-center text-xs text-mute">© {new Date().getFullYear()} HiveOut. Free for students and colleges.</p>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <p className="mb-3 text-sm font-bold">{title}</p>
      <ul className="space-y-2 text-sm text-mute">{links.map(([l, h]) => <li key={l}><Link href={h} className="transition hover:text-ink">{l}</Link></li>)}</ul>
    </div>
  );
}
