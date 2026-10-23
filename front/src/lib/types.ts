export type Role = "user" | "organizer" | "admin";

export interface User {
  id: number;
  name: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  role: Role;
  interests_set: boolean;
  college_id: number | null;
  study_year: number | null;
  is_student_verified: boolean;
  college_ids: number[];
  organizer_welcome_pending: boolean;
  has_password: boolean;
  google_linked: boolean;
  profile_complete: boolean;
  created_at: string;
}

export interface SignupInput {
  first_name: string; last_name: string; email: string; date_of_birth: string; password: string;
  accept_terms: boolean;
}

export interface Interest { id: number; name: string }

export interface College {
  id: number;
  name: string;
  area: string | null;
  emoji: string | null;
  website: string | null;
  email_domains?: string | null;
  partner_status?: "prospect" | "partner";
  event_count: number;
}

export interface AdminCollege extends College {
  coordinator_name: string | null;
  coordinator_phone: string | null;
  coordinator_email: string | null;
  partner_since: string | null;
  partner_notes: string | null;
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
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  campus_address?: string | null;
  map_url?: string | null;
  instagram_url?: string | null;
  website_url?: string | null;
  extra_sections?: ExtraSection[] | null;
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
  is_team_event: boolean;
  team_min: number | null;
  team_max: number | null;
  end_time: string | null;
  extra_sections: ExtraSection[] | null;
  students_only: boolean;
  student_price: number | null;
  cancelled: boolean;
  cancel_reason: string | null;
  reject_reason: string | null;
}

export interface ExtraSection { title: string; body: string }

export interface FestManage extends Fest {
  description: string | null; start_date: string | null; end_date: string | null; campus_address: string | null; map_url: string | null;
  instagram_url: string | null; website_url: string | null; extra_sections: ExtraSection[] | null;
  contact_name: string | null; contact_email: string | null; contact_phone: string | null;
  faculty_name: string | null; faculty_phone: string | null; faculty_email: string | null;
  review_status: ReviewStatus; review_note: string | null; submitted_at: string | null; reviewed_at: string | null;
}

export interface Question { id: number; label: string; kind: "short_text" | "choice" | "yes_no"; required: boolean; options: string[] | null; position: number }
export interface Announcement { id: number; fest_id: number; event_id: number | null; event_title: string | null; title: string; body: string; email_requested: boolean; emails_sent: number; emails_failed: number; created_at: string }
export interface GatePass { pass_id: number; user_name: string | null; user_email: string | null; status: string; checked_in: boolean; checked_in_at: string | null; registrations: { event_id: number; title: string; approval_status: string; attended: boolean }[] }

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
  team_id: number | null;
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
  expires_in?: number;
  idle_timeout_seconds?: number;
  profile_complete?: boolean;
  notice?: string | null;
}

export type FestRole = "owner" | "core" | "volunteer" | "admin";

export type ReviewStatus = "draft" | "in_review" | "changes_requested" | "approved" | "rejected";

export interface MyFest extends Fest {
  my_role: FestRole;
  review_status: ReviewStatus;
  review_note: string | null;
}

export interface FestStats {
  passes_issued: number;
  passes_checked_in: number;
  events: { id: number; title: string; date: string; cancelled: boolean; requires_registration: boolean; registration_limit: number | null; registered: number; pending: number; attended: number }[];
}

export interface ManagedEvent extends FestEvent {
  registration_count: number;
  pending_count: number;
}

export interface TeamMember { registration_id: number; name: string | null; email: string | null; is_leader: boolean; approval_status: "pending" | "approved" | "rejected"; attended: boolean }
export interface Team {
  id: number; event_id: number; name: string; code: string | null; size: number; team_min: number | null; team_max: number | null;
  complete: boolean; status: "pending" | "approved" | "rejected"; i_am_leader: boolean; members: TeamMember[];
}
export interface FestTransfer { id: number; fest_slug: string; fest_name: string; from_name: string | null; from_email: string | null; to_name: string | null; to_email: string | null; status: string; keep_previous_owner: boolean; created_at: string }
export interface ImportResult { dry_run: boolean; rows: { line: number; title: string; errors: string[] }[]; file_errors: string[]; valid: number; created: number }

export interface RegistrationDetail extends Registration {
  user_name: string | null;
  user_email: string | null;
  checked_in: boolean;
  answers: { question_id: number; label: string; answer: string }[];
  team_name: string | null;
  is_team_leader: boolean;
}

export interface Member {
  id: number;
  fest_id: number;
  user_id: number;
  role: "owner" | "core" | "volunteer";
  user_name: string | null;
  user_email: string | null;
}

export interface AdminUser {
  id: number;
  name: string;
  email: string | null;
  role: Role;
  is_active: boolean;
  college_ids: number[];
  created_at: string;
}

export interface AdminOverview {
  members: number; organizers: number; admins: number; suspended: number;
  partner_colleges: number; prospect_colleges: number;
  fests_live: number; fests_in_review: number; fests_changes_requested: number; fests_draft: number;
  events_total: number; city_events_pending: number; registrations: number; fest_passes: number;
  verifications_pending: number; verified_students: number;
}

export interface FestReview {
  fest: Fest & {
    description: string | null; start_date: string | null; end_date: string | null; campus_address: string | null; map_url: string | null;
    instagram_url: string | null; website_url: string | null;
    contact_name: string | null; contact_email: string | null; contact_phone: string | null;
    faculty_name: string | null; faculty_phone: string | null; faculty_email: string | null;
    review_status: string; review_note: string | null; submitted_at: string | null;
  };
  college: { id: number; name: string; partner_status: string; coordinator_name: string | null; coordinator_phone: string | null; coordinator_email: string | null } | null;
  events: { id: number; title: string; date: string; time: string | null; end_time: string | null; location: string | null; price: number }[];
  missing: string[];
  owners: string[];
  short_link: string | null;
}

export interface VerificationReview {
  id: number; user_id: number; user_name: string | null; user_email: string | null; method: string; status: string;
  college_id: number | null; college_name: string | null; document_type: string | null; document_name: string | null;
  has_file: boolean; created_at: string;
}

export interface AuthSession { id: string; created_at: string; last_seen_at: string; ip: string | null; user_agent: string | null; current: boolean }
