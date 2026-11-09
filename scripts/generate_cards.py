#!/usr/bin/env python3
"""Generate self-hosted GitHub profile cards (stats, languages, streak, pinned repos).

Writes SVG files to ./assets and refreshes the pinned block in README.md.
No third-party packages and no third-party image servers: only the GitHub API.
Run `python scripts/generate_cards.py --demo` to test offline with fake data.
"""
import datetime as dt
import json
import os
import re
import sys
import textwrap
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "abhijitpavse")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = "assets"
README = "README.md"

# Tokyo Night palette
BG, BORDER = "#1a1b27", "#2f334d"
TITLE, TEXT, ACCENT, GREEN = "#70a5fd", "#a9b1d6", "#bf91f3", "#38bdae"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"


# ---------------------------------------------------------------- API
def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.load(r)
    if not data.get("data"):
        raise RuntimeError(data.get("errors"))
    return data["data"]


PROFILE_Q = """
query($login:String!){ user(login:$login){
  name createdAt
  followers{totalCount}
  pullRequests{totalCount}
  issues{totalCount}
  contributionsCollection{ totalCommitContributions }
  pinnedItems(first:6, types:REPOSITORY){ nodes{ ... on Repository{
    name description url stargazerCount forkCount primaryLanguage{name color} } } }
  repositories(ownerAffiliations:OWNER, isFork:false, first:100, privacy:PUBLIC){
    totalCount
    nodes{ stargazerCount languages(first:8, orderBy:{field:SIZE, direction:DESC}){
      edges{ size node{ name color } } } } }
}}"""

CAL_Q = """
query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
  contributionsCollection(from:$from, to:$to){ contributionCalendar{
    totalContributions weeks{ contributionDays{ date contributionCount } } } } } }"""


