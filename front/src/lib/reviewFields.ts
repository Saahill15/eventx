import type { ReviewFieldKey } from "./types";

/**
 * The parts of a fest an admin can flag when sending it back. `tab` is where the committee fixes it; `card` is the box
 * on the Fest details tab that shows the note.
 */
export const REVIEW_FIELDS: { key: ReviewFieldKey; label: string; tab: "details" | "events"; card: "basics" | "pictures" | "where" | "contacts" | "events" }[] = [
  { key: "name", label: "Name", tab: "details", card: "basics" },
  { key: "tagline", label: "Tagline", tab: "details", card: "basics" },
  { key: "description", label: "Description", tab: "details", card: "basics" },
  { key: "dates", label: "Dates", tab: "details", card: "basics" },
  { key: "banner", label: "Banner image", tab: "details", card: "pictures" },
  { key: "venue", label: "Campus address", tab: "details", card: "where" },
  { key: "links", label: "Links and extra sections", tab: "details", card: "where" },
  { key: "contact", label: "Contact details", tab: "details", card: "contacts" },
  { key: "events", label: "Events", tab: "events", card: "events" },
];

export const reviewFieldLabel = (key: string) => REVIEW_FIELDS.find((f) => f.key === key)?.label ?? key;
