"""One-off (local): section headings as SVG (your own typeface; lowercase label + hairline rule)."""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgkit import FONTS, THEMES, b64, font_face, svg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADINGS = ["hello", "stack", "projects", "activity", "contact"]
W, SIZE = 800, 15
ADV = 0.6 * SIZE


def build(label, theme):
    faces = font_face("JBM", b64(os.path.join(FONTS, "jbm-700.woff2")), 700)
    text = f"~/{label}"
    x_rule = 2 + len(text) * ADV + 14
    body = (
        f'<text x="2" y="24" font-size="{SIZE}" class="b">{text}</text>'
        f'<line x1="{x_rule:.1f}" y1="19" x2="{W}" y2="19" stroke="{THEMES[theme]["rule"]}" stroke-width="1"/>'
    )
    return svg(W, 34, body, faces, theme, "", label)


if __name__ == "__main__":
    for h in HEADINGS:
        for theme in THEMES:
            with open(os.path.join(ROOT, "assets", f"hd-{h}-{theme}.svg"), "w") as f:
                f.write(build(h, theme))
    print("headings:", len(HEADINGS) * 2, "files")
