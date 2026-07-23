#!/usr/bin/env python3
"""
wheel.py — render a natal chart as a self-contained SVG wheel.  [SHIP]

Pure Python, zero dependencies. Takes the dict from chart.assemble() (or any dict
with the same shape) and returns an SVG string. Ascendant is placed at the left
(9 o'clock) with the zodiac increasing counter-clockwise — the standard chart
convention. Theme-aware (light/dark) via a CSS block.

Glyphs are standard Unicode astrological symbols (no font-licensing issue); if a
viewer's font lacks them, pass text_labels=True for 2-3 letter abbreviations.
"""

from __future__ import annotations

import math

SIGN_GLYPHS = ["♈", "♉", "♊", "♋", "♌", "♍",
               "♎", "♏", "♐", "♑", "♒", "♓"]
SIGN_ABBR = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"]

PLANET_GLYPHS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀",
    "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅",
    "Neptune": "♆", "Pluto": "♇", "TrueNode": "☊", "MeanNode": "☊",
    "MeanLilith": "⚸", "OscuLilith": "⚸", "Chiron": "⚷",
    "Ceres": "⚳", "Pallas": "⚴", "Juno": "⚵", "Vesta": "⚶",
}
PLANET_ABBR = {k: (k[:2] if k not in ("Sun", "Moon") else k[:2]) for k in PLANET_GLYPHS}