def fetch():
    u = gql(PROFILE_Q, {"login": USER})["user"]
    now = dt.datetime.now(dt.timezone.utc)
    days = []
    for year in range(int(u["createdAt"][:4]), now.year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = min(now, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        cal = gql(CAL_Q, {"login": USER, "from": frm, "to": to.strftime("%Y-%m-%dT%H:%M:%SZ")})
        cal = cal["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days.append((d["date"], d["contributionCount"]))
    return u, sorted(set(days))


def demo():
    u = {"name": "Abhijit Pavse", "createdAt": "2022-10-11T00:00:00Z",
         "followers": {"totalCount": 4}, "pullRequests": {"totalCount": 7},
         "issues": {"totalCount": 2}, "contributionsCollection": {"totalCommitContributions": 310},
         "pinnedItems": {"nodes": [
             {"name": "Customer-Shopping-Behavior-Analysis", "url": "https://github.com/x/y",
              "description": "End-to-end customer shopping behavior analysis using Python, PostgreSQL and Power BI dashboards.",
              "stargazerCount": 3, "forkCount": 1, "primaryLanguage": {"name": "Jupyter Notebook", "color": "#DA5B0B"}},
             {"name": "CodeAlpha_StockPortfolio", "url": "https://github.com/x/z", "description": None,
              "stargazerCount": 0, "forkCount": 0, "primaryLanguage": {"name": "Python", "color": "#3572A5"}}]},
         "repositories": {"totalCount": 18, "nodes": [
             {"stargazerCount": 3, "languages": {"edges": [
                 {"size": 9000, "node": {"name": "Jupyter Notebook", "color": "#DA5B0B"}},
                 {"size": 5000, "node": {"name": "Python", "color": "#3572A5"}},
                 {"size": 2000, "node": {"name": "HTML", "color": "#e34c26"}},
                 {"size": 1500, "node": {"name": "JavaScript", "color": "#f1e05a"}},
                 {"size": 800, "node": {"name": "CSS", "color": "#563d7c"}},
                 {"size": 400, "node": {"name": "Java", "color": "#b07219"}}]}}]}}
    start = dt.date(2025, 9, 1)
    days = [((start + dt.timedelta(i)).isoformat(), 0 if i % 9 == 0 else 2) for i in range(60)]
    return u, days


# ---------------------------------------------------------------- helpers
def svg(w, h, body, title=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>'
            f'<style>text{{font-family:{FONT}}}</style>'
            f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>'
            f'{body}</svg>')


def text(x, y, s, size=14, fill=TEXT, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(str(s))}</text>')


def fmt(n):
    return f"{n:,}"


def short_date(iso):
    return dt.date.fromisoformat(iso).strftime("%b %d, %Y").replace(" 0", " ")


# ---------------------------------------------------------------- streaks
def streaks(days):
    today = dt.date.today().isoformat()
    days = [d for d in days if d[0] <= today]
    total = sum(c for _, c in days)
    longest = (0, None, None)
    run_start, run = None, 0
    for i, (d, c) in enumerate(days):
        if c > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest[0]:
                longest = (run, run_start, d)
        else:
            run = 0
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1                      # today may not have contributions yet
    cur_end, cur = (days[i][0] if i >= 0 else None), 0
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    cur_start = days[i + 1][0] if cur else None
    return total, days[0][0], (cur, cur_start, cur_end), longest


# ---------------------------------------------------------------- cards
def stats_card(u):
    repos = u["repositories"]["nodes"]
    rows = [("Total Stars", sum(r["stargazerCount"] for r in repos)),
            ("Commits (last year)", u["contributionsCollection"]["totalCommitContributions"]),
            ("Pull Requests", u["pullRequests"]["totalCount"]),
            ("Issues", u["issues"]["totalCount"]),
            ("Public Repos", u["repositories"]["totalCount"]),
            ("Followers", u["followers"]["totalCount"])]
    name = u.get("name") or USER
    b = text(25, 38, f"{name}'s GitHub Stats", 18, TITLE, 600)
    for i, (label, val) in enumerate(rows):
        x = 25 if i < 3 else 262
        y = 82 + (i % 3) * 36
        b += f'<circle cx="{x+4}" cy="{y-5}" r="4" fill="{ACCENT}"/>'
        b += text(x + 18, y, label, 14)
        b += text(x + 205, y, fmt(val), 14, TITLE, 700, "end")
    return svg(495, 195, b, "GitHub stats")


def languages_card(u):
    agg = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]
            a = agg.setdefault(n["name"], [0, n["color"] or "#8b949e"])
            a[0] += e["size"]
    top = sorted(agg.items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(v[0] for _, v in top) or 1
    b = text(25, 38, "Top Languages", 18, TITLE, 600)
    b += '<clipPath id="c"><rect x="25" y="55" width="445" height="10" rx="5"/></clipPath><g clip-path="url(#c)">'
    x = 25.0
    for _, (size, color) in top:
        w = 445 * size / total
        b += f'<rect x="{x:.2f}" y="55" width="{w:.2f}" height="10" fill="{color}"/>'
        x += w
    b += "</g>"
    for i, (name, (size, color)) in enumerate(top):
        cx = 25 if i % 2 == 0 else 262
        y = 98 + (i // 2) * 30
        b += f'<circle cx="{cx+5}" cy="{y-5}" r="5" fill="{color}"/>'
        b += text(cx + 18, y, name, 13)
        b += text(cx + 205, y, f"{100*size/total:.1f}%", 13, TITLE, 600, "end")
    return svg(495, 195, b, "Top languages")


def streak_card(days):
    total, first, cur, longest = streaks(days)
    rng = lambda s, e: f"{short_date(s)} - {short_date(e)}" if s and e else "No streak yet"
    today = dt.date.today()
    b = text(82, 88, fmt(total), 30, TITLE, 700, "middle")
    b += text(82, 115, "Total Contributions", 13, TITLE, 400, "middle")
    b += text(82, 140, f"{short_date(first)} - Present", 11, GREEN, 400, "middle")
    b += f'<line x1="165" y1="40" x2="165" y2="155" stroke="{BORDER}" stroke-width="2"/>'
    b += f'<circle cx="247.5" cy="82" r="40" fill="none" stroke="{TITLE}" stroke-width="5"/>'
    b += text(247.5, 92, cur[0], 30, ACCENT, 700, "middle")
    b += text(247.5, 142, "Current Streak", 13, ACCENT, 700, "middle")
    b += text(247.5, 160, rng(cur[1], cur[2]) if cur[0] else today.strftime("%b %d").replace(" 0", " "), 11, GREEN, 400, "middle")
    b += f'<line x1="330" y1="40" x2="330" y2="155" stroke="{BORDER}" stroke-width="2"/>'
    b += text(412, 88, longest[0], 30, TITLE, 700, "middle")
    b += text(412, 115, "Longest Streak", 13, TITLE, 400, "middle")
    b += text(412, 140, rng(longest[1], longest[2]), 11, GREEN, 400, "middle")
    return svg(495, 195, b, "Contribution streak")


def pin_card(r):
    desc = textwrap.wrap(r.get("description") or "No description provided.", 54)
    lines = desc[:2]
    if len(desc) > 2:
        lines[1] = lines[1][:51].rstrip() + "..."
    name = r["name"] if len(r["name"]) <= 34 else r["name"][:31] + "..."
    b = f'<path d="M25 24h6v10h-6z" fill="none"/>'
    b += text(25, 36, name, 17, TITLE, 600)
    for i, ln in enumerate(lines):
        b += text(25, 64 + i * 19, ln, 13)
    lang = r.get("primaryLanguage")
    x = 25
    if lang:
        b += f'<circle cx="{x+5}" cy="103" r="5" fill="{lang["color"] or "#8b949e"}"/>'
        b += text(x + 16, 108, lang["name"], 12)
        x += 30 + len(lang["name"]) * 7
    b += text(x, 108, f"\u2605 {r['stargazerCount']}", 12)
    b += text(x + 50, 108, f"Forks {r['forkCount']}", 12)
    return svg(400, 125, b, r["name"])


# ---------------------------------------------------------------- main
def write(name, content):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)


def update_readme(pins):
    if not os.path.exists(README):
        return
    cards = "\n".join(
        f'<a href="{p["url"]}"><img src="assets/pin-{i}.svg" alt="{escape(p["name"])}" width="400"/></a>'
        for i, p in enumerate(pins, 1))
    block = f'<!--START_SECTION:pinned-->\n<div align="center">\n\n{cards}\n\n</div>\n<!--END_SECTION:pinned-->'
    s = open(README, encoding="utf-8").read()
    new = re.sub(r"<!--START_SECTION:pinned-->.*?<!--END_SECTION:pinned-->", lambda m: block, s, flags=re.S)
    if new != s:
        open(README, "w", encoding="utf-8").write(new)


def main():
    u, days = demo() if "--demo" in sys.argv else fetch()
    write("stats.svg", stats_card(u))
    write("languages.svg", languages_card(u))
    write("streak.svg", streak_card(days))
    pins = u["pinnedItems"]["nodes"][:4]
    for f in os.listdir(OUT) if os.path.isdir(OUT) else []:
        if f.startswith("pin-"):
            os.remove(os.path.join(OUT, f))
    for i, p in enumerate(pins, 1):
        write(f"pin-{i}.svg", pin_card(p))
    update_readme(pins)
    print("cards updated:", len(pins), "pinned repos")


if __name__ == "__main__":
    main()
