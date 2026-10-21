# HiveOut user flow (college fests first)

## Goal
Give college fest committees one free tool that replaces their Google Sheets: schedule, registrations, entry. Students must create an account (Google sign-in) to register, which builds the user base. City events come later, once there are users.

Status key: **Done** = works today, **Partial** = exists but incomplete, **Missing** = not built.

## 1. Committee flow (the customer)

| Step | What happens | Status |
|---|---|---|
| 1 | College is onboarded; a fest is created with an owner | Partial: fests and owners exist, but only an admin can set them up, no self-serve onboarding |
| 2 | Owner invites core members and volunteers, creates departments | Partial: roles exist in the API, no screen |
| 3 | Add events: date, venue, capacity, team size, price, auto or manual approval | Done, plus cancel and restore an event. Team size is not built |
| 4 | Live registrations table, approve or reject, export CSV | Done |
| 5 | Announcements and schedule changes to registered students | Missing |
| 6 | Gate and event check-in by scanning pass QR codes | Backend done (look up a pass by QR, check in at the gate, check in at an event, undo; volunteers can scan). No scanner screen yet |
| 7 | After the fest: attendance and registration numbers | Backend done (`GET /api/fests/{slug}/manage/stats`, attendance column in the CSV). No screen yet |

## 2. Student flow

| Step | What happens | Status |
|---|---|---|
| 1 | Opens a fest from a poster QR code or shared link, browses without logging in | Done |
| 2 | Signs in with Google (name, email); adds college and year | Email and password work, and the profile now stores college, year and phone and allows changing the password. Google sign-in and password reset are missing |
| 3 | Gets the free fest entry pass | Done |
| 4 | Registers for events; team events need a team and invites | Single registration and cancelling a registration are Done; teams and waitlists are missing |
| 5 | Pays for paid events | Missing: paid events are marked paid without charging |
| 6 | Sees pass QR and registrations in My Passes | Done |
| 7 | Gets reminders and schedule updates | Missing |
| 8 | Shows the QR at the gate | Depends on the scanner (committee step 6) |

## 3. Gate volunteer flow

Open the scanner on a phone, scan a pass, see valid / already used / blocked immediately. Must work on weak mobile data. Status: backend done (QR lookup, check-in, undo); no scanner screen yet.

## Build order

1. **Google sign-in** (students). Needs a Google Cloud OAuth client ID, created by the project owner.
2. **Committee dashboard:** fest setup, team invites, event create/edit with registration settings, registrations table with CSV export.
3. **Gate scanner** (mobile web, works on poor signal).
4. **Team registration.**
5. **Real payments** (Razorpay) before pitching colleges that sell paid passes.
6. **Announcements and reminders** (email first).
7. **Self-serve college onboarding** and a pilot-ready landing page aimed at committees, not students.

## Not now
City events, recommendations by interest, native apps.

## Open items
- No pilot college or fest date yet. Finding one is the first real task and sets the deadline for the list above.
- Student data needs a privacy policy and a short agreement with each college before launch.

## Accounts, roles and student verification

- A new account is a normal member. There are two roles above that, and neither can be requested: **organiser** and **admin**. An admin makes someone an organiser from the admin panel (People).
- **Student** is not a role. It is a verification a member can add, valid for one year. After a year they verify again (allowed in the last 30 days before it ends).
- Two ways to verify:
  1. **College email code.** The student enters a college email. If its domain matches a college's list (set by an admin) or ends in `.ac.in`, `.edu.in` or `.edu`, a 6-digit code is emailed (15 minutes, 5 tries). One college email can verify one account.
  2. **Upload a document** (ID card, fee receipt, enrollment form or other; JPEG, PNG or PDF up to 5 MB). An admin reviews it and approves or rejects with a reason. The file is deleted as soon as a decision is made.
- Verification matters in two places: events a committee marks **students only**, and **student pricing** (a lower price for verified students, recorded as the amount due on each registration). Everything else stays open to every member.
- Backend is done (`/api/users/me/student/*`, `/api/admin/student-verifications/*`, `/api/admin/users`). Screens are not built yet. Email sending needs `BREVO_API_KEY` and `MAIL_FROM_EMAIL`; without them the email option reports that it is not set up and students use the document upload.
