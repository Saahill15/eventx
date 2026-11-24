# HiveOut as an operating system for college fests: research and design

Written 25 Nov 2026. The goal: run a whole fest on HiveOut, for the home committee **and** for the committees of the colleges that visit (their contingent leaders), and keep every fest's own theme, format and flow configurable instead of hard-coded.

## How to read this

Every claim carries a tag, because the evidence is uneven:

- **[S]** found on a public page that I opened and read (linked at the end).
- **[S\*]** reported by a search-result summary of a public page that I did **not** open myself. Probably right, but less certain than [S]. Two pages I tried to open failed (a 404 and a dead address), and a summary had mislabelled one of them, which is why I do not trust summaries alone.
- **[F]** the founder's first-hand knowledge. Not found in any public source, so it needs checking against other fests.
- **[I]** my inference or design proposal. A hypothesis, not a fact.

**The main finding:** the visiting-college side of a fest (contingent leaders, contingent names, CL meets, name bidding) is almost undocumented online. The pages I could read show one CL meet with a balloon game and no points, one that mentions CLs earning "PR points", and one fest with team scoring for on-spot events. Nothing at all describes name bidding. This is an oral tradition passed between committees. That makes it a real gap for a product, and it also means we cannot design it from the internet. It has to come from talking to committees (the interview guide is at the end).

**A correction I made while writing this:** my first searches returned summaries saying a CL "can be any student", that a team "cannot register without a CL", and that a CL pays on the contingent's behalf. When I read the actual pages, none of them said that (and the Mood Indigo page would not load). I removed those claims. What is below is only what the pages say.

---

## 1. How a fest runs

The order below is the typical shape. Every fest differs in its details.

| Stage | What happens | Tag |
|---|---|---|
| 1. Form the committee | A core committee is chosen months ahead, often through interview rounds and assignments. Managers lead groups of coordinators and organisers. | [S] |
| 2. Get approval and a budget | A faculty in-charge and student leads are typical. Colleges often want a budget estimate before releasing an advance. | [I] [S*] |
| 3. Raise money | Sponsorship often decides the budget. One guide splits a budget roughly as prizes 30%, marketing 25%, logistics and tech 20%, food and hospitality 10%, and a 15% contingency buffer. | [S] [S*] |
| 4. Plan events | Events are grouped into categories (cultural, technical, sports, literary, gaming and so on), each with coordinators, rules, judges, venue and timing. | [I] |
| 5. Onboard other colleges | Each visiting college picks a contingent leader (CL), often with one or two assistants (ACLs). A CL meet is held before the fest. | [S] [F] |
| 6. Open registrations | Individuals and teams register, usually through Google Forms, payment screenshots or a ticketing tool. | [S*] |
| 7. Logistics | Venue, equipment, stalls, security, accommodation, food, transport. Hostel and mess committees handle part of it. | [S] [S*] |
| 8. Publicity | Social media, college outreach, posters, PR. | [I] |
| 9. Fest days | Gate and check-in, running schedules, judging, results, volunteers on the ground. | [I] |
| 10. Wrap-up | Prizes, certificates, settling money with sponsors and vendors, thanking volunteers, a report for the college. | [I] |

---

## 2. The people

Titles change from fest to fest. This is the common shape, not a standard.

**Home committee**
- **Faculty in-charge or council:** approves, signs, supervises. [I]
- **Core committee:** a separate cultural or fest core committee, chosen through several rounds of interviews and assignments. One college's guide suggests 3 to 5 leaders, which is one college's advice and not a norm. [S]
- **Managers and coordinators:** one large fest (Techfest) is described as three tiers, with 21 managers under an overall coordinator, each manager supervising coordinators and organisers. [S*]
- **Heads of functions:** one guide lists marketing, sponsorship, event coordinators (per track), logistics, and creative and finance sub-teams. [S] Others I expect but could not source: registration and help desk, accommodation and hospitality, prizes, PR, tech, security. [I]
- **Event coordinators:** each runs one event: rules, judges, schedule, results. [I]
- **Volunteers** (often called organisers or OCs): a fest's volunteers can take over check-in after a day or two of mock training, according to one vendor's case study. [S*]

