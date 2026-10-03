#!/usr/bin/env python3
"""Generate an isometric 3D GitHub contribution matrix as a standalone SVG.

Usage:
    python scripts/contribution_matrix.py            # writes assets/contribution-matrix.svg

Env vars:
    GH_USER   GitHub username              (default: Anupam2400)
    OUT       output path                  (default: assets/contribution-matrix.svg)
    GH_TOKEN  / GITHUB_TOKEN  optional; uses the GraphQL API when present,
              otherwise falls back to scraping the public contribution calendar.

No third-party packages needed (standard library only).
"""
import datetime as dt
import html
import json
import os
import re
import urllib.request

USER = os.environ.get("GH_USER", "Anupam2400")
OUT = os.environ.get("OUT", "assets/contribution-matrix.svg")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
UA = {"User-Agent": "Mozilla/5.0 (contribution-matrix)"}


# --------------------------------------------------------------------------- data
def fetch_graphql(user, token):
    """Exact daily counts via the GraphQL API."""
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start = now - dt.timedelta(days=364)
    query = """query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){contributionsCollection(from:$from,to:$to){
        contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    body = json.dumps({"query": query, "variables": {
        "login": user, "from": start.isoformat(), "to": now.isoformat()}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={**UA, "Authorization": f"bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def fetch_scrape(user):
    """No-token fallback: parse the public contribution calendar fragment."""
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    cells = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"\s+id="(contribution-day-component-\d+-\d+)"', page)
    tips = {}
    for cid, text in re.findall(r'for="(contribution-day-component-\d+-\d+)"[^>]*>\s*([^<]*)', page):
        m = re.match(r"(\d+) contribution", text.strip())
        tips[cid] = int(m.group(1)) if m else 0
    return {date: tips.get(cid, 0) for date, cid in cells}


def load_counts():
    if TOKEN:
        try:
            return fetch_graphql(USER, TOKEN)
        except Exception as exc:  # fall back rather than fail the workflow
            print(f"GraphQL failed ({exc}); falling back to scrape")
    return fetch_scrape(USER)


# --------------------------------------------------------------------------- layout
def build_weeks(counts):
    """Return list of weeks (Sun..Sat); each day is (date, count) or None."""
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    weeks, cur = [], start
    while cur <= today:
        week = []
        for i in range(7):
            day = cur + dt.timedelta(days=i)
            week.append((day, counts.get(day.isoformat(), 0)) if day <= today else None)
        weeks.append(week)
        cur += dt.timedelta(days=7)
    return weeks


# level -> (top, front, side)
PALETTE = [
    ("#0f2a1c", "#0a1a12", "#07120d"),
    ("#1f7a45", "#0f5132", "#0a3b25"),
    ("#22a05b", "#11703f", "#0c5530"),
    ("#2fc873", "#158a4d", "#0e6c3b"),
    ("#4ade80", "#1fae5e", "#14864a"),
    ("#bbf7d0", "#4ade80", "#22a05b"),
]


def level(count, peak):
    if count <= 0 or peak <= 0:
        return 0
    r = count / peak
    return 1 if r <= .2 else 2 if r <= .4 else 3 if r <= .6 else 4 if r <= .8 else 5


def bar(x, yb, h, bw, dx, dy, pal, extra=""):
    top, front, side = pal
    f = f'<rect x="{x:.1f}" y="{yb - h:.1f}" width="{bw}" height="{h:.1f}" fill="{front}"/>'
    s = (f'<polygon points="{x + bw:.1f},{yb:.1f} {x + bw + dx:.1f},{yb + dy:.1f} '
         f'{x + bw + dx:.1f},{yb + dy - h:.1f} {x + bw:.1f},{yb - h:.1f}" fill="{side}"/>')
    t = (f'<polygon points="{x:.1f},{yb - h:.1f} {x + dx:.1f},{yb - h + dy:.1f} '
         f'{x + bw + dx:.1f},{yb - h + dy:.1f} {x + bw:.1f},{yb - h:.1f}" fill="{top}"/>')
    return f"<g{extra}>{f}{s}{t}</g>"


# --------------------------------------------------------------------------- render
def render(weeks):
    W, H = 900, 380
    gx, gy, cw, rh, bw, dx, dy = 72, 178, 13.4, 13.0, 10.2, 4.5, -3.5
    flat = [d for w in weeks for d in w if d]
    total = sum(c for _, c in flat)
    active = sum(1 for _, c in flat if c > 0)
    peak = max((c for _, c in flat), default=0)

    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-label="GitHub contribution matrix for {html.escape(USER)}: {total} contributions, '
      f'{active} active days, peak {peak}">')
    a('<defs>'
      '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#03120b"/>'
      '<stop offset=".55" stop-color="#020a06"/><stop offset="1" stop-color="#010403"/></linearGradient>'
      '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
      '<filter id="frameglow" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="3" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
      '</defs>')
    a(f'<rect width="{W}" height="{H}" fill="#000"/>')
    a(f'<rect x="8" y="8" width="{W - 16}" height="{H - 16}" rx="22" fill="url(#bg)" '
      f'stroke="#22c55e" stroke-opacity=".85" stroke-width="1.4" filter="url(#frameglow)"/>')

    mono = "font-family=\"'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace\""
    a(f'<g {mono}>')
    a('<text x="30" y="50" font-size="20" font-weight="700" fill="#4ade80" letter-spacing="1">'
      '&gt; GITHUB :: CONTRIBUTION MATRIX</text>')
    a('<text x="30" y="70" font-size="9.5" fill="#3f7f55" letter-spacing="1.5">DAILY CONTRIBUTION ACTIVITY</text>')
    a(f'<line x1="30" y1="84" x2="{W - 30}" y2="84" stroke="#14532d" stroke-opacity=".7"/>')

    for x, label, val in ((600, "TOTAL", total), (676, "ACTIVE DAYS", active), (766, "PEAK", peak)):
        a(f'<text x="{x}" y="42" font-size="8" fill="#3f7f55" letter-spacing="1">{label}</text>')
        a(f'<text x="{x}" y="62" font-size="15" font-weight="700" fill="#86efac">{val}</text>')
    a('<circle cx="848" cy="52" r="8" fill="#052e16" stroke="#14532d"/>'
      '<circle cx="848" cy="52" r="4" fill="#4ade80" filter="url(#glow)">'
      '<animate attributeName="opacity" values="1;.3;1" dur="2.2s" repeatCount="indefinite"/></circle>'
      '<text x="860" y="55" font-size="7.5" fill="#3f7f55" letter-spacing="1">LIVE</text>')

    # floor grid (fake perspective)
    for i, y in enumerate((280, 296, 312, 328)):
        a(f'<line x1="{60 + i * 6}" y1="{y}" x2="{W - 60 - i * 6}" y2="{y}" stroke="#22c55e" stroke-opacity=".07"/>')
    for x in range(100, 801, 100):
        a(f'<line x1="{x}" y1="280" x2="{450 + (x - 450) * 1.15:.0f}" y2="330" stroke="#22c55e" stroke-opacity=".05"/>')

    # month labels
    last_x, prev_month = -99, None
    for wi, week in enumerate(weeks):
        mid = week[3] or next((d for d in week if d), None)  # mid-week day decides the month
        if not mid:
            continue
        day = mid[0]
        key = (day.year, day.month)
        x = gx + wi * cw
        if key != prev_month and x - last_x >= 46:
            a(f'<text x="{x:.1f}" y="108" font-size="8.5" fill="#6fae85">{day.year}-{day.month:02d}</text>')
            last_x = x
        prev_month = key

    for d, name in ((1, "MON"), (3, "WED"), (5, "FRI")):
        a(f'<text x="{gx - 10}" y="{gy + d * rh - 1}" font-size="8" fill="#3f7f55" text-anchor="end">{name}</text>')

    # bars: back rows first, then left->right
    for d in range(7):
        yb = gy + d * rh
        for wi, week in enumerate(weeks):
            cell = week[d]
            if not cell:
                continue
            _, c = cell
            lv = level(c, peak)
            h = 1.6 if c == 0 else 6 + (c / peak) ** 0.75 * 44
            extra = ' filter="url(#glow)"' if lv == 5 else ""
            a(bar(gx + wi * cw, yb, h, bw, dx, dy, PALETTE[lv], extra))

    # footer
    a(f'<text x="30" y="{H - 28}" font-size="8" fill="#3f7f55" letter-spacing="1">'
      f'GITHUB CONTRIBUTION DATA · UPDATED {dt.date.today().isoformat()}</text>')
    a(f'<text x="{W / 2}" y="{H - 28}" font-size="8" fill="#3f7f55" letter-spacing="1" text-anchor="middle">'
      'ISOMETRIC 3D VISUALIZATION</text>')
    a(f'<text x="{W - 214}" y="{H - 28}" font-size="8" fill="#6fae85" letter-spacing="1">LESS</text>')
    for i, pal in enumerate(PALETTE):
        a(f'<rect x="{W - 182 + i * 14}" y="{H - 36}" width="9" height="9" rx="1" fill="{pal[1] if i else pal[0]}"/>')
    a(f'<text x="{W - 90}" y="{H - 28}" font-size="8" fill="#6fae85" letter-spacing="1">MORE</text>')
    a('</g></svg>')
    return "\n".join(o)


def main():
    counts = load_counts()
    svg = render(build_weeks(counts))
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {OUT} ({sum(counts.values())} contributions, {len(counts)} days)")


if __name__ == "__main__":
    main()
