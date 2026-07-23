import os, re, sys
from datetime import date

# Deletes per-account dated markdown files (YYYY_MM_DD_*.md) older than N days.
# Leaves README.md, Latest_News.md, and scripts untouched.
ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
MAX_AGE_DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 90
today = date.today()
pat = re.compile(r"^(\d{4})_(\d{2})_(\d{2})_.+\.md$")

deleted = 0
for dirpath, _dirs, files in os.walk(ROOT):
    if ".git" in dirpath or "scripts" in dirpath:
        continue
    for fn in files:
        m = pat.match(fn)
        if not m:
            continue
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            fdate = date(y, mo, d)
        except ValueError:
            continue
        age = (today - fdate).days
        if age > MAX_AGE_DAYS:
            os.remove(os.path.join(dirpath, fn))
            deleted += 1
print(f"Pruned {deleted} file(s) older than {MAX_AGE_DAYS} days.")
