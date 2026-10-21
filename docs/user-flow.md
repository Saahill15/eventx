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
