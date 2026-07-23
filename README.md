# Account News

Automated daily news intelligence for Microsoft FSI (Financial Services Industry) account teams.

This repository tracks recent, current, and upcoming news for every account in the FY26 FSI
book of business, organized by vertical and sub-vertical. It refreshes automatically every day
so account teams can walk into customer conversations with the latest context.

## What's inside

Each account has its own markdown file containing the most relevant news from the past 30 days:
headline, date, a short summary, a **potential-impact rating**, the **Microsoft angle** (why it
matters for our engagement), a link to the source article, and a source thumbnail. Open any file
in **preview mode** to read it cleanly.

Every sub-vertical folder also has a **`Latest_News.md`** file — a rolled-up summary of all
accounts in that sub-vertical, with a scannable table plus detail sections.

## Structure

```
Account News/
├── README.md
├── Banking/
│   ├── Banking Majors/
│   │   ├── Latest_News.md
│   │   └── YYYY_MM_DD_<account>.md
│   └── Banking Strategic/
├── Capital Market/
│   ├── Capital Market Majors/
│   └── Capital Markets Strategic/
└── Insurance/
    ├── Insurance Majors/
    └── Insurance Strategic/
```

## File naming

Per-account files are named `YYYY_MM_DD_accountname.md`, where the date is when the news was
gathered. This gives a dated history per account and makes automatic pruning simple.

## Account mapping (source of truth)

The account → sub-vertical mapping is pulled from the **authoritative FY26 FSI mapping** in
Microsoft 365 (via WorkIQ / M365 Copilot) — the FY26 FSI SE Onboarding materials and the FY26
FSI Banking Majors account list. Accounts are **not** guessed. If the mapping changes, the daily
run picks it up.

## Impact rating

| Badge | Meaning |
|---|---|
| 🔴 High | Material event — earnings, M&A, leadership change, regulatory action; act now |
| 🟠 Medium | Notable strategic/product move worth a talking point |
| 🟡 Low | Minor or informational item |

## Signals on every item

Each news item is auto-classified so reps can filter by what they sell and prioritize outreach:

- **Solution plays** — `Azure AI`, `Copilot`, `Fabric`, `Security` (an item can carry several).
- **Sentiment** — 🟢 Positive / ⚪ Neutral / 🔴 Negative.
- **Trigger events** — `Earnings`, `M&A`, `CxO Change`, `Breach`, `Product Launch`, `Regulatory`.

`Latest_News.md` is sorted by priority (impact → trigger present → recency) and exposes these as
columns so you can scan or filter quickly.

## Per-account timelines

Every account has a rolling **`<account>_timeline.md`** — a dated history table of tracked news
over the last 90 days (headline, impact, sentiment, link), newest first. It updates each run and
self-trims at 90 days.

## Morning Teams digest

Each daily run generates `DIGEST.html` (a compact, prioritized roll-up grouped by sub-vertical)
and **sends it to you on Teams** (Notes to Self) so you get the highlights without opening the repo.

## Automation

A scheduled job runs **daily at 9:00 AM ET** and:

1. Re-pulls the sub-vertical account mappings from WorkIQ (authoritative).
2. Gathers the last 30 days of news for each account.
3. Writes new `YYYY_MM_DD_<account>.md` files and updates each `<account>_timeline.md`.
4. **Deletes any dated account file older than 90 days.**
5. Regenerates each sub-vertical's `Latest_News.md`.
6. Builds `DIGEST.html` and sends the morning digest to Teams.
7. Commits and pushes the changes.

> **Timezone note:** the scheduler runs in the host's local time. It is currently set so the run
> fires at ~9:00 AM **US Eastern (EDT)**. When Eastern shifts to EST (standard time), nudge the
> schedule by one hour to keep it at 9 AM ET.

## Coverage snapshot

- **237** accounts tracked across 6 sub-verticals.
- Sub-verticals: Banking Majors, Banking Strategic, Capital Market Majors, Capital Markets
  Strategic, Insurance Majors, Insurance Strategic.

## Notes & caveats

- News is gathered via automated web search and is **best-effort**. Always click through to the
  source before using an item in a customer conversation.
- Accounts with no significant public news in the window show a clean "No material news" file —
  this is expected, especially for smaller/private entities.
- Internal Microsoft mapping documents are referenced only to build the roster; no confidential
  source links are stored in this repo.

---
_Private repository. Auto-generated content. Owner: alanhkim._
