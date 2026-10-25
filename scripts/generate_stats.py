#!/usr/bin/env python3
"""Draw the profile stats as SVGs inside this repo. Standard library only.

Runs in GitHub Actions with GITHUB_TOKEN (GraphQL). With no token it falls back to
public pages so you can preview locally:  python3 scripts/generate_stats.py Andrew190707
Output: gen/{stats,streak,langs,year}-{dark,light}.svg
"""
import datetime as dt
import html
import json
import math
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgkit import DAY_RAMP, ROOT, basic_faces, esc, svg  # noqa: E402

LOGIN = os.environ.get("GH_LOGIN") or (sys.argv[1] if len(sys.argv) > 1 else "Andrew190707")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
W = 800

# Trap 1: pin the window to whole UTC days so two runs minutes apart agree.
TODAY = dt.datetime.now(dt.timezone.utc).date()
if os.environ.get("GEN_TODAY"):
    TODAY = dt.date.fromisoformat(os.environ["GEN_TODAY"])
START = TODAY - dt.timedelta(days=364)


# ---------------------------------------------------------------- fetching
def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    req.add_header("User-Agent", "profile-stats")
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode()


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    out = json.loads(http("https://api.github.com/graphql", body, {
        "Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}))
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


CAL_Q = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
 contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
LANG_Q = """query($login:String!){user(login:$login){createdAt
 repositories(first:100,privacy:PUBLIC,ownerAffiliations:OWNER,isFork:false){nodes{name
  languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""


def years_from(first_year):
    return range(first_year, TODAY.year + 1)


def days_graphql():
    created = gql(LANG_Q, {"login": LOGIN})["user"]["createdAt"]
    days = {}
    for y in years_from(int(created[:4])):
        a = dt.date(y, 1, 1)
        b = min(dt.date(y, 12, 31), TODAY)
        d = gql(CAL_Q, {"login": LOGIN, "from": f"{a}T00:00:00Z", "to": f"{b}T23:59:59Z"})
        for w in d["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for x in w["contributionDays"]:
                days[x["date"]] = x["contributionCount"]
    return days


def days_public():
    days = {}
    for y in years_from(TODAY.year - 2):
        a, b = dt.date(y, 1, 1), min(dt.date(y, 12, 31), TODAY)
        page = http(f"https://github.com/users/{LOGIN}/contributions?from={a}&to={b}")
        ids = dict(re.findall(r'data-date="(\d{4}-\d\d-\d\d)" id="([^"]+)"', page))
        tips = dict(re.findall(r'for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page))
        for date, i in ids.items():
            m = re.match(r"(\d+) contribution", html.unescape(tips.get(i, "")))
            days[date] = int(m.group(1)) if m else 0
    return days


def langs_graphql():
    nodes = gql(LANG_Q, {"login": LOGIN})["user"]["repositories"]["nodes"]
    size, repos = {}, {}
    for n in nodes:
        for e in n["languages"]["edges"]:
            k = e["node"]["name"]
            size[k] = size.get(k, 0) + e["size"]
            repos[k] = repos.get(k, 0) + 1
    return size, repos


def langs_public():
    page = http(f"https://github.com/{LOGIN}?tab=repositories")
    size, repos = {}, {}
    for blk in page.split('itemprop="name codeRepository"')[1:]:
        blk = blk.split('itemprop="name codeRepository"')[0]
        if "Forked from" in blk:
            continue
        m = re.search(r'itemprop="programmingLanguage">([^<]+)', blk)
        if m:
            k = m.group(1).strip()
            size[k] = size.get(k, 0) + 1          # no byte counts without the API
            repos[k] = repos.get(k, 0) + 1
    return size, repos


# ---------------------------------------------------------------- numbers
def fmt_date(d):
    return d.strftime("%b ") + str(d.day)


def fmt_range(a, b):
    if a is None:
        return "no streak yet"
    y = f", {b.year}"
    return f"{fmt_date(a)} – {fmt_date(b)}{y}" if a != b else f"{fmt_date(a)}{y}"


def streaks(days):
    ds = sorted(days)
    longest = (0, None, None)
    run, run_start, prev = 0, None, None
    for k in ds:
        d = dt.date.fromisoformat(k)
        if days[k] > 0:
            if prev is not None and (d - prev).days == 1 and run > 0:
                run += 1
            else:
                run, run_start = 1, d
            if run > longest[0]:
                longest = (run, run_start, d)
        else:
            run = 0
        prev = d
    # current: walk back from today; an empty *today* doesn't break it yet
    cur, end, d = 0, None, TODAY
    if days.get(str(d), 0) == 0:
        d -= dt.timedelta(days=1)
    while days.get(str(d), 0) > 0:
        cur += 1
        end = end or d
        d -= dt.timedelta(days=1)
    cur_start = end - dt.timedelta(days=cur - 1) if cur else None
    return (cur, cur_start, end), longest


def window(days):
    out = []
    d = START
    while d <= TODAY:
        out.append((d, days.get(str(d), 0)))
        d += dt.timedelta(days=1)
    return out


# ---------------------------------------------------------------- drawing
def r2(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def draw_hero(days, theme):
    win = window(days)
    total = sum(c for _, c in win)
    active = sum(1 for _, c in win if c)
    weeks = [sum(c for _, c in win[i:i + 7]) for i in range(0, len(win), 7)]
    best_week = max(weeks) if weeks else 0
    best_day = max((c for _, c in win), default=0)
    x0, x1, y0, y1 = 340, 776, 34, 116
    top = max(max(weeks), 1)
    pts = []
    for i, v in enumerate(weeks):
        x = x0 + (x1 - x0) * i / max(len(weeks) - 1, 1)
        y = y1 - (y1 - y0) * v / top
        pts.append((x, y))
    line = " ".join(f"{r2(x)},{r2(y)}" for x, y in pts)
    area = f"{r2(x0)},{y1} {line} {r2(x1)},{y1}"
    body = (
        '<text x="24" y="34" font-size="12" class="dim">contributions · last 12 months</text>'
        f'<text x="22" y="100" font-size="64" class="b acc">{total:,}</text>'
        f'<text x="24" y="134" font-size="12" class="dim">{active} active days · best week {best_week} · best day {best_day}</text>'
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" class="rule"/>'
        f'<polygon points="{area}" class="area"/>'
        f'<polyline points="{line}" class="spark" fill="none"/>'
        f'<circle cx="{r2(pts[-1][0])}" cy="{r2(pts[-1][1])}" r="3" class="dot"/>'
        f'<text x="{x0}" y="136" font-size="11" class="dim">{fmt_date(START)}</text>'
        f'<text x="{x1}" y="136" font-size="11" class="dim" text-anchor="end">{fmt_date(TODAY)}</text>'
    )
    return svg(W, 150, body, basic_faces(), theme, css_for(theme), "Contributions, last 12 months")


def draw_streak(days, theme):
    cur, lon = streaks(days)
    cols = [(24, "current streak", cur), (424, "longest streak", lon)]
    body = ""
    for x, label, (n, a, b) in cols:
        body += (
            f'<text x="{x}" y="30" font-size="12" class="dim">{label}</text>'
            f'<text x="{x - 2}" y="82" font-size="48" class="b">{n}</text>'
            f'<text x="{x + 29 * len(str(n)) + 10}" y="82" font-size="14" class="dim">days</text>'
            f'<text x="{x}" y="108" font-size="12" class="dim">{esc(fmt_range(a, b))}</text>'
        )
    body += f'<line x1="400" y1="20" x2="400" y2="108" class="rule"/>'
    return svg(W, 124, body, basic_faces(), theme, css_for(theme), "Contribution streaks")


def draw_langs(size, repos, theme):
    top = sorted(size.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    total = sum(size.values()) or 1
    mx = top[0][1] if top else 1
    body = '<text x="24" y="28" font-size="12" class="dim">top languages · public repos</text>'
    for i, (k, v) in enumerate(top):
        y = 62 + i * 30
        bw = max(3, 330 * v / mx)
        body += (
            f'<text x="24" y="{y}" font-size="13">{esc(k)}</text>'
            f'<rect x="170" y="{y - 9}" width="{r2(bw)}" height="9" class="bar"/>'
            f'<text x="600" y="{y}" font-size="13" class="b" text-anchor="end">{100 * v / total:.1f}%</text>'
            f'<text x="776" y="{y}" font-size="12" class="dim" text-anchor="end">{repos.get(k, 0)} repo{"s" if repos.get(k, 0) != 1 else ""}</text>'
        )
    h = 62 + max(len(top), 1) * 30 - 6
    return svg(W, h, body, basic_faces(), theme, css_for(theme), "Top languages")


def draw_year(days, theme):
    win = window(days)
    nz = sorted(c for _, c in win if c)

    def level(c):
        if c == 0:
            return 0
        rank = sum(1 for v in nz if v <= c) / len(nz)          # quantile of busy days
        return 1 + min(7, int(rank * 8 - 1e-9))

    first_dow = (START.weekday() + 1) % 7                      # Sunday-first columns
    cw, ch, ox, oy = 14.2, 17, 40, 40
    body = ""
    last_m = None
    for i, (d, c) in enumerate(win):
        col, row = (i + first_dow) // 7, (i + first_dow) % 7
        x, y = ox + col * cw, oy + row * ch
        body += f'<text x="{r2(x)}" y="{y}" font-size="12.9" class="{"dim" if c == 0 else ""}">{DAY_RAMP[level(c)]}</text>'
        if d.day <= 7 and row == 0 and d.month != last_m:
            body += f'<text x="{r2(x)}" y="22" font-size="11" class="dim">{d.strftime("%b").lower()}</text>'
            last_m = d.month
    for row, lab in ((1, "mon"), (3, "wed"), (5, "fri")):
        body += f'<text x="0" y="{oy + row * ch}" font-size="11" class="dim">{lab}</text>'
    ly = oy + 7 * ch + 14
    body += f'<text x="{ox}" y="{ly}" font-size="11" class="dim">less</text>'
    for j, ch_ in enumerate(DAY_RAMP):
        body += f'<text x="{ox + 36 + j * 11}" y="{ly}" font-size="12.9">{ch_}</text>'
    body += f'<text x="{ox + 36 + len(DAY_RAMP) * 11 + 6}" y="{ly}" font-size="11" class="dim">more</text>'
    return svg(W, ly + 12, body, basic_faces(), theme, css_for(theme), "Contributions, one character per day")


def css_for(theme):
    from svgkit import THEMES
    t = THEMES[theme]
    return (f".rule{{stroke:{t['rule']};stroke-width:1}}.area{{fill:{t['accent']};opacity:.14}}"
            f".spark{{stroke:{t['accent']};stroke-width:1.6;stroke-linejoin:round}}"
            f".dot{{fill:{t['accent']}}}.bar{{fill:{t['accent']}}}")


def main():
    out = os.path.join(ROOT, "gen")
    os.makedirs(out, exist_ok=True)
    if TOKEN:
        days, (size, repos) = days_graphql(), langs_graphql()
    else:
        print("no GITHUB_TOKEN: using public pages (preview mode)")
        days, (size, repos) = days_public(), langs_public()
    for theme in ("dark", "light"):
        for name, fn in (("stats", lambda t: draw_hero(days, t)), ("streak", lambda t: draw_streak(days, t)),
                         ("langs", lambda t: draw_langs(size, repos, t)), ("year", lambda t: draw_year(days, t))):
            path = os.path.join(out, f"{name}-{theme}.svg")
            new = fn(theme)
            old = open(path).read() if os.path.exists(path) else None
            if old != new:
                open(path, "w").write(new)
    print("window", START, "->", TODAY, "| days:", len(days), "| langs:", dict(size))


if __name__ == "__main__":
    main()
