# Organiser tools: how they work

This is the working logic for committees. It matches what the backend does today.

## 1. From the first meeting to an organiser account

1. HiveOut meets the college in person. An admin adds (or edits) the college and fills in its **partnership record**, visible only to admins: status (`prospect` or `partner`), faculty coordinator name, phone and email, the date of the meeting, notes, and the college's email domains.
2. Only **partner** colleges can have fests.
3. An admin makes a member an **organiser** from the admin panel (People) and picks the college or colleges they may list fests for. There is no "request organiser access". Demoting someone clears their colleges, and an organiser who owns a fest must hand it over first.

## 2. Listing a fest

Starting a fest needs only a name, a web address (`/fest/your-fest`) and the college. It begins as a **draft**, visible only to the committee, and the person who started it becomes the **director** (owner).

To submit it for review these must all be filled in:

| Detail | Notes |
|---|---|
| Name, tagline, description | |
| Start and end date | End cannot be before start |
| Campus address and map link | Map link must be an http(s) address |
| Banner image | Uploaded (JPEG, PNG or WebP up to 3 MB) or a link |
| Committee contact name, email, phone | Private: only the committee and admins see them |
| At least one event | Each with the event details below, dated inside the fest's start and end dates |

Optional: logo, Instagram and website links, faculty coordinator for this fest (otherwise the college's coordinator on file), and **extra sections** (up to 10 blocks of title plus text, such as Rules, Prizes, Accommodation).

Submitting lists anything still missing. While a fest is **in review** it is frozen so the admin reviews exactly what was submitted; the organiser can **withdraw** it to edit.

## 3. Review

The admin sees the fest, its events, the organisers, and the college's partnership record side by side, and can:

- **Approve**: the director can now make the fest live. A note is optional.
- **Request changes**: sends it back with a note. The organiser fixes things and submits again.
- **Reject**: sends it back with a reason. The organiser may fix and submit again.

A fest can only go **live** once approved, and the director (or an admin) switches it live or offline.

## 4. After approval

- Dates, descriptions, banner, links and extra sections can be changed freely, even while live.
- Changing the fest's **name or college** sends it back to review and takes it offline until approved again.
- The team: the director and core members add people by email as core or volunteer. Volunteers can work the gate but cannot manage anything.
- Events can be added, edited and removed at any time with no further review.

## 5. Events

A fest event needs: title, date, **start time, end time, venue, description**. Optional: category, cover image (a designed placeholder is shown if none), price and **student price**, seat limit, automatic or manual approval, **students only**, extra sections, and custom registration questions.

Removing an event: with nobody registered it is **deleted**. With registrations the delete is refused; **cancel** it instead. Cancelling keeps it listed as cancelled, closes registration, and posts an announcement emailed to everyone registered.

Once people have registered, registration settings (required, paid, students only, student price) are locked.

## 6. Custom registration questions

Per event, up to 10 questions of three types: **short text**, **choice from a list** (2 to 20 options) and **yes or no**, each required or optional. Students answer when registering; answers show on the registrations list and as extra CSV columns. Once anyone has registered, existing questions cannot be changed or removed, and new ones must be optional.

## 7. Announcements

The director or core team posts a notice, to the **whole fest** (everyone with a pass) or **one event** (everyone registered). It appears on the fest page and in each student's notifications. Tick "email" to also send it through Brevo. Fest must be live; limit 10 per fest per day. Email sending runs after the post, and the announcement records how many emails went out or failed.

## 8. Day of the fest

Volunteers and the committee scan pass QR codes: look up a pass, check in at the gate, check in at an event, undo a wrong scan (director and core only). Stats show passes issued and used, and per-event registered, waiting and attended.

## Not built yet

Team events, waitlists, payments and refunds, transferring a fest to a new director, ticket tiers and promo codes, certificates, bulk import of events from a spreadsheet. Screens for most of the above are the next step.
