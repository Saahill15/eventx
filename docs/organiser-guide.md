# Organiser tools: how they work

This is the working logic for committees. It matches what the backend does today.

## 1. From the first meeting to an organiser account

1. HiveOut meets the college in person. An admin adds (or edits) the college and fills in its **partnership record**, visible only to admins: status (`prospect` or `partner`), faculty coordinator name, phone and email, the date of the meeting, notes, and the college's email domains.
2. Only **partner** colleges can have fests.
3. An admin makes a member an **organiser** from the admin panel (People) and picks the college or colleges they may list fests for. There is no "request organiser access". Demoting someone clears their colleges, and an organiser who owns a fest must hand it over first.

## 2. Listing a fest

Starting a fest needs only a **name**. The college is chosen for you when the organiser has just one, and the web address is built from the name (it can be edited, and cannot change afterwards). **Dates are optional** at this point, since many colleges have not fixed them. The fest begins as a **draft**, visible only to the committee, and the person who started it becomes the **director** (owner). The committee contact starts as the director's own name and email, so they only need to add a phone number.

After creating it, the director lands on a **"Get your fest ready" checklist** with a progress bar: dates, banner, description, campus address, contact, first event, and an optional step to invite the committee. Each step has a button that opens the right tab, and everything saves as they go.

To submit it for review these must all be filled in:

| Detail | Notes |
|---|---|
| Name, description | The tagline is optional |
| Start and end date | End cannot be before start. Not final yet? See **Dates coming soon** below |
| Campus address | The map link is optional: a Google Maps link is built from the address when none is given |
| Banner image | Uploaded (JPEG, PNG or WebP up to 3 MB) or a link |
| Committee contact name, email, phone | Private: only the committee and admins see them |
| At least one event | Each with the event details below, dated inside the fest's start and end dates (not needed while dates are coming soon) |

