# Organiser tools: how they work

This is the working logic for committees. It matches what the backend does today.

## 1. From the first meeting to an organiser account

1. HiveOut meets the college in person. An admin adds (or edits) the college and fills in its **partnership record**, visible only to admins: status (`prospect` or `partner`), faculty coordinator name, phone and email, the date of the meeting, notes, and the college's email domains.
2. Only **partner** colleges can have fests.
3. An admin makes a member an **organiser** from the admin panel (People) and picks the college or colleges they may list fests for. There is no "request organiser access". Demoting someone clears their colleges, and an organiser who owns a fest must hand it over first.

### The first sign-in: a short tour

When an admin makes someone an organiser, their next page load shows "You are now an organiser" with two choices: **Take a 1-minute tour** or **Skip the tour**. The tour dims the page and lights up the Fests list, the + that starts a fest, and the account menu, then explains the four steps to going live; its last step has a "Create my first fest" button. It can be skipped at any point (the Skip button is always on screen, and Esc skips) and taken again from the account menu ("Take the tour again"). The first time an organiser opens one of their fests, a second short tour walks through that page's tabs; it runs once per browser and can be replayed with "Take a tour of this page".

## 2. Listing a fest

Starting a fest needs only a **name**. The college is chosen for you when the organiser has just one, and the web address is built from the name (it can be edited, and cannot change afterwards). **Dates are optional** at this point, since many colleges have not fixed them. Pick the first and last day and the page says "Your fest runs for 3 days" on the spot: **nobody types in the number of days**, it is worked out from the two dates (at most 15 days) and shown, read-only, in Fest details and on the Overview. The fest begins as a **draft**, visible only to the committee, and the person who started it becomes the **director** (owner). The committee contact starts as the director's own name and email, so they only need to add a phone number.

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

The event form asks in this order:

