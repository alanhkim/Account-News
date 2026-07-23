import os, sys
from datetime import date
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rosters import ROSTERS
from news import NEWS
from generate import enrich, level_badge, PRIORITY

TODAY_HUMAN = date.today().strftime("%B %d, %Y")
REPO = sys.argv[1] if len(sys.argv) > 1 else "."

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

blocks = []
total = 0
high_count = 0
for top, subs in ROSTERS.items():
    for sub, accounts in subs.items():
        items = []
        for a in accounts:
            if a in NEWS:
                n = NEWS[a]
                plays, triggers, sentiment = enrich(n)
                items.append((a, n, plays, triggers, sentiment))
        # Always render the sub-vertical, even when it has no news.
        if not items:
            blocks.append(f"<h4>{esc(sub)} (0)</h4><p><i>No news.</i></p>")
            continue
        items.sort(key=lambda x: (PRIORITY.get(x[1]["level"], 0), 1 if x[3] else 0, x[1]["date"]), reverse=True)
        total += len(items)
        high_count += sum(1 for i in items if i[1]["level"] == "High")
        rows = []
        for a, n, plays, triggers, sentiment in items:
            tg = f" &middot; <i>{esc(', '.join(triggers))}</i>" if triggers else ""
            pl = f" &middot; {esc(', '.join(plays))}" if plays else ""
            rows.append(
                f"<li><b>{esc(a)}</b> — <a href=\"{esc(n['url'])}\">{esc(n['title'])}</a>"
                f"<br/>{level_badge(n['level'])} &middot; {sentiment}{tg}{pl}</li>"
            )
        blocks.append(f"<h4>{esc(sub)} ({len(items)})</h4><ul>{''.join(rows)}</ul>")

SITE = "https://alanhkim.github.io/Account-News/"
header = (
    f"<p>🔗 <b><a href=\"{SITE}\">Open the FSI Account News dashboard →</a></b></p>"
    f"<h3>📊 FSI Account News — {TODAY_HUMAN}</h3>"
    f"<p><b>{total}</b> accounts with news today &middot; <b>{high_count}</b> high-impact. "
    f"Browse &amp; filter in the <a href=\"{SITE}\">dashboard</a> &middot; "
    f"source in the <a href=\"https://github.com/alanhkim/Account-News\">repo</a>.</p>"
)
html = header + "".join(blocks) if blocks else header + "<p>No material news across tracked accounts today.</p>"

# Write digest to DIGEST.html; the caller sends its contents to Teams (contentType=html).
with open(os.path.join(REPO, "DIGEST.html"), "w", encoding="utf-8") as f:
    f.write(html)
print(f"Wrote DIGEST.html ({len(html)} chars, {total} accounts, {high_count} high-impact).")