**Visiting colleges**
- **Contingent leader (CL):** the college's single point of contact and representative. [F] The pages I could read never define the role or its duties. What they do show: E-Summit (IIT Madras) defines a contingent as a group of students from one college, needs at least 5 members, lets a college form several contingents, and asks leaders to register to get further information. [S]
- **Assistant contingent leaders (ACLs):** one or two per college, so there is a backup. [F] A 2022 CL meet at DGMC had CLs and ACLs from 50+ colleges on a Zoom call. No public source describes the ACL's duties. [S]
- **Contingent members:** the participants. [S]
- **Contingent code and name:** each college gets a code, often tied to the fest's theme. [F]

**Others:** judges, guests and performers, sponsors, vendors, the audience. [I]

---

## 3. Where committees struggle

Most public sources are older student-press pieces or vendor marketing, so treat the evidence as anecdotal. The ranking below is my reading of it.

| Problem | Evidence | What HiveOut could do |
|---|---|---|
| **Sponsorship**: the most-cited problem. Budgets rise and fall with it, sponsors back out, last-minute costs go uncovered. [S] | Student interviews in press pieces (not opened) [S*] | Sponsor pipeline, deliverables per sponsor, a live budget against spend, with a reserve buffer |
| **Registration chaos**: Google Forms that fill past capacity, UPI screenshots in DMs, manual name checks at the gate. [S] | A vendor post, so the details are the vendor's view [S*] | Proper registration and payment (Razorpay), duplicate-proof passes, QR check-in. Largely built already |
| **Crowd and gate control**: Mood Indigo cancelled all pre-registrations after thousands gathered at the gate. [S] | News report [S*] | Capacity limits per day and slot, scanning on weak signal, volunteer roles at the gate |
| **Logistics sprawl**: venue, equipment, food, security, accommodation, each tracked in its own sheet or chat. [S] | Careers360 on hostel and mess committees needing cross-committee coordination [S] | One task and resource board per function, with owners and deadlines |
| **Coordinating many people**: dozens of volunteers and coordinators, mostly students, with faculty supervising. [S] | Careers360, RCM guide [S] | Roles and permissions, shifts, attendance, one place for announcements |
| **Visiting colleges**: contingent lists, payments, accommodation and updates handled by hand across chats. [F] [I] | Not documented publicly | A contingent portal for CLs: see section 4 |
| **Meetings and follow-up**: [I] | Not sourced; common in student teams | Agenda, minutes, action items with owners, attendance |
| **Schedule clashes and last-minute changes**: [I] | Not sourced | A single schedule by venue, with clash warnings and automatic notices to the people affected |

---

## 4. The contingent system

Everything in this section is **[F]** unless marked. Treat it as a hypothesis to validate.

### What you described
1. A college becomes a contingent, led by one **CL** and one or two **ACLs**.
2. Each contingent gets a **code and name**, usually tied to the fest's theme.
3. Before the fest, a **CL meet** is held. CLs hear what the fest is and play games.
4. In the games, CLs **earn and lose points**. Everyone starts with the same points.
5. CLs **bid their points** to win the contingent name they want.
6. Colleges that do not bid are **allotted the remaining names randomly**.
7. None of this is the same everywhere: each fest has its own theme, format and flow.

### What the public record shows
- **A CL meet with a game, no points:** BMS's 2015 meet had 20+ colleges. CLs heard about the events from the heads of cultural, academics and sports, and each picked and burst a balloon to reveal the challenge for the fashion show. [S]
- **A CL meet that mentions points:** DGMC's 2022 meet (CLs and ACLs from 50+ colleges, on Zoom) says CLs "can earn more PR points" by taking part in one of the fest's sections. So points tied to a CL exist at some fests. [S]
- **Team scoring at one fest:** E-Summit (IIT Madras) gives every team 50 points for taking part in on-spot events and 350, 300 and 250 for first to third, with ties broken by team strength and number of events entered. [S]
- **Contingent rules at one fest:** E-Summit has group discounts of 10% to 30% by contingent size, no changes to the team once registered, and "accommodation assistance" that gives contingents a preference to stay together. [S]
- **No source describes name bidding at all.** [S, as an absence]

### What this means for the product
Because every fest does it differently, the platform cannot ship one "CL meet". It needs a **configurable engine** with these building blocks (**[I]**):