Optional: logo, Instagram and website links, faculty coordinator for this fest (otherwise the college's coordinator on file), and **extra sections** (up to 10 blocks of title plus text, such as Rules, Prizes, Accommodation).

### Dates coming soon

If the committee has not fixed its dates, it can choose **"Not final yet"** on the checklist, or tick "The dates are not final yet" under Fest details. The fest then needs **no dates and no events** to be sent for review, and once live it is listed as **"Dates coming soon"** on its page, its card and its share image. Entry passes still work.

Events need dates, so a fest in this state cannot take events (or a CSV import) until its dates are set. Setting dates switches it off again. A fest that already has events cannot be switched to "dates coming soon".

Submitting lists anything still missing. While a fest is **in review** it is frozen so the admin reviews exactly what was submitted; the organiser can **withdraw** it to edit.

## 3. Review

The admin sees the fest, its events, the organisers, and the college's partnership record side by side, and can:

- **Approve**: the director can now make the fest live. A note is optional.
- **Request changes**: sends it back. The admin can **flag specific parts** of the fest (name, tagline, description, dates, banner, campus address, links, contact, events) with a short note on each, and/or write a general note. The organiser sees a feedback card on the Overview with a "Fix this" button for each flagged part, the note appears on the matching checklist step and on the matching box under Fest details, and the flags clear when the fest is submitted again.
- **Reject**: sends it back with a reason, and optionally flagged fields. The organiser may fix and submit again.

A fest can only go **live** once approved, and the director (or an admin) switches it live or offline.

## 4. After approval

- Dates, descriptions, banner, links and extra sections can be changed freely, even while live.
- Changing the fest's **name or college** sends it back to review and takes it offline until approved again.
- The team: the director and core members add people by email as core or volunteer. Volunteers can work the gate but cannot manage anything.
- Events can be added, edited and removed at any time with no further review.

## 5. Events

A fest event needs: title, date, **start time, end time, venue, description**. Optional: category, cover image (a designed placeholder is shown if none), price and **student price**, seat limit, automatic or manual approval, **students only**, extra sections, and custom registration questions.

**Templates and defaults.** A new event can start from a template (Competition, Team competition, Workshop, Talk or panel, Concert or show, Exhibition or stalls) that sets registration, team size, seat limit, category and usual times; the committee writes the title and details. A new event starts on the day of the last one added (or the fest's first day), the end time follows the start time until it is typed by hand, and venues already used in the fest are suggested. **Duplicate** copies an existing event, with its questions, into a new one.

Removing an event: with nobody registered it is **deleted**. With registrations the delete is refused; **cancel** it instead. Cancelling keeps it listed as cancelled, closes registration, and posts an announcement emailed to everyone registered.

Once people have registered, registration settings (required, paid, students only, student price) are locked.

## 6. Custom registration questions

Per event, up to 10 questions of three types: **short text**, **choice from a list** (2 to 20 options) and **yes or no**, each required or optional. Students answer when registering; answers show on the registrations list and as extra CSV columns. Once anyone has registered, existing questions cannot be changed or removed, and new ones must be optional.

## 7. Announcements

The director or core team posts a notice, to the **whole fest** (everyone with a pass) or **one event** (everyone registered). It appears on the fest page and in each student's notifications. Tick "email" to also send it through Brevo. Fest must be live; limit 10 per fest per day. Email sending runs after the post, and the announcement records how many emails went out or failed.

## 8. Running the committee

These tools are for the committee itself. They sit in the fest's tabs and are available as soon as the fest exists, before review.

**Committee structure (Committee tab).** Access stays three simple levels (festival director, core team, volunteer), because that decides who can manage what. On top of it every fest uses its own words:
- **Teams:** the parts of the committee (Sponsorship, PR, Logistics and so on). One click adds the usual nine; add, rename or delete your own. Up to 30 per fest. Deleting a team keeps its people and tasks.
- **Titles and reporting lines:** "Edit place" on each person sets a title in the fest's own words (for example "Sponsorship Head"), a team, and who they report to. The chart that results shows on the same tab. A chart cannot loop (nobody can end up reporting to someone who reports to them), the lead must be on the same committee, and only the director or an admin can move the director.
- Removing someone clears the lead of the people who reported to them, unassigns their tasks and takes them off meeting invitations.

**Tasks (Tasks tab).** Who does what by when: a title, an owner, a team, a due date and details, on a board of To do, In progress and Done. The director and core team add, edit, assign and delete; the person a task is assigned to can move it along; volunteers see their own tasks above the check-in screen. Filters: all, mine, overdue, by team. A task is overdue once its due date has passed and it is not done. Up to 500 per fest.

**Meetings (Meetings tab).** Schedule a meeting with a date, time, place and agenda, and choose who is invited (everyone by default). Invitees get a notification, and again if the time or place changes, or when they are added later; cancelling a future meeting tells them too. After the meeting the core team records who came, writes the minutes, and adds **action items**, which are ordinary tasks tied to the meeting and show on the task board with "From the meeting...". Cancelling a meeting keeps its action items. Up to 300 per fest.

**Schedule (Schedule tab).** Every event by day and venue. Two events **clash** when they are at the same venue on the same day and their times overlap; back-to-back is fine, venue names are compared ignoring capitalisation and spacing, an event with no end time is assumed to take an hour, and cancelled events never clash. Clashes are marked in red and listed at the top. While an event is being created or edited the form warns about a clash (without blocking the save). Events with no time or venue are listed as "not placed yet".

## 9. Day of the fest

Volunteers and the committee scan pass QR codes: look up a pass, check in at the gate, check in at an event, undo a wrong scan (director and core only). Stats show passes issued and used, and per-event registered, waiting and attended.

## Not built yet

Waitlists, payments and refunds, transferring a fest to a new director, ticket tiers and promo codes, certificates, bulk import of events from a spreadsheet. Screens for most of the above are the next step.
