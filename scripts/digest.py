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

def domain(url):
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""

blocks = []
total = 0
high_count = 0
# Level 2 (H2) = top vertical; Level 3 (H3) = sub-vertical; bold = account; link = headline; small = metadata.
for top, subs in ROSTERS.items():
    sub_blocks = []
    top_total = 0
    for sub, accounts in subs.items():
        items = []
        for a in accounts:
            if a in NEWS:
                n = NEWS[a]
                plays, triggers, sentiment = enrich(n)
                items.append((a, n, plays, triggers, sentiment))
        # Always render the sub-vertical, even when it has no news.
        if not items:
            sub_blocks.append(f"<h3>{esc(sub)} <span style=\"font-weight:normal;color:#8b949e;\">(0)</span></h3><p><small><i>No news.</i></small></p>")
            continue
        items.sort(key=lambda x: (PRIORITY.get(x[1]["level"], 0), 1 if x[3] else 0, x[1]["date"]), reverse=True)
        total += len(items)
        top_total += len(items)
        high_count += sum(1 for i in items if i[1]["level"] == "High")
        rows = []
        for a, n, plays, triggers, sentiment in items:
            tg = f" &middot; <i>{esc(', '.join(triggers))}</i>" if triggers else ""
            pl = f" &middot; {esc(', '.join(plays))}" if plays else ""
            src = domain(n["url"])
            src_tag = f" &middot; <span style=\"color:#8b949e;\">{esc(src)}</span>" if src else ""
            rows.append(
                f"<li><b>{esc(a)}</b><br/>"
                f"<a href=\"{esc(n['url'])}\">{esc(n['title'])}</a><br/>"
                f"<small>{level_badge(n['level'])} &middot; {sentiment}{tg}{pl}{src_tag}</small></li>"
            )
        sub_blocks.append(f"<h3>{esc(sub)} <span style=\"font-weight:normal;color:#8b949e;\">({len(items)})</span></h3><ul>{''.join(rows)}</ul>")
    blocks.append(f"<h2>{esc(top)} <span style=\"font-weight:normal;color:#8b949e;\">({top_total})</span></h2>{''.join(sub_blocks)}")

SITE = "https://alanhkim.github.io/Account-News/"
header = (
    f"<h1>📊 FSI Account News</h1>"
    f"<p style=\"color:#8b949e;\"><b>{TODAY_HUMAN}</b> &middot; <b>{total}</b> accounts with news &middot; <b>{high_count}</b> high-impact</p>"
    f"<p>🔗 <b><a href=\"{SITE}\">Open the FSI Account News dashboard →</a></b></p>"
    f"<p><small>Browse &amp; filter in the <a href=\"{SITE}\">dashboard</a> &middot; "
    f"source in the <a href=\"https://github.com/alanhkim/Account-News\">repo</a>.</small></p>"
    f"<hr/>"
)
html = header + "".join(blocks) if blocks else header + "<p>No material news across tracked accounts today.</p>"

# Write digest to DIGEST.html; the caller sends its contents to Teams (contentType=html).
with open(os.path.join(REPO, "DIGEST.html"), "w", encoding="utf-8") as f:
    f.write(html)
print(f"Wrote DIGEST.html ({len(html)} chars, {total} accounts, {high_count} high-impact).")