- **A name pool:** the names a fest offers (with optional code, theme and description).
- **A points wallet** per contingent, with a starting balance and a ledger of every gain and loss (the same ledger can hold "PR points" earned outside the meet).
- **Games or activities** that award or deduct points. In v1 these can be entered by hand by the organiser; the games themselves happen in the room.
- **An allotment method:** bidding, lottery, first-come, or the organiser assigns. Bidding has its own settings: open or sealed, number of rounds, minimum bid, tie-break rule, what happens to unspent points.
- **A fallback rule:** whatever is left is allotted randomly to contingents that did not win a name.
- **A live screen for the room:** names, bids, points, results, visible on a projector.

---

## 5. The design principle: configure, never hard-code

A fest should be **assembled from options**, not fitted to our assumptions.

### Configurable per fest
- **Roles and teams:** the committee defines its own hierarchy (names, levels, what each role can do). Today HiveOut has three fixed roles (director, core, volunteer); this must become custom roles with permissions.
- **Event categories and rounds:** categories, rounds (prelims, finals), solo or team, judging criteria.
- **Scoring:** points per placing and per participation; whether there is an overall championship; how ties break.
- **Registration forms:** custom questions per event, per contingent and per participant (partly built).
- **Contingent rules:** who may lead, how many ACLs, minimum and maximum members, whether a college may field several contingents, entry limits per event, when the team locks (E-Summit allows no changes after registering), and group pricing by contingent size (E-Summit discounts 10% to 30%).
- **Points for CLs and contingents:** what earns points (taking part in a section, a game, a placing) and what they are worth (DGMC's "PR points", E-Summit's 50/350/300/250).
- **Modules on or off:** a small fest may use only events and registration; a large one turns on everything.
- **Names for things:** "contingent", "CL", "OC" are one fest's words. Labels should be editable.

### Two fests, one platform (illustration, **[I]**)

| | Fest A (large cultural) | Fest B (small technical) |
|---|---|---|
| Visiting colleges | 60, each with CL + 2 ACLs | None, open to individuals |
| Name allotment | Bidding at a CL meet, random leftovers | Not used |
| Scoring | Overall championship by points | No overall winner |
| Roles | 6 levels (convenor, heads, coordinators, OCs...) | 3 levels |
| Accommodation | Yes, per contingent | No |

---

## 6. Proposed modules, in build order

The order follows what unblocks the most committees soonest, and what the current build can extend. It is a proposal, not a decision.

| Phase | Module | Why this order | Builds on |
|---|---|---|---|
| **Done** | Organiser onboarding, event templates, "dates coming soon", field-level review notes | Gets a fest listed with less friction | Current build |
| **1** | **Custom roles and team hierarchy** | Everything else needs "who can do what" | Fest members (owner, core, volunteer) |
| **1** | **Meetings, tasks and schedule** | Every committee needs them, and they are the daily habit that keeps people on the platform | Events, announcements |
| **2** | **Contingent portal**: CL and ACL accounts, contingent registration, member lists, event entries, fees, accommodation requests | The visiting-college side, and what makes HiveOut a platform and not a website | Registrations, teams, payments |
| **2** | **Payments** (Razorpay) | Contingent fees and paid events both need it | Not built |
| **3** | **CL meet and name allotment engine** | The most distinctive feature, but it depends on contingents existing first | Contingent portal |
| **3** | **Results and leaderboard**, overall championship | Needs events, entries and contingents | Events, contingents |
| **4** | Volunteer shifts and attendance, gate upgrades, certificates | Builds on roles and schedule | Gate, roles |
| **5** | Sponsors and finance: pipeline, deliverables, budget against spend | Top pain point, but the hardest to get right without real committees | Roles, tasks |

---

## 7. What we must still learn (due diligence)

We do not yet know how these things work at fests beyond the one you know. Before building phases 2 and 3, talk to real people. A short list:

**Who to talk to (aim for 8 to 10, across 4 or more colleges):** 3 core committee members from different fests; 3 CLs or ACLs who have attended other fests; 1 faculty in-charge; 1 sponsorship or PR head.

