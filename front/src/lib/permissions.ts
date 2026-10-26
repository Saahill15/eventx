import type { User } from "@/lib/types";

/** Admins always can. An organiser can only if an admin switched fest hosting on for their account. */
export const canHostFests = (user: User | null | undefined) => user?.role === "admin" || (user?.role === "organizer" && user.can_host_fests);

/** Admins always can. An organiser can only if an admin switched city events on for their account. */
export const canHostCityEvents = (user: User | null | undefined) => user?.role === "admin" || (user?.role === "organizer" && user.can_host_city_events);
