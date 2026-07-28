#!/usr/bin/env python3
"""Fetch recent per-account news from a news API and (re)write scripts/news.py.

Providers
---------
- Default: GDELT DOC 2.0 (keyless).           https://api.gdeltproject.org/api/v2/doc/doc
- Optional: NewsAPI (richer: description+image) if env NEWSAPI_KEY is set.

Guarantees
----------
- Deep article links (not landing pages), real publish dates, de-duplicated.
- Only accounts with a brand-matched article in the last WINDOW_DAYS are kept.
- Never fabricates: if nothing solid is found for an account, it is omitted.

Downstream: generate.py infers solution plays / triggers / sentiment from the
title+summary, and derives per-item badges. This script only supplies the raw
facts (title, url, date, summary, image) plus a coarse impact level.

Speed
-----
Accounts are fetched concurrently (a small worker pool) while a single global
rate limiter paces request *launches* so the aggregate hit rate on the API stays
polite. This overlaps the network latency of many accounts instead of paying it
serially, which keeps the full roster to minutes even when the API is slow.

Usage:  python scripts/fetch_news.py [repo_root] [--limit N] [--window 30]
                                     [--workers 8] [--pace 3.0]
"""
import os, sys, re, json, time, ssl, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosters import ROSTERS
from generate import infer_plays, infer_triggers  # safe: generate guards its build under __main__

REPO = "."
LIMIT = None
WINDOW_DAYS = 30
WORKERS = 8
PACE = 3.0  # min seconds between request launches (global, across all workers)
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--limit":
        LIMIT = int(args[i + 1]); i += 2
    elif args[i] == "--window":
        WINDOW_DAYS = int(args[i + 1]); i += 2
    elif args[i] == "--workers":
        WORKERS = int(args[i + 1]); i += 2
    elif args[i] == "--pace":
        PACE = float(args[i + 1]); i += 2
    else:
        REPO = args[i]; i += 1

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "").strip()
PROVIDER = "newsapi" if NEWSAPI_KEY else "gdelt"
UA = "AccountNewsBot/1.0 (+https://github.com/alanhkim/Account-News)"
CUTOFF = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
_ctx = ssl.create_default_context()

# ---- Global paced rate limiter -------------------------------------------
# A single lock serializes request *launches* so that, no matter how many
# worker threads are running, the API is hit at most once per PACE seconds
# (plus an adaptive penalty that grows when the API starts returning 429s).
_rate_lock = threading.Lock()
_next_slot = [0.0]        # earliest monotonic time the next request may start
_penalty = [0.0]          # adaptive extra spacing added after 429s (seconds)

def _throttle():
    """Block until this thread is allowed to launch its request."""
    with _rate_lock:
        now = time.monotonic()
        start = max(now, _next_slot[0])
        _next_slot[0] = start + PACE + _penalty[0]
    wait = start - time.monotonic()
    if wait > 0:
        time.sleep(wait)

def _note_429():
    """Back off globally when throttled; capped so it can't stall forever."""
    with _rate_lock:
        _penalty[0] = min(_penalty[0] + 1.0, 8.0)

def _note_ok():
    """Slowly relax the adaptive penalty on successful calls."""
    with _rate_lock:
        if _penalty[0] > 0:
            _penalty[0] = max(0.0, _penalty[0] - 0.25)

CORP_SUFFIX = re.compile(
    r"\b(inc|inc\.|llc|l\.l\.c|corp|corporation|co|company|group|holdings?|plc|"
    r"n\.a|na|the|ltd|lp|l\.p|associates?|sa|ag|and|&)\b", re.I)

def brand(account):
    """A short, quotable brand form for querying + a token used to validate matches."""
    name = account.replace("&", " and ")
    name = re.sub(r"[^A-Za-z0-9 ]", " ", name)
    words = [w for w in name.split() if not CORP_SUFFIX.fullmatch(w)]
    short = " ".join(words[:4]) if words else account
    token = (words[0].lower() if words else account.split()[0].lower())
    return short.strip(), token

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20, context=_ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

# ---------------- Providers ----------------
def gdelt(query):
    q = urllib.parse.quote(f'"{query}" sourcelang:eng')
    url = (f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}"
           f"&mode=ArtList&maxrecords=20&timespan={WINDOW_DAYS}d&format=json&sort=DateDesc")
    for attempt in range(2):
        _throttle()
        try:
            data = _get(url)
            _note_ok()
            out = []
            for a in data.get("articles", []):
                dt = _parse_gdelt_date(a.get("seendate", ""))
                if not dt:
                    continue
                out.append({"title": (a.get("title") or "").strip(),
                            "url": a.get("url", ""), "date": dt,
                            "summary": "", "image": a.get("socialimage", "") or "",
                            "domain": a.get("domain", "")})
            return out
        except Exception as e:
            if "429" in str(e) and attempt < 1:
                _note_429()
                continue
            return []
    return []