**Questions for committees**
1. Walk me through the six months before your last fest. What did you do each month?
2. What tools did you use (sheets, WhatsApp, forms)? Which broke?
3. How was your committee structured? Names, levels, how many people?
4. What took more time than it should have? What went wrong on the day?
5. How do you track money, sponsors and promises?
6. How do you tell 60 colleges the same thing at once, and know they saw it?

**Questions for contingent leaders**
1. What does a CL actually do before and during a fest? And the ACL?
2. How did you get your contingent name and code at the last fest you attended? Was there a meet? What were the rules?
3. What was hard: registering, paying, accommodation, getting answers?
4. What did you wish you could see (schedule, results, your points)?
5. How do you manage your own college's participants?

**Things to ask for (the best evidence)**
- A CL meet rulebook, game sheets and bid records.
- A contingent code list and the theme behind it.
- A fest schedule sheet, a budget sheet and a volunteer duty chart.
- The Google Forms or sheets they used.

**Check against the research:** the questions the web could not answer, namely how widespread name bidding is, how ACLs are used, and how colleges get accommodation, should be marked as open until committees confirm them.

---

## Sources

**Opened and read:**
- [Blood, sweat and toil behind college fests (Careers360)](https://www.careers360.com/articles/blood-sweat-n-toil-behind-college-fests): core committee, interview rounds, the Techfest tiers, hostel and mess committees. Only the first part was available verbatim; the rest was a summary of the page.
- [How to organise a college fest: Brahmastra 2026 (RCM Bhubaneswar)](https://rcm.ac.in/how-to-organize-a-college-fest-lessons-from-brahmastra-2026/): team sizes, roles, the budget split and the 15% buffer. One college's own advice.
- [Contingent pass (E-Summit, E-Cell IIT Madras)](https://esummitiitm.org/passes/contingent-leader): contingent size, group discounts, accommodation assistance, team scoring. It does not define the CL role.
- [First CL meet of Meter Down 2015 (BMS)](https://www.bms.co.in/first-cl-meet-of-meter-down-2015/): a CL meet with a balloon game and no points.
- [Contingent Leader Meet, MIA and Cinevoyage 2022 (DGMC)](https://dgmc.org.in/?p=24282): CLs and ACLs of 50+ colleges, and "PR points".

**Seen only as search-result summaries (marked [S\*] above):**
- [Cost of a fest (Deccan Herald)](https://www.deccanherald.com/content/329668/cost-fest.html): budget estimates before an advance.
- [Season of college festivals (The Patriot)](https://thepatriot.in/reports/season-of-college-festivals-33685/amp): sponsorship difficulty.
- [How to organise a college fest (Unstop)](https://unstop.com/blog/how-to-organize-a-college-fest): teams, budgeting, ticketing.
- [Elan and nVision 2023 documentation (IIT Hyderabad)](https://gymkhana.iith.ac.in/documents/Elan%20&%20%CE%B7Vision%202023%20Documentation.pdf): sponsor outreach, creatives, volunteers.
- [Krupanidhi digitises campus events (Zoho Backstage)](https://www.zoho.com/backstage/customers/krupanidhi-group-of-institutions-college-fest.html): vendor case study, volunteers and check-in. Promotional.
- [DEV Community: a fest replaces Google Forms and UPI screenshots](https://dev.to/animesh_gupta_705a19fc6f8/how-a-college-cultural-fest-replaced-google-forms-upi-screenshots-and-a-name-check-queue-2825): registration pain. A vendor post.
- [Mood Indigo cancels pre-registrations amid crowd chaos (Careers360)](https://news.careers360.com/iit-bombay-cancels-mood-indigo-pre-registrations-stops-entry-outsiders-crowd-chaos-seedhe-maut-concert-sonu-nigam-vicky-kaushal): gate and crowd control.
- [College Fest Management Software (Townscript)](https://www.townscript.com/organize/college-fest-management-software) and [Unifesto (Capterra India)](https://www.capterra.in/software/1327832/Unifesto): existing tools. None found that cover contingents or accommodation.

**Tried and could not use:** a committee page on a Jabalpur institute's fest site (404), an IIT Mandi committee order (address did not load), and Mood Indigo's accommodation portal (loaded as an empty page). Earlier summaries had described them, and I dropped those claims.
