import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-24 border-t border-black/5">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 sm:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <Image src="/logo.png" alt="HiveOut" width={116} height={28} className="h-6 w-auto" />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-neutral-500">
            Every college fest in one place. Find what is on, register in seconds, and walk in with a QR pass.
          </p>
        </div>
        <div>
          <p className="mb-3 text-sm font-semibold">Explore</p>
          <ul className="space-y-2 text-sm text-neutral-500">
            <li><Link href="/fests" className="hover:text-ink">College fests</Link></li>
            <li><Link href="/events" className="hover:text-ink">All events</Link></li>
            <li><Link href="/my-passes" className="hover:text-ink">My passes</Link></li>
          </ul>
        </div>
        <div>
          <p className="mb-3 text-sm font-semibold">For committees</p>
          <ul className="space-y-2 text-sm text-neutral-500">
            <li><Link href="/committee" className="hover:text-ink">Committee dashboard</Link></li>
            <li><Link href="/signup" className="hover:text-ink">Create an account</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-black/5 py-6 text-center text-xs text-neutral-400">© {new Date().getFullYear()} HiveOut</div>
    </footer>
  );
}
