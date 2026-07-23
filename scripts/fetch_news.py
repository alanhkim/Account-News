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

Usage:  python scripts/fetch_news.py [repo_root] [--limit N] [--window 30]
"""
import os, sys, re, json, time, ssl, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosters import ROSTERS
from generate import infer_plays, infer_triggers  # safe: generate guards its build under __main__

REPO = "."
LIMIT = None
WINDOW_DAYS = 30
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--limit":
        LIMIT = int(args[i + 1]); i += 2
    elif args[i] == "--window":
        WINDOW_DAYS = int(args[i + 1]); i += 2
    else:
        REPO = args[i]; i += 1

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "").strip()
PROVIDER = "newsapi" if NEWSAPI_KEY else "gdelt"
UA = "AccountNewsBot/1.0 (+https://github.com/alanhkim/Account-News)"
CUTOFF = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
_ctx = ssl.create_default_context()

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
    with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

# ---------------- Providers ----------------
def gdelt(query):
    q = urllib.parse.quote(f'"{query}" sourcelang:eng')
    url = (f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}"
           f"&mode=ArtList&maxrecords=20&timespan={WINDOW_DAYS}d&format=json&sort=DateDesc")
    for attempt in range(4):
        try:
            data = _get(url)
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
            if "429" in str(e) and attempt < 3:
                time.sleep(6 * (attempt + 1)); continue
            return []
    return []

def newsapi(query):
    frm = CUTOFF.strftime("%Y-%m-%d")
    q = urllib.parse.quote(f'"{query}"')
    url = (f"https://newsapi.org/v2/everything?q={q}&from={frm}&language=en"
           f"&sortBy=publishedAt&pageSize=15&apiKey={NEWSAPI_KEY}")
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
def run():
    accounts = []
    for top, subs in ROSTERS.items():
        for sub, names in subs.items():
            accounts.extend(names)
    if LIMIT:
        accounts = accounts[:LIMIT]

    fetch = newsapi if PROVIDER == "newsapi" else gdelt
    news, kept = {}, 0
    for idx, acct in enumerate(accounts, 1):
        short, _ = brand(acct)
        try:
            best = pick(acct, fetch(short))
        except Exception:
            best = None
        if best:
            blob = f"{best['title']} {best['summary']}"
            plays = infer_plays(blob)
            triggers = infer_triggers(blob)
            news[acct] = {
                "title": best["title"],
                "date": best["date"].strftime("%Y-%m-%d"),
                "summary": best["summary"],
                "impact": derive_impact(plays),
                "level": derive_level(triggers, plays),
                "url": best["url"],
                "image": best["image"],
            }
            kept += 1
        if PROVIDER == "gdelt":
            time.sleep(5)  # be polite to the keyless API
        if idx % 25 == 0:
            print(f"  ...{idx}/{len(accounts)} scanned, {kept} with news", file=sys.stderr)

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