# Aspect line styling (color, dash). Class names keyed for the CSS block.
ASPECT_STYLE = {
    "conjunction": ("#8a8a8a", ""),
    "opposition": ("#d7263d", ""),
    "square": ("#d7263d", ""),
    "trine": ("#1f7a8c", ""),
    "sextile": ("#1f7a8c", "4 3"),
    "quincunx": ("#3f8f3f", "2 3"),
    "semisextile": ("#3f8f3f", "2 3"),
    "semisquare": ("#c08a2e", "2 3"),
    "sesquiquadrate": ("#c08a2e", "2 3"),
    "quintile": ("#7a4fb0", "2 3"),
}


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_svg(chart: dict, size: int = 760, theme: str = "auto",
               text_labels: bool = False, title: str | None = None) -> str:
    cx = cy = size / 2.0
    r_out = size * 0.47              # outer edge
    r_zod_in = r_out * 0.86          # inner edge of the zodiac band
    r_house = r_zod_in               # house-wheel outer edge
    r_planet = r_zod_in * 0.82       # ring the glyphs sit on
    r_hub = r_planet * 0.70          # aspect hub radius
    glyphs = None if not text_labels else True

    angles = chart.get("angles") or {}
    asc = angles.get("asc", 0.0)     # unknown-time -> 0 Aries at left
    cusps = chart.get("cusps")

    def pol(r, lon):
        """Ecliptic longitude -> (x, y). Asc at left, zodiac CCW."""
        a = math.radians(180.0 + (lon - asc))
        return cx + r * math.cos(a), cy - r * math.sin(a)

    P = []  # svg fragments
    P.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
             f'width="{size}" height="{size}" role="img" '
             f'aria-label="{_esc(title or "natal chart")}">')
    P.append(_css(theme))
    P.append(f'<rect x="0" y="0" width="{size}" height="{size}" class="bg"/>')

    # --- rings ---
    for r in (r_out, r_zod_in, r_planet, r_hub):
        P.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" class="ring"/>')

    # --- zodiac: 12 sectors (fixed to longitude) ---
    for i in range(12):
        lon0 = i * 30.0
        x1, y1 = pol(r_zod_in, lon0)
        x2, y2 = pol(r_out, lon0)
        P.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="tick"/>')
        gx, gy = pol((r_zod_in + r_out) / 2.0, lon0 + 15.0)
        label = SIGN_ABBR[i] if glyphs else SIGN_GLYPHS[i]
        P.append(f'<text x="{gx:.1f}" y="{gy:.1f}" class="sign" '
                 f'dominant-baseline="central" text-anchor="middle">{label}</text>')

    # --- houses ---
    if cusps and len(cusps) >= 12:
        for i, c in enumerate(cusps):
            x1, y1 = pol(r_hub, c)
            x2, y2 = pol(r_house, c)
            cls = "cusp-angle" if i in (0, 3, 6, 9) else "cusp"
            P.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}"/>')
            mid = c + (((cusps[(i + 1) % 12] - c) % 360.0) / 2.0)
            nx, ny = pol(r_hub * 1.08, mid)
            P.append(f'<text x="{nx:.1f}" y="{ny:.1f}" class="housenum" '
                     f'dominant-baseline="central" text-anchor="middle">{i + 1}</text>')
        # Asc / MC labels
        for key, lab in (("asc", "AC"), ("mc", "MC")):
            if key in angles:
                lx, ly = pol(r_out * 0.99, angles[key])
                P.append(f'<text x="{lx:.1f}" y="{ly:.1f}" class="anglelab" '
                         f'dominant-baseline="central" text-anchor="middle">{lab}</text>')

    # --- planets (with simple angular de-collision on the display ring) ---
    bodies = chart.get("bodies") or {}
    placed = _spread([(n, b["lon"]) for n, b in bodies.items()], min_gap=7.0)
    hub_pts = {}
    for name, lon, disp in placed:
        # tick from zodiac to planet ring at true longitude
        tx1, ty1 = pol(r_planet, lon)
        tx2, ty2 = pol(r_house, lon)
        P.append(f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" class="pmark"/>')
        gx, gy = pol(r_planet * 0.93, disp)
        g = (PLANET_ABBR.get(name, name[:2]) if glyphs else PLANET_GLYPHS.get(name, name[:2]))
        retro = bodies[name].get("retro")
        P.append(f'<text x="{gx:.1f}" y="{gy:.1f}" class="planet" '
                 f'dominant-baseline="central" text-anchor="middle">{_esc(g)}</text>')
        dx, dy = pol(r_planet * 0.80, disp)
        deg = f'{int(bodies[name]["lon"] % 30)}°' + ("℞" if retro else "")
        P.append(f'<text x="{dx:.1f}" y="{dy:.1f}" class="deg" '
                 f'dominant-baseline="central" text-anchor="middle">{deg}</text>')
        hub_pts[name] = pol(r_hub, lon)

    # --- aspects (lines across the hub) ---
    for asp in chart.get("aspects") or []:
        a, b = asp.get("a"), asp.get("b")
        if a in hub_pts and b in hub_pts:
            color, dash = ASPECT_STYLE.get(asp.get("aspect"), ("#999", "2 3"))
            (x1, y1), (x2, y2) = hub_pts[a], hub_pts[b]
            da = f' stroke-dasharray="{dash}"' if dash else ""
            P.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="{color}" class="aspect"{da}/>')

    if title:
        P.append(f'<text x="{cx:.1f}" y="{size*0.04:.1f}" class="title" '
                 f'text-anchor="middle">{_esc(title)}</text>')
    P.append('</svg>')
    return "\n".join(P)


def _spread(items, min_gap=7.0):
    """De-collide glyph display angles: keep true longitude for the mark, but
    nudge the glyph position so neighbours don't overlap. Returns (name,lon,disp)."""
    items = sorted(items, key=lambda t: t[1])
    disp = [lon for _, lon in items]
    n = len(disp)
    for _ in range(40):  # relaxation passes
        moved = False
        for i in range(n):
            j = (i + 1) % n
            gap = (disp[j] - disp[i]) % 360.0
            if 0 < gap < min_gap:
                push = (min_gap - gap) / 2.0
                disp[i] = (disp[i] - push) % 360.0
                disp[j] = (disp[j] + push) % 360.0
                moved = True
        if not moved:
            break
    return [(items[i][0], items[i][1], disp[i]) for i in range(n)]


def _css(theme: str) -> str:
    base = """
    <style>
    .bg{fill:#ffffff}
    .ring{fill:none;stroke:#c9c9c9;stroke-width:1}
    .tick{stroke:#c9c9c9;stroke-width:1}
    .sign{fill:#444;font:600 20px system-ui,sans-serif}
    .cusp{stroke:#e0e0e0;stroke-width:1}
    .cusp-angle{stroke:#9a9a9a;stroke-width:1.6}
    .housenum{fill:#999;font:11px system-ui,sans-serif}
    .anglelab{fill:#333;font:700 12px system-ui,sans-serif}
    .pmark{stroke:#bdbdbd;stroke-width:1}
    .planet{fill:#111;font:600 20px system-ui,sans-serif}
    .deg{fill:#666;font:9px system-ui,sans-serif}
    .aspect{stroke-width:1.1;fill:none;opacity:.8}
    .title{fill:#222;font:600 15px system-ui,sans-serif}
    </style>"""
    dark = """
    <style>
    @media (prefers-color-scheme: dark){
      .bg{fill:#14161a}.ring,.tick{stroke:#3a3f47}.sign{fill:#c9cdd4}
      .cusp{stroke:#2a2e35}.cusp-angle{stroke:#6a7280}.housenum{fill:#7a828c}
      .anglelab{fill:#d5d9df}.pmark{stroke:#454b54}.planet{fill:#f2f4f7}
      .deg{fill:#9aa1ab}.title{fill:#e6e9ee}
    }</style>"""
    if theme == "light":
        return base
    if theme == "dark":
        return base + dark.replace("@media (prefers-color-scheme: dark){", ":root{").rstrip("}\n ") + "}</style>"
    return base + dark  # auto


if __name__ == "__main__":
    import houses
    # Real analytic houses (no skyfield) + a few mock planets, to a file.
    h = houses.houses_from_jd(2448027.270833, 40.7128, -74.0060, "Placidus")
    demo = {
        "angles": {"asc": h.asc, "mc": h.mc, "vertex": h.vertex, "east_point": h.east_point},
        "cusps": h.cusps,
        "bodies": {
            "Sun": {"lon": 54.6, "retro": False}, "Moon": {"lon": 300.2, "retro": False},
            "Mercury": {"lon": 47.1, "retro": True}, "Venus": {"lon": 78.0, "retro": False},
            "Mars": {"lon": 300.9, "retro": False}, "Saturn": {"lon": 293.4, "retro": False},
        },
        "aspects": [
            {"a": "Sun", "b": "Mercury", "aspect": "conjunction", "orb": 7.5},
            {"a": "Moon", "b": "Saturn", "aspect": "conjunction", "orb": 6.8},
            {"a": "Sun", "b": "Moon", "aspect": "trine", "orb": -5.6},
        ],
    }
    svg = render_svg(demo, title="Demo Chart")
    with open("demo_chart.svg", "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote demo_chart.svg ({len(svg)} bytes); asc={h.asc:.2f} mc={h.mc:.2f}")
