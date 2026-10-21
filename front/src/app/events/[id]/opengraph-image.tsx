import { getEventById } from "@/lib/api";
import { formatDay, formatTime } from "@/lib/format";
import { ogCard, ogSize } from "@/lib/og";

export const size = ogSize;
export const contentType = "image/png";
export const alt = "HiveOut event";

export default async function Image({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const e = await getEventById(id);
  if (!e) return ogCard({ eyebrow: "HiveOut", title: "Every college fest in one place" });
  return ogCard({ eyebrow: e.fest_name ?? "Event", title: e.title, line1: `${formatDay(e.date)}${e.time ? ` · ${formatTime(e.time)}` : ""}`, line2: e.location ?? undefined });
}
