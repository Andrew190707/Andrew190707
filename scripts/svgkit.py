"""Shared helpers: themes, font embedding, SVG wrapper. Standard library only."""
import base64
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")

THEMES = {
    "dark": dict(fg="#e6edf3", dim="#7d8590", rule="#30363d", accent="#58a6ff"),
    "light": dict(fg="#1f2328", dim="#656d76", rule="#d0d7de", accent="#0969da"),
}

RAMP = " .`:-=+*cs#%@"          # 13 levels, blank -> dense
DAY_RAMP = ".:-=+*#%@"           # year grid: zero day is '.', never blank

CHAR_ADV = 0.600                 # JetBrains Mono advance, in em


def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def font_face(family, woff2_b64, weight=400):
    return (
        f"@font-face{{font-family:'{family}';font-weight:{weight};"
        f"src:url(data:font/woff2;base64,{woff2_b64}) format('woff2');}}"
    )


def basic_faces():
    """Basic-latin subsets, committed in the repo (regular + bold)."""
    return font_face("JBM", b64(os.path.join(FONTS, "jbm-400.woff2")), 400) + font_face(
        "JBM", b64(os.path.join(FONTS, "jbm-700.woff2")), 700
    )


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(width, height, body, faces, theme, extra_css="", title=""):
    t = THEMES[theme]
    css = (
        faces
        + f"text{{font-family:'JBM','JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;"
        f"fill:{t['fg']};white-space:pre}}"
        + f".dim{{fill:{t['dim']}}}.acc{{fill:{t['accent']}}}.b{{font-weight:700}}"
        + extra_css
    )
    ttl = f"<title>{esc(title)}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">'
        f"{ttl}<style>{css}</style>{body}</svg>\n"
    )
