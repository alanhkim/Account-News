import os, re, sys, json
from datetime import date, timedelta
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosters import ROSTERS
from news import NEWS

REPO = sys.argv[1] if len(sys.argv) > 1 else "repo"
TODAY = date.today()
TODAY_STR = TODAY.strftime("%Y_%m_%d")
TODAY_ISO = TODAY.strftime("%Y-%m-%d")
TODAY_HUMAN = TODAY.strftime("%B %d, %Y")
MAX_AGE_DAYS = 90

def slug(name):
    s = name.lower()
    s = re.sub(r"[&]", "and", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")

def favicon(url):
    try:
        d = urlparse(url).netloc
    except Exception:
        d = ""
    return f"https://www.google.com/s2/favicons?domain={d}&sz=32" if d else ""

def level_badge(level):
    return {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟡 Low"}.get(level, "⚪ n/a")

# ---------------- Classification ----------------
PLAY_KEYWORDS = {
    "Azure AI": ["ai ", "a.i.", "artificial intelligence", "machine learning", "genai",
                 "ai-powered", "ai-driven", "quantamental", "chatbot", "automation", "models"],
    "Copilot": ["copilot", "advisor productivity", "productivity", "employee", "benefits platform",
                "customer engagement"],
    "Fabric": ["data", "analytics", "index", "reporting", "modeling", "model", "actuarial",
               "platform", "esg", "settlement", "market-data", "market data", "migration"],
    "Security": ["cyber", "security", "breach", "ransomware", "cyberattack", "resilience",
                 "fraud", "custody", "risk"],
}
TRIGGER_KEYWORDS = {
    "Earnings": ["earnings", "quarterly", "q1 ", "q2 ", "q3 ", "q4 ", "results", "revenue",
                 "net income", "dividend", "stress test", "profit"],
    "M&A": ["acquir", "acquisition", "merger", "stake", "deal", "sells", "sold", "restructur",
            "fund", "raises", "first close", "buyout", "consortium"],
    "CxO Change": ["cfo", "ceo", "chief ", "appoint", "names ", "leadership", "executive vice president"],
    "Breach": ["breach", "ransomware", "cyberattack", "hack", "data leak"],
    "Product Launch": ["launch", "unveil", "introduce", "rolls out", "rolled out", "partner",
                       "partnership", "platform for"],
    "Regulatory": ["regulatory", "approval", "sec ", "finra", "compliance", "ratings", "rating"],
}
POS = ["record", "growth", "strong", "raise", "beat", "excellent", "up ", "expand",
       "outstanding", "surge", "gains", "leadership", "boost"]
NEG = ["downturn", "loss", "losses", "distress", "alarm", "warns", "warn", "cut", "decline",
       "vulnerab", "restructur", "pressure", "concern", "headwind", "attack"]

def _hits(text, keywords):
    t = text.lower()
    return [k for k in keywords if k in t]

def infer_plays(text):
    return [p for p, kws in PLAY_KEYWORDS.items() if _hits(text, kws)]

def infer_triggers(text):
    return [tg for tg, kws in TRIGGER_KEYWORDS.items() if _hits(text, kws)]

def infer_sentiment(text):
    t = text.lower()
    pos = sum(t.count(w) for w in POS)
    neg = sum(t.count(w) for w in NEG)
    if pos > neg:
        return "🟢 Positive"
    if neg > pos:
        return "🔴 Negative"
    return "⚪ Neutral"

def enrich(n):
    blob = f"{n['title']} {n['summary']} {n['impact']}"
    return infer_plays(blob), infer_triggers(blob), infer_sentiment(blob)

PRIORITY = {"High": 3, "Medium": 2, "Low": 1}

# ---------------- Per-account file ----------------
def account_md(account, subvertical):
    n = NEWS.get(account)
    L = []
    L.append(f"# {account}")
    L.append("")
    L.append(f"**Sub-vertical:** {subvertical}  ")
    L.append(f"**News gathered:** {TODAY_HUMAN}  ")
    L.append(f"**History:** see [`{slug(account)}_timeline.md`]({slug(account)}_timeline.md)  ")
    L.append("")
    L.append("---")
    L.append("")
    if n:
        plays, triggers, sentiment = enrich(n)
        thumb = favicon(n["url"])
        img = f'<img src="{thumb}" width="24" height="24" align="left" style="margin-right:8px" /> ' if thumb else ""
        L.append(f"## {img}{n['title']}")
        L.append("")
        L.append("| | |")
        L.append("|---|---|")
        L.append(f"| **Date** | {n['date']} |")
        L.append(f"| **Potential impact** | {level_badge(n['level'])} |")
        L.append(f"| **Sentiment** | {sentiment} |")
        L.append(f"| **Trigger events** | {', '.join(triggers) if triggers else '—'} |")
        L.append(f"| **Solution plays** | {', '.join(plays) if plays else '—'} |")
        L.append(f"| **Source** | [{urlparse(n['url']).netloc}]({n['url']}) |")
        L.append("")
        L.append(f"**Summary.** {n['summary']}")
        L.append("")
        L.append(f"**Why it matters (Microsoft angle).** {n['impact']}")
        L.append("")
        L.append(f"[Read the article →]({n['url']})")
    else:
        L.append("## No material news identified in the past 30 days")
        L.append("")
        L.append("_No significant public news was found for this account in the current window. "
                 "This file will refresh automatically on the next daily run._")
    L.append("")
    L.append("---")
    L.append(f"_Auto-generated on {TODAY_HUMAN}. News older than {MAX_AGE_DAYS} days is pruned automatically._")
    L.append("")
    return "\n".join(L)

# ---------------- Rolling timeline ----------------
TL_ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*\[link\]\((.*?)\)\s*\|\s*$")

def update_timeline(path, account, n):
    rows = {}  # date -> (headline, impact, sentiment, url)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = TL_ROW.match(line.strip())
                if m:
                    rows[m.group(1)] = (m.group(2), m.group(3), m.group(4), m.group(5))
    if n:
        _, _, sentiment = enrich(n)
        rows[n["date"]] = (n["title"].replace("|", "\\|"), level_badge(n["level"]), sentiment, n["url"])
    cutoff = TODAY - timedelta(days=MAX_AGE_DAYS)
    kept = {}
    for d, v in rows.items():
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            continue
        if dd >= cutoff:
            kept[d] = v
    L = [f"# {account} — News Timeline", "",
         f"Rolling history of tracked news (last {MAX_AGE_DAYS} days). Updated {TODAY_HUMAN}.", "",
         "| Date | Headline | Impact | Sentiment | Link |",
         "|---|---|---|---|---|"]
    if kept:
        for d in sorted(kept.keys(), reverse=True):
            hl, imp, sent, url = kept[d]
            L.append(f"| {d} | {hl} | {imp} | {sent} | [link]({url}) |")
    else:
        L.append("| — | _No tracked news in the current window._ | — | — | — |")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

# ---------------- Sub-vertical summary ----------------
def latest_news_md(subvertical, accounts):
    items = []
    for a in accounts:
        if a in NEWS:
            n = NEWS[a]
            plays, triggers, sentiment = enrich(n)
            items.append((a, n, plays, triggers, sentiment))
    without = [a for a in accounts if a not in NEWS]
    items.sort(key=lambda x: (PRIORITY.get(x[1]["level"], 0), 1 if x[3] else 0, x[1]["date"]), reverse=True)
    L = []
    L.append(f"# Latest News — {subvertical}")
    L.append("")
    L.append(f"**Updated:** {TODAY_HUMAN}  ")
    L.append(f"**Accounts tracked:** {len(accounts)}  ")
    L.append(f"**Accounts with news this cycle:** {len(items)}  ")
    L.append("")
    L.append("---")
    L.append("")
    if items:
        L.append("## Prioritized summary")
        L.append("")
        L.append("| | Account | Headline | Date | Impact | Sentiment | Triggers | Solution plays | Link |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for a, n, plays, triggers, sentiment in items:
            thumb = favicon(n["url"])
            img = f'![]({thumb})' if thumb else ""
            title = n["title"].replace("|", "\\|")
            L.append(f"| {img} | **{a}** | {title} | {n['date']} | {level_badge(n['level'])} | "
                     f"{sentiment} | {', '.join(triggers) or '—'} | {', '.join(plays) or '—'} | [link]({n['url']}) |")
        L.append("")
        L.append("## Detail")
        L.append("")
        for a, n, plays, triggers, sentiment in items:
            L.append(f"### {a}")
            L.append(f"**{n['title']}** — {n['date']} — {level_badge(n['level'])} — {sentiment}")
            L.append("")
            L.append(f"{n['summary']}")
            L.append("")
            if triggers:
                L.append(f"_Trigger events:_ {', '.join(triggers)}  ")
            if plays:
                L.append(f"_Solution plays:_ {', '.join(plays)}  ")
            L.append(f"_Microsoft angle:_ {n['impact']}")
            L.append("")
            L.append(f"[Read →]({n['url']})")
            L.append("")
    else:
        L.append("_No material news across tracked accounts this cycle._")
        L.append("")
    if without:
        L.append("---")
        L.append("")
        L.append(f"<details><summary>Accounts with no material news this cycle ({len(without)})</summary>")
        L.append("")
        for a in without:
            L.append(f"- {a}")
        L.append("")
        L.append("</details>")
        L.append("")
    L.append("---")
    L.append(f"_Auto-generated on {TODAY_HUMAN}._")
    L.append("")
    return "\n".join(L)

# ---------------- Build ----------------
def sentiment_word(s):
    return s.split(" ", 1)[-1] if s else "Neutral"

def main():
    total_accounts = total_news = high_count = 0
    verticals = []
    for top, subs in ROSTERS.items():
        for sub, accounts in subs.items():
            d = os.path.join(REPO, top, sub)
            os.makedirs(d, exist_ok=True)
            sub_items = []
            for a in accounts:
                total_accounts += 1
                n = NEWS.get(a)
                if n:
                    total_news += 1
                    plays, triggers, sentiment = enrich(n)
                    if n["level"] == "High":
                        high_count += 1
                    sub_items.append({
                        "account": a, "title": n["title"], "url": n["url"],
                        "date": n["date"], "level": n["level"],
                        "summary": n.get("summary", ""), "impact": n.get("impact", ""),
                        "plays": plays, "triggers": triggers,
                        "sentiment": sentiment_word(sentiment),
                        "image": n.get("image", ""), "favicon": favicon(n["url"]),
                    })
                with open(os.path.join(d, f"{TODAY_STR}_{slug(a)}.md"), "w", encoding="utf-8") as f:
                    f.write(account_md(a, sub))
                update_timeline(os.path.join(d, f"{slug(a)}_timeline.md"), a, n)
            with open(os.path.join(d, "Latest_News.md"), "w", encoding="utf-8") as f:
                f.write(latest_news_md(sub, accounts))
            sub_items.sort(key=lambda x: (PRIORITY.get(x["level"], 0), 1 if x["triggers"] else 0, x["date"]), reverse=True)
            verticals.append({"top": top, "sub": sub, "count": len(sub_items), "items": sub_items})

    # ---------------- Front-end data ----------------
    docs_dir = os.path.join(REPO, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    data = {
        "generated": TODAY_ISO,
        "generated_human": TODAY_HUMAN,
        "counts": {"accounts_total": total_accounts, "with_news": total_news, "high": high_count},
        "verticals": verticals,
    }
    with open(os.path.join(docs_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Accounts: {total_accounts}, with news: {total_news}, high: {high_count}. Wrote docs/data.json")

if __name__ == "__main__":
    main()
