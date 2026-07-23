import os, re, sys
from datetime import datetime, date
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosters import ROSTERS
from news import NEWS

REPO = sys.argv[1] if len(sys.argv) > 1 else "repo"
TODAY = date.today()
TODAY_STR = TODAY.strftime("%Y_%m_%d")
TODAY_HUMAN = TODAY.strftime("%B %d, %Y")

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
    if not d:
        return ""
    return f"https://www.google.com/s2/favicons?domain={d}&sz=32"

def level_badge(level):
    return {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟡 Low"}.get(level, "⚪ n/a")

def account_md(account, subvertical):
    n = NEWS.get(account)
    lines = []
    lines.append(f"# {account}")
    lines.append("")
    lines.append(f"**Sub-vertical:** {subvertical}  ")
    lines.append(f"**News gathered:** {TODAY_HUMAN}  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    if n:
        thumb = favicon(n["url"])
        img = f'<img src="{thumb}" width="24" height="24" align="left" style="margin-right:8px" /> ' if thumb else ""
        lines.append(f"## {img}{n['title']}")
        lines.append("")
        lines.append(f"| | |")
        lines.append(f"|---|---|")
        lines.append(f"| **Date** | {n['date']} |")
        lines.append(f"| **Potential impact** | {level_badge(n['level'])} |")
        lines.append(f"| **Source** | [{urlparse(n['url']).netloc}]({n['url']}) |")
        lines.append("")
        lines.append(f"**Summary.** {n['summary']}")
        lines.append("")
        lines.append(f"**Why it matters (Microsoft angle).** {n['impact']}")
        lines.append("")
        lines.append(f"[Read the article →]({n['url']})")
    else:
        lines.append("## No material news identified in the past 30 days")
        lines.append("")
        lines.append("_No significant public news was found for this account in the current window. "
                     "This file will refresh automatically on the next daily run._")
    lines.append("")
    lines.append("---")
    lines.append(f"_Auto-generated on {TODAY_HUMAN}. News older than 90 days is pruned automatically._")
    lines.append("")
    return "\n".join(lines)

def latest_news_md(subvertical, accounts):
    with_news = [(a, NEWS[a]) for a in accounts if a in NEWS]
    without = [a for a in accounts if a not in NEWS]
    lines = []
    lines.append(f"# Latest News — {subvertical}")
    lines.append("")
    lines.append(f"**Updated:** {TODAY_HUMAN}  ")
    lines.append(f"**Accounts tracked:** {len(accounts)}  ")
    lines.append(f"**Accounts with news this cycle:** {len(with_news)}  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    if with_news:
        # sort by impact level then date desc
        order = {"High": 0, "Medium": 1, "Low": 2}
        with_news.sort(key=lambda x: (order.get(x[1]["level"], 3), x[1]["date"]), reverse=False)
        lines.append("## Summary table")
        lines.append("")
        lines.append("| | Account | Headline | Date | Impact | Link |")
        lines.append("|---|---|---|---|---|---|")
        for a, n in with_news:
            thumb = favicon(n["url"])
            img = f'![]({thumb})' if thumb else ""
            title = n["title"].replace("|", "\\|")
            lines.append(f"| {img} | **{a}** | {title} | {n['date']} | {level_badge(n['level'])} | [link]({n['url']}) |")
        lines.append("")
        lines.append("## Detail")
        lines.append("")
        for a, n in with_news:
            lines.append(f"### {a}")
            lines.append(f"**{n['title']}** — {n['date']} — {level_badge(n['level'])}")
            lines.append("")
            lines.append(f"{n['summary']}")
            lines.append("")
            lines.append(f"_Microsoft angle:_ {n['impact']}")
            lines.append("")
            lines.append(f"[Read →]({n['url']})")
            lines.append("")
    else:
        lines.append("_No material news across tracked accounts this cycle._")
        lines.append("")
    if without:
        lines.append("---")
        lines.append("")
        lines.append("<details><summary>Accounts with no material news this cycle "
                     f"({len(without)})</summary>")
        lines.append("")
        for a in without:
            lines.append(f"- {a}")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    lines.append("---")
    lines.append(f"_Auto-generated on {TODAY_HUMAN}._")
    lines.append("")
    return "\n".join(lines)

total_accounts = 0
total_news = 0
for top, subs in ROSTERS.items():
    for sub, accounts in subs.items():
        d = os.path.join(REPO, top, sub)
        os.makedirs(d, exist_ok=True)
        for a in accounts:
            total_accounts += 1
            if a in NEWS:
                total_news += 1
            fname = f"{TODAY_STR}_{slug(a)}.md"
            with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
                f.write(account_md(a, sub))
        with open(os.path.join(d, "Latest_News.md"), "w", encoding="utf-8") as f:
            f.write(latest_news_md(sub, accounts))

print(f"Accounts: {total_accounts}, with news: {total_news}")
