import type { MetadataRoute } from "next";
import { SITE_URL, getAllEvents, getLiveFests } from "@/lib/api";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [fests, events] = await Promise.all([getLiveFests(), getAllEvents()]);
  return [
    { url: SITE_URL, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/fests`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/events`, changeFrequency: "daily", priority: 0.9 },
    ...(fests ?? []).map((f) => ({ url: `${SITE_URL}/fest/${f.slug}`, changeFrequency: "daily" as const, priority: 0.8 })),
    ...(events ?? []).map((e) => ({ url: `${SITE_URL}/events/${e.id}`, changeFrequency: "daily" as const, priority: 0.7 })),
  ];
}