1. **What is it?** A template (optional), title, category, description.
2. **When?** The fest's days are listed ("Day 1 · Thu, 10 Dec"). Pick the day it starts and **how many days it runs** (up to the end of the fest), then its daily start and end time. An event over several days repeats at the same times each day, and shows on each of those days in the schedule ("day 2 of 3"). Without fest dates the form says to set them first.
3. **Where?** The venue; a clash warning appears if another event has the same venue at the same time on any of its days.
4. **How do people take part?** *Just turn up* (no registration) or *Register first*. If they register: *solo* or *team* (with the smallest and largest team), a seat limit (teams or people), when registration opens (*Open now*, *On a date*, or *Not decided yet*; see below), when it closes (optional; it cannot be after the event's last day, and people cannot register after it), and whether it is confirmed instantly or the committee approves each one. Also who can take part (anyone, or verified students only) and the entry fee (free, or paid with an optional student price).
5. **Who runs it?** A coordinator's name and phone, shown on the event page.
6. **Rules, prizes and a picture.** Extra sections and a cover image.
7. **Questions** for people who register, when registration is on.

At review, a multi-day event must fit inside the fest's dates. Its details can be changed later; registration settings lock once people have registered.

**Templates and defaults.** A new event can start from a template (Competition, Team competition, Workshop, Talk or panel, Concert or show, Exhibition or stalls). A template visibly sets how people join (register or just turn up), solo or team and the team size, the seat limit, the category, the usual start and end time, and adds empty headings for the extra information (for example Rules, Prizes and Judging), and the form says what it set. The committee writes the title and details and can change anything. A new event starts on the day of the last one added (or the fest's first day), the end time follows the start time until it is typed by hand, and venues already used in the fest are suggested. **Duplicate** copies an existing event, with its questions, into a new one.

Removing an event: with nobody registered it is **deleted**. With registrations the delete is refused; **cancel** it instead. Cancelling keeps it listed as cancelled, closes registration, and posts an announcement emailed to everyone registered.

Once people have registered, registration settings (required, paid, students only, student price) are locked.

### When registration opens

Every event that needs registration has three ways to start:

- **Open now**: students can register straight away.
- **On a date**: it opens by itself on the day you pick (never after it closes, or after the event's last day). Until then the public sees "Registration opens on 27 November 2026".
- **Not decided yet**: the public sees "Registration is not open yet". Nobody can register until you open it.

On the Events tab each event shows its state, with **Open registrations now** or **Close registrations** next to it. Closing by hand stops new registrations at once and **Reopen registrations** starts it again (unless the closing date has already passed; then change that date first). People already registered keep their place. The same rules apply to team events (starting or joining a team).

An event made without choosing (for example by CSV import) opens at once, as it always did.

## 6. Custom registration questions

Per event, up to 10 questions of three types: **short text**, **choice from a list** (2 to 20 options) and **yes or no**, each required or optional. Students answer when registering; answers show on the registrations list and as extra CSV columns. Once anyone has registered, existing questions cannot be changed or removed, and new ones must be optional.

### Pictures

The banner, the logo and an event's cover each say what they should look like before anything is chosen: the **banner** 1920 × 820 px (wide), the **logo** 512 × 512 px (square), an **event cover** 1280 × 800 px (landscape). After choosing a picture the organiser **crops** it to that shape (drag to move, slider to zoom). Big photos are fine, up to 15 MB: the picture is cut down to size and compressed before it is sent, so what is stored is always under the server's 3 MB limit. A picture smaller than the minimum (for example under 1200 px wide for a banner) gets a warning that it may look blurry. JPEG, PNG and WebP are accepted; a PNG logo keeps its transparency.

### The Overview tab

Opens with the fest at a glance: banner, name, status, dates with the number of days, college, and tiles for events, entry passes, registrations waiting for approval, committee size, open and overdue tasks, the next meeting, and (if switched on) visiting colleges waiting. Each tile opens the tab where you act on it. Below it sit the review progress and, while the fest is a draft, the "Get your fest ready" checklist.

## 7. Announcements

The director or core team posts a notice, to the **whole fest** (everyone with a pass) or **one event** (everyone registered). It appears on the fest page and in each student's notifications. Tick "email" to also send it through Brevo. Fest must be live; limit 10 per fest per day. Email sending runs after the post, and the announcement records how many emails went out or failed.

## 8. Running the committee

These tools are for the committee itself. They sit in the fest's tabs and are available as soon as the fest exists, before review.

**Committee structure (Committee tab).** Two separate ideas, kept apart on purpose:
- **Access level** (festival director, core team, volunteer) decides what someone can manage on HiveOut.
- **Position** says where they sit: an optional title in the fest's own words (Chairperson, Vice Chairperson, General Secretary, Treasurer, Sponsorship Head... suggestions only), and inside a team: head, co-head or member.

The **Core team is not a team in the list**. It is the access level of the people who run the fest: the director, the office-bearers (Chairperson's deputy, Treasurer and so on, who lead no team) and, usually, the head of every team. A head may or may not have Core access, and the form offers it by default.

- **One place to add people.** "Add someone to the committee" asks for their email, an optional title, their team and position, and their access level. Choosing **head** sets access to Core team by default; co-heads and members start as volunteers (the director can raise anyone). Only the director can give Core access; for anyone else a head joins as a volunteer and leads the team from there. The invitation tells them where they will sit, and they land there when they accept.
- **Teams.** The usual nine in one click, or your own. **Edit team** sets the name, a one-line description, the **head**, up to three **co-heads**, and two permissions: give the head Core access in the same step (the director only; co-heads keep the access they have), and "the team's leaders run the team". Choosing a head moves them into the team; the earlier head stays as a plain member. Deleting a team keeps its people (as plain members) and its tasks.
- **What a team's leaders can do** (when "leaders run the team" is on, even without Core access): bring people into their team and send them out, set their titles and leads, edit the team's description, and give tasks to people in their team. They cannot rename the team, choose heads, change access, touch other teams, or delete anything. A head without Core access sees their team above the check-in screen. The core team can switch this off per team.
- **The chart fills itself in.** A head reports to the director, everyone else in a team reports to its head, and office-bearers report to the director. Anything already set by hand is kept, and the chart never loops. "Edit place" on any person changes the title, team, position, lead and (for the director) access level.
- Removing someone clears the lead of the people who reported to them, unassigns their tasks and takes them off meeting invitations.

**Sponsors (Sponsors tab).** The director and core team list the fest's sponsors and partners, and they get their own section on the public fest page with logos. Each sponsor has a name, a kind (Title Sponsor, Powered by, Associate Sponsors, Gift, Food, Media, Knowledge, Hospitality or Travel Partner, or your own wording and size), a logo (3:2, cropped on upload; 600 × 400 px; PNG keeps transparency), an optional website the logo links to, and an optional line about them (shown for title and "powered by" sponsors). Bigger tiers are shown larger and first; move a sponsor up or down inside its tier. A sponsor can be added before its logo arrives (its name is shown instead). Up to 40 per fest. Drafts are private to the committee; once the fest is live the public page shows them (it can take up to 30 seconds to refresh).

**Tasks (Tasks tab).** Who does what by when: a title, an owner, a team, a due date and details, on a board of To do, In progress and Done. The director and core team add, edit, assign and delete; the person a task is assigned to can move it along; volunteers see their own tasks above the check-in screen. Filters: all, mine, overdue, by team. A task is overdue once its due date has passed and it is not done. Up to 500 per fest.

**Meetings (Meetings tab).** Schedule a meeting with a date, time, place and agenda, and choose who is invited (everyone by default). Invitees get a notification, and again if the time or place changes, or when they are added later; cancelling a future meeting tells them too. After the meeting the core team records who came, writes the minutes, and adds **action items**, which are ordinary tasks tied to the meeting and show on the task board with "From the meeting...". Cancelling a meeting keeps its action items. Up to 300 per fest.

**Schedule (Schedule tab).** Every event by day and venue. Two events **clash** when they are at the same venue on the same day and their times overlap; back-to-back is fine, venue names are compared ignoring capitalisation and spacing, an event with no end time is assumed to take an hour, and cancelled events never clash. Clashes are marked in red and listed at the top. While an event is being created or edited the form warns about a clash (without blocking the save). Events with no time or venue are listed as "not placed yet".

## 9. Day of the fest

Volunteers and the committee scan pass QR codes: look up a pass, check in at the gate, check in at an event, undo a wrong scan (director and core only). Stats show passes issued and used, and per-event registered, waiting and attended.

## 10. Visiting colleges (contingents)

Many fests host other colleges. HiveOut lets each fest decide whether to, what to call them, and the rules. It is **off by default**; the committee turns it on in the **Visiting colleges** tab. Nothing about names or limits is fixed:

| Setting | What it does |
|---|---|
| The words | What the fest calls a visiting college's team ("contingent", "delegation"...), its leader and the leader's helper. These words appear everywhere a college sees them |
| Helpers | How many assistants a leader may add (0 to 10) |
| Team size | The smallest and largest roster; colleges see a warning outside it, and cannot add past the largest |
| Registration window | Optional open and close dates |
| Approval | Either the committee approves each college, or colleges are approved the moment they register |
| Several per college | Whether a college may send more than one team |
| Roster lock | Whether colleges can still change their list of people once registration closes (the committee always can) |

**For the college.** A "For other colleges" card appears on the live fest page. The visitor signs in (or signs up), registers their college, and becomes its **leader**. Registering is refused if the fest is not live, not taking colleges, or outside its window, if they already lead or help a team at this fest, or if the college already has one (unless the fest allows several; spelling and capitalisation are ignored). The leader can then:
- correct the college's name,
- add **helpers** by email (they need a HiveOut account and are told; up to the fest's limit; a helper can manage the roster and can leave, but cannot add helpers or withdraw),
- keep the **roster**: name, optional email, phone, year and notes for each person, who need no accounts,
- see the status, and the code and name the committee gives them,
- withdraw, which releases the code and name.

**For the committee.** The tab lists every college with filters (waiting, approved, not approved, withdrawn). Opening one shows its leader, helpers and roster. The committee can approve (a note is optional), decline (a reason is required, and any code and name are released), give it a **code** and a **name** (each unique in the fest, ignoring capitalisation), withdraw it, or delete it. The leader is told of every decision, and the committee is told when a college registers or withdraws.

Not built yet in this part: the games and name bidding at a leaders' meet, entering contingents into events, accommodation requests and fees.

## Not built yet

Waitlists, payments and refunds, transferring a fest to a new director, ticket tiers and promo codes, certificates, bulk import of events from a spreadsheet. Screens for most of the above are the next step.
