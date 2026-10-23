import { getFestBySlug } from "@/lib/api";
import { ogCard, ogSize } from "@/lib/og";

export const size = ogSize;
export const contentType = "image/png";
export const alt = "HiveOut fest";

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const f = await getFestBySlug(slug);
  if (!f) return ogCard({ eyebrow: "HiveOut", title: "Every college fest in one place" });
  return ogCard({ eyebrow: "College fest", title: f.name, line1: f.tagline ?? undefined, line2: `${f.event_count} event${f.event_count === 1 ? "" : "s"} on HiveOut` });
}
