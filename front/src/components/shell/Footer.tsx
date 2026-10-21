import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="mx-auto mt-24 max-w-7xl px-4 pb-6 sm:px-6">
      <div className="card px-8 py-12 sm:px-12">
        <div className="grid gap-10 sm:grid-cols-[1.6fr_1fr_1fr_1fr]">
          <div>
            <Image src="/logo.png" alt="HiveOut" width={116} height={28} className="h-6 w-auto" />
            <p className="mt-4 max-w-xs leading-relaxed text-mute">Every college fest in one place. Find what is on, register in seconds, walk in with a QR pass.</p>
          </div>
          <FooterCol title="Explore" links={[["Home", "/"], ["College fests", "/fests"], ["All events", "/events"]]} />
          <FooterCol title="Account" links={[["My passes", "/my-passes"], ["Sign in", "/login"], ["Join free", "/signup"]]} />
          <FooterCol title="Committees" links={[["Dashboard", "/committee"], ["Request access", "/profile"]]} />
        </div>
        <div className="mt-10 flex flex-col justify-between gap-2 border-t border-black/5 pt-6 text-sm text-mute sm:flex-row">
          <p>© {new Date().getFullYear()} HiveOut. Free for students and colleges.</p>
          <p>Made for fest season.</p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <p className="mb-3 font-semibold">{title}</p>
      <ul className="space-y-2.5 text-mute">{links.map(([l, h]) => <li key={l}><Link href={h} className="transition hover:text-brand">{l}</Link></li>)}</ul>
    </div>
  );
}
