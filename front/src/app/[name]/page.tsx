import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { resolveShortLink } from "@/lib/api";

export const metadata: Metadata = { robots: { index: false } };

/** hiveout.in/some-name: if an organiser holds that name for a fest that is live, go to the fest. Anything else is not found. */
export default async function ShortLinkPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const path = await resolveShortLink(name);
  if (!path) notFound();
  redirect(path);
}