def newsapi(query):
    frm = CUTOFF.strftime("%Y-%m-%d")
    q = urllib.parse.quote(f'"{query}"')
    url = (f"https://newsapi.org/v2/everything?q={q}&from={frm}&language=en"
           f"&sortBy=publishedAt&pageSize=15&apiKey={NEWSAPI_KEY}")
    _throttle()
    try:
        data = _get(url)
    except Exception:
        return []
    out = []
    for a in data.get("articles", []):
        dt = _parse_iso(a.get("publishedAt", ""))
        if not dt:
            continue
        src = (a.get("url") or "")
        out.append({"title": (a.get("title") or "").strip(),
                    "url": src, "date": dt,
                    "summary": (a.get("description") or "").strip(),
                    "image": a.get("urlToImage") or "",
                    "domain": urllib.parse.urlparse(src).netloc})
    return out

def _parse_gdelt_date(s):
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def _parse_iso(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

# ---------------- Selection ----------------
def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()

def pick(account, arts):
    """Dedup and keep the most recent in-window article.
    The provider query already phrase-matches the quoted brand, so we trust
    relevance and only de-duplicate + enforce the date window here."""
    seen_u, seen_t, cands = set(), set(), []
    for a in arts:
        if not a["url"] or not a["title"] or a["date"] < CUTOFF:
            continue
        u = a["url"].split("?")[0].rstrip("/").lower()
        nt = norm_title(a["title"])
        if u in seen_u or nt in seen_t:
            continue
        seen_u.add(u); seen_t.add(nt); cands.append(a)
    if not cands:
        return None
    cands.sort(key=lambda x: x["date"], reverse=True)
    return cands[0]

def derive_level(triggers, plays):
    if set(triggers) & {"Breach", "M&A", "Earnings"}:
        return "High"
    if triggers or plays:
        return "Medium"
    return "Low"

def derive_impact(plays):
    if plays:
        return ("Potential " + ", ".join(plays) +
                " opportunity — align outreach to this signal.")
    return "Account-planning context; no direct solution-play signal detected."

# ---------------- Run ----------------
def _fetch_account(acct, fetch):
    """Worker: fetch + select the best in-window article for one account.
    Returns (acct, record_or_None). Pacing/backoff is handled inside `fetch`."""
    short, _ = brand(acct)
    try:
        best = pick(acct, fetch(short))
    except Exception:
        best = None
    if not best:
        return acct, None
    blob = f"{best['title']} {best['summary']}"
    plays = infer_plays(blob)
    triggers = infer_triggers(blob)
    return acct, {
        "title": best["title"],
        "date": best["date"].strftime("%Y-%m-%d"),
        "summary": best["summary"],
        "impact": derive_impact(plays),
        "level": derive_level(triggers, plays),
        "url": best["url"],
        "image": best["image"],
    }

def run():
    accounts = []
    for top, subs in ROSTERS.items():
        for sub, names in subs.items():
            accounts.extend(names)
    if LIMIT:
        accounts = accounts[:LIMIT]

    fetch = newsapi if PROVIDER == "newsapi" else gdelt
    news, kept, done = {}, 0, 0
    # Fetch concurrently: workers overlap the (often high) network latency while
    # the global rate limiter keeps the aggregate request rate polite.
    with ThreadPoolExecutor(max_workers=max(1, WORKERS)) as pool:
        futures = {pool.submit(_fetch_account, acct, fetch): acct for acct in accounts}
        for fut in as_completed(futures):
            acct = futures[fut]
            try:
                _, rec = fut.result()
            except Exception:
                rec = None
            done += 1
            if rec:
                news[acct] = rec
                kept += 1
            if done % 25 == 0:
                print(f"  ...{done}/{len(accounts)} scanned, {kept} with news",
                      file=sys.stderr)

    # Keep a stable roster order in the output (independent of completion order).
    news = {a: news[a] for a in accounts if a in news}

    out = os.path.join(REPO, "scripts", "news.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write('"""Per-account news — AUTO-GENERATED by fetch_news.py. Do not hand-edit.\n')
        f.write(f'Provider: {PROVIDER}. Window: last {WINDOW_DAYS} days. '
                f'Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")}.\n"""\n\n')
        f.write("NEWS = ")
        f.write(json.dumps(news, ensure_ascii=False, indent=4))
        f.write("\n")
    print(f"Provider={PROVIDER}: wrote {kept} accounts with news to scripts/news.py")

if __name__ == "__main__":
    run()
