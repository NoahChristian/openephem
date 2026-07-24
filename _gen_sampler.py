import base64, io, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from openephem import timeplace as tp, chart as chartmod
from ephemvis import wheel, aspectgrid

r = tp.resolve(date=(1990, 5, 15), time=(14, 30), lat=40.7128, lon=-74.0060, tz="America/New_York")
c = chartmod.assemble(r, house_system="WholeSign", de440="de440.bsp", kernel_dir="./kernels")
nn = c["bodies"].get("TrueNode")
if nn:
    c["bodies"]["SouthNode"] = {"lon": (nn["lon"] + 180.0) % 360.0, "retro": nn.get("retro", False)}

ORDER = [("prism", "Prism"), ("twilight", "Twilight"), ("aurora", "Aurora"), ("opal", "Opal"),
         ("seafoam", "Seafoam"), ("meadow", "Meadow"), ("dawn", "Dawn"), ("blossom", "Blossom"),
         ("infrared", "Infrared"), ("ultraviolet", "Ultraviolet"),
         ("light", "Light"), ("dark", "Dark")]


def _uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


# The preview SVGs are stored RAW (not as <img> data URIs) and injected inline via
# innerHTML, so their <title> hover tooltips work. Thumbnails stay as flat images.
rows = []
for key, label in ORDER:
    wsvg = wheel.render_svg(c, size=800, theme=key, title=None)
    gsvg = aspectgrid.render_aspect_grid_svg(c, theme=key, cell=26)
    pal = wheel.PALETTES[key]
    # tooltip background = the grid's top-right (100%) gradient stop, per-theme reversal
    gwarm, gcool = pal["aHard"], pal["aSoft"]
    if key in aspectgrid._GRID_GRAD_REVERSE:
        gwarm, gcool = gcool, gwarm
    rows.append("  " + json.dumps({
        "key": key, "label": label, "accent": pal["anglelab"], "bg": pal["bg"][0],
        "tip": gcool, "thumb": _uri(wsvg), "wheel": wsvg, "grid": gsvg}, ensure_ascii=False) + ",")
themes_js = "const THEMES=[\n" + "\n".join(rows) + "\n];\n"

