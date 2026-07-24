import io, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from openephem import timeplace as tp, chart as chartmod
from ephemvis import wheel, render_aspect_grid_svg

resolved = tp.resolve(
    date=(1990, 5, 15), time=(14, 30),
    lat=40.7128, lon=-74.0060, tz="America/New_York",
)
c = chartmod.assemble(resolved, house_system="WholeSign",
                      de440="de440.bsp", kernel_dir="./kernels")

# South Node = point opposite the North Node
_nn = c["bodies"].get("TrueNode") or c["bodies"].get("MeanNode")
if _nn:
    c["bodies"]["SouthNode"] = {"lon": (_nn["lon"] + 180.0) % 360.0,
                                "retro": _nn.get("retro", False)}

svg = wheel.render_svg(c, size=800, theme="prism", title=None)

# report whole-sign house of each body so the key badges can be corrected
_cusps = c["cusps"]
def _house_of(lon):
    for i in range(12):
        span = (_cusps[(i + 1) % 12] - _cusps[i]) % 360.0
        if span == 0 or (lon - _cusps[i]) % 360.0 < span:
            return i + 1
    return 12
print("ASC", round(c["angles"]["asc"], 2), "MC", round(c["angles"]["mc"], 2))
for _name, _b in c["bodies"].items():
    print(f"{_name:11s} {_b['lon'] % 30:5.2f}  house {_house_of(_b['lon'])}")

SCR = r"C:\Users\noahc\AppData\Local\Temp\claude\C--Users-noahc-ElpisWeb\3e9d2450-76d2-4623-a9f8-8dd80a39762b\scratchpad"
# standalone page for rasterizing (keeps the white bg rect)
wrap = ('<!doctype html><meta charset="utf-8"><style>'
        ':root{--brass:#9c7518;'
        '--serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif}'
        'html,body{margin:0;padding:0;background:#fff}svg{display:block}'
        'svg .anglelab{fill:var(--brass);font-family:var(--serif);'
        'font-weight:600;font-size:20px;letter-spacing:.02em}</style>' + svg)
open(SCR + r"\_wrap.html", "w", encoding="utf-8").write(wrap)

# inject into the artifact page: strip bg rect, aria-label "natal chart"
inj = re.sub(r'<rect[^>]*class="bg"[^>]*/>\s*', '', svg)
inj = re.sub(r'aria-label="[^"]*"', 'aria-label="natal chart"', inj, count=1).strip()
ART = SCR + r"\chart.html"
html = open(ART, encoding="utf-8").read()
new_html = re.sub(r'<svg xmlns="http://www\.w3\.org/2000/svg".*?</svg>',
                  inj, html, count=1, flags=re.DOTALL)
assert inj in new_html, "svg injection failed"

# --- aspect grid (triangular aspectarian), rendered by ephemvis as SVG ---
grid_svg = render_aspect_grid_svg(c, theme="prism", cell=30)
new_html = re.sub(r'<!--AG-->.*?<!--/AG-->',
                  lambda m: '<!--AG-->' + grid_svg + '<!--/AG-->',
                  new_html, count=1, flags=re.DOTALL)
assert 'aria-label="aspect grid"' in new_html, "aspect-grid injection failed"

open(ART, "w", encoding="utf-8").write(new_html)
print("bodies:", len(c["bodies"]), "| aspects:", len(c["aspects"]), "| injected OK")
