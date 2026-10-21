import { Music, Cpu, Trophy, Palette, Gamepad2, Shirt, BookOpen, Briefcase, GraduationCap, Mic, Sparkles, type LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  Music, Technical: Cpu, Technology: Cpu, Sports: Trophy, Design: Palette, Gaming: Gamepad2,
  Fashion: Shirt, Literary: BookOpen, Business: Briefcase, Finance: Briefcase, Education: GraduationCap,
  Cultural: Mic,
};

const TINTS = [
  "from-hive-100 via-orange-50 to-white",
  "from-orange-100 via-amber-50 to-white",
  "from-rose-100 via-pink-50 to-white",
  "from-violet-100 via-indigo-50 to-white",
  "from-sky-100 via-cyan-50 to-white",
];

/** Cover image, or a branded gradient with the category icon when an event has no picture. */
export function EventArt({ src, alt, category, seed = 0, className = "" }: { src?: string | null; alt: string; category?: string | null; seed?: number; className?: string }) {
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} loading="lazy" referrerPolicy="no-referrer" className={`h-full w-full object-cover ${className}`} />;
  }
  const Icon = (category && ICONS[category]) || Sparkles;
  return (
    <div className={`flex h-full w-full items-center justify-center bg-gradient-to-br ${TINTS[seed % TINTS.length]} ${className}`} role="img" aria-label={alt}>
      <Icon className="h-10 w-10 text-hive-ink/70" strokeWidth={1.5} />
    </div>
  );
}

/** Cover for fests without a banner: honey gradient with a hexagon pattern, in the HiveOut style. */
export function FestArt({ src, alt = "" }: { src?: string | null; alt?: string }) {
  if (src) return <EventArt src={src} alt={alt} />;
  return (
    <div className="relative h-full w-full overflow-hidden bg-gradient-to-br from-hive via-amber-300 to-orange-300" role="img" aria-label={alt || "Fest cover"}>
      <svg className="absolute inset-0 h-full w-full opacity-30" aria-hidden>
        <defs>
          <pattern id="hex" width="56" height="97" patternUnits="userSpaceOnUse" patternTransform="scale(1.1)">
            <path d="M28 2 54 17v30L28 62 2 47V17z M28 64 54 79v18 M28 64 2 79v18" fill="none" stroke="#fff" strokeWidth="2" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hex)" />
      </svg>
    </div>
  );
}
