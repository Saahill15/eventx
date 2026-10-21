export type Role = "user" | "organizer" | "admin";

export interface User {
  id: number;
  name: string;
  email: string | null;
  role: Role;
  interests_set: boolean;
  created_at: string;
}

export interface College {
  id: number;
  name: string;
  area: string | null;
  emoji: string | null;
  website: string | null;
  event_count: number;
}

export interface Fest {
  id: number;
  slug: string;
  name: string;
  tagline: string | null;
  banner_url: string | null;
  logo_url: string | null;
  college_id: number | null;
  status: "draft" | "live";
  event_count: number;
  created_at: string;
}

export interface FestEvent {
  id: number;
  event_type: "fest" | "city";
  title: string;
  description: string | null;
  location: string | null;
  date: string; // local date-time without timezone, e.g. 2026-12-05T18:00:00
  time: string | null;
  image_url: string | null;
  category: string | null;
  price: number;
  is_free: boolean;
  status: "pending" | "approved" | "rejected";
  college_id: number | null;
  college_name: string | null;
  fest_id: number | null;
  fest_slug: string | null;
  fest_name: string | null;
  requires_registration: boolean;
  is_paid: boolean;
  registration_limit: number | null;
  approval_mode: "auto" | "manual";
}

export interface FestPass {
  id: number;
  fest_id: number;
  fest_slug: string | null;
  fest_name: string | null;
  status: string;
  qr_code: string;
  checked_in: boolean;
  created_at: string;
}

export interface Registration {
  id: number;
  fest_pass_id: number;
  event_id: number;
  approval_status: "pending" | "approved" | "rejected";
  payment_status: "unpaid" | "paid";
  created_at: string;
}

export interface CityPass {
  id: number;
  pass_code: string;
  event_id: number;
  payment_status: string;
  created_at: string;
}

export interface AuthResult {
  access_token: string;
  role: Role;
  interests_set: boolean;
}