HTML = r"""<title>Chart Wheel — Theme Modes</title>
<style>
  :root{--bg:#f4f6fb;--card:#ffffff;--ink:#1e2532;--muted:#6b7280;--line:#e5e8f0;--accent:#4f86c8;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}
  @media (prefers-color-scheme:dark){:root{--bg:#12141a;--card:#1a1d25;--ink:#e6e9f1;--muted:#8b93a5;--line:#2a2e39;--accent:#8fb3e6;}}
  :root[data-theme="dark"]{--bg:#12141a;--card:#1a1d25;--ink:#e6e9f1;--muted:#8b93a5;--line:#2a2e39;--accent:#8fb3e6;}
  :root[data-theme="light"]{--bg:#f4f6fb;--card:#ffffff;--ink:#1e2532;--muted:#6b7280;--line:#e5e8f0;--accent:#4f86c8;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
    padding:clamp(1.4rem,4vw,3rem) clamp(1rem,4vw,2rem);transition:background .4s}
  .head{max-width:56rem;margin:0 auto 1.6rem;text-align:center}
  .eyebrow{margin:0;font-size:.72rem;letter-spacing:.34em;text-transform:uppercase;color:var(--accent);font-weight:700}
  h1{margin:.35rem 0 .5rem;font-family:var(--serif);font-weight:500;font-size:clamp(1.9rem,4.4vw,2.7rem);line-height:1.1}
  .head p{margin:0 auto;color:var(--muted);max-width:40rem;line-height:1.55;font-size:.96rem}
  .stage{max-width:560px;margin:0 auto 1.4rem;background:#fff;border:2px solid var(--accent);
    border-radius:20px;padding:clamp(.8rem,3vw,1.4rem);box-shadow:0 22px 50px -26px rgba(20,25,45,.5);
    transition:background .4s,border-color .4s}
  #preview svg{display:block;width:100%;height:auto;border-radius:8px}
  #preview svg,#preview svg *,#gridimg svg,#gridimg svg *{cursor:default}
  .cap{text-align:center;margin:.6rem 0 0;font-family:var(--serif);font-size:1.15rem;font-weight:600}
  .cap small{font-family:var(--sans);font-weight:400;color:var(--muted);font-size:.8rem;margin-left:.4rem}
  .gridwrap{margin-top:.9rem;padding-top:.9rem;border-top:1px dashed var(--line);text-align:center}
  .gridwrap .lbl{font-size:.68rem;letter-spacing:.24em;text-transform:uppercase;color:var(--muted);margin-bottom:.5rem}
  #gridimg{display:flex;justify-content:center}
  #gridimg svg{max-width:100%;height:auto;border-radius:6px}
  .strip{max-width:60rem;margin:0 auto;display:grid;gap:.9rem;
    grid-template-columns:repeat(auto-fill,minmax(120px,1fr))}
  .tile{cursor:pointer;background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:.4rem .4rem .5rem;font:inherit;color:inherit;text-align:center;transition:transform .15s,box-shadow .15s,border-color .15s}
  .tile:hover{transform:translateY(-2px);box-shadow:0 12px 24px -16px rgba(20,25,45,.5)}
  .tile.on{border-color:var(--a);box-shadow:0 0 0 2px var(--a) inset}
  .tile img{display:block;width:100%;height:auto;border-radius:7px}
  .tile span{display:block;margin-top:.35rem;font-size:.78rem;font-weight:600;letter-spacing:.01em}
  .foot{max-width:56rem;margin:2.2rem auto 0;color:var(--muted);font-size:.82rem;line-height:1.6;
    border-top:1px solid var(--line);padding-top:1.05rem;text-align:center}
  .foot b{color:var(--ink)}
  #tt{position:fixed;z-index:60;pointer-events:none;opacity:0;transition:opacity .1s;
    font:600 12.5px var(--sans);padding:.32rem .55rem;border-radius:8px;white-space:nowrap;
    box-shadow:0 8px 22px -8px rgba(0,0,0,.55);transform:translate(14px,14px)}
</style>
<div class="head">
  <p class="eyebrow">Chart Wheel · Theme Studio</p>
  <h1>Twelve wheel modes</h1>
  <p>Every palette is a real, selectable mode in the engine (<code>render_svg(theme=&hellip;)</code>) and drives the aspectarian too. Click a swatch to switch modes; <b>hover any symbol or aspect cell</b> for its name, sign &amp; degree (e.g. &ldquo;Moon in Pisces at 5.01&deg;&rdquo;). <b>Prism</b> is the current pick; <b>Twilight</b> the runner-up.</p>
</div>
<div class="stage" id="stage">
  <div id="preview"></div><p class="cap" id="cap"></p>
  <div class="gridwrap"><div class="lbl">Aspect grid · hover a cell for its meaning</div><div id="gridimg"></div></div>
</div>
<div class="strip" id="strip"></div>
<div id="tt"></div>
<div class="foot">These are the exact SVGs the engine produces (inlined here so their hover tooltips work) &mdash; same geometry, only the palette changes. The aspectarian is a clean square grid, one glyph per cell, with the theme gradient radiating from the bottom-left corner out to the symbol edge. <b>light</b> and <b>dark</b> are the functional themes; the rest are the &ldquo;pretty&rdquo; family plus the <b>infrared / ultraviolet</b> spectral pair. Say the word to tweak any palette&rsquo;s hues.</div>
<script>
__THEMES__
const strip=document.getElementById('strip'), stage=document.getElementById('stage');
const prev=document.getElementById('preview'), cap=document.getElementById('cap');
const gridimg=document.getElementById('gridimg'), tt=document.getElementById('tt');
let curTip='#333', curInk='#fff';
// pick a readable text colour for a given background
function ink(h){const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);
  return (0.2126*r+0.7152*g+0.0722*b)>150?'#15181f':'#ffffff';}
// move each SVG <title> onto its parent as data-tip (kills the native tooltip)
function enhance(box){box.querySelectorAll('title').forEach(t=>{
  const p=t.parentNode; if(p&&p.nodeType===1&&p!==box)p.setAttribute('data-tip',t.textContent); t.remove();});}
function moved(e){const el=e.target.closest('[data-tip]');
  if(el){tt.textContent=el.getAttribute('data-tip');tt.style.background=curTip;tt.style.color=curInk;
    tt.style.left=e.clientX+'px';tt.style.top=e.clientY+'px';tt.style.opacity='1';}else tt.style.opacity='0';}
function hideTip(){tt.style.opacity='0';}
[prev,gridimg].forEach(box=>{box.addEventListener('mousemove',moved);box.addEventListener('mouseleave',hideTip);});
function sel(i){const t=THEMES[i];
  prev.innerHTML=t.wheel; gridimg.innerHTML=t.grid; enhance(prev); enhance(gridimg);
  curTip=t.tip; curInk=ink(t.tip); hideTip();
  cap.innerHTML=t.label+' <small>theme="'+t.key+'"</small>';
  stage.style.background=t.bg; stage.style.borderColor=t.accent;
  [...strip.children].forEach((el,j)=>el.classList.toggle('on',j===i));}
THEMES.forEach((t,i)=>{const b=document.createElement('button');b.className='tile';
  b.style.setProperty('--a',t.accent);
  b.innerHTML='<img src="'+t.thumb+'" alt="'+t.label+'"><span>'+t.label+'</span>';
  b.onclick=()=>sel(i); strip.appendChild(b);});
sel(0);
</script>
"""

out = HTML.replace("__THEMES__", themes_js)
SCR = r"C:\Users\noahc\AppData\Local\Temp\claude\C--Users-noahc-ElpisWeb\3e9d2450-76d2-4623-a9f8-8dd80a39762b\scratchpad"
open(SCR + r"\palette_board.html", "w", encoding="utf-8").write(out)
print("wrote palette_board.html", len(out), "bytes;", len(rows), "themes")
