"""One-off (local): photo -> typing ASCII portrait SVGs (dark + light).
pip install pillow numpy opencv-python-headless rembg onnxruntime fonttools brotli
Usage: python3 scripts/build_portrait.py assets/crop.png
"""
import io
import os
import sys

import cv2
import numpy as np
from fontTools import subset
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgkit import RAMP, ROOT, THEMES, b64, esc, font_face, svg  # noqa: E402

COLS = 90
CHAR_W = 7.74            # 0.600 em at font-size 12.9
FONT_SIZE = 12.9
ROW_H = CHAR_W / 0.48    # monospace cells are ~2x taller than wide
GAMMA = 1.35             # darkening curve: what keeps glasses/brows/lips alive
LIFT = 0.6               # this photo is low-key, so shadows get lifted first
CLAHE_CLIP = 3.0
SHARP = 1.1              # unsharp amount at character-cell scale (edges: glasses, nose, jaw)
STAGGER = 0.09
ROW_DUR = 0.9


def mask_for(img):
    """Segment on a shadow-lifted copy so dark hair isn't eaten by a dark wall."""
    from rembg import new_session, remove

    a = np.asarray(img.convert("RGB")).astype(float) / 255
    lift = np.clip((a ** 0.45 - 0.05) * 1.3, 0, 1)
    lim = Image.fromarray((lift * 255).astype("uint8"))
    m = remove(lim, session=new_session("u2net"), only_mask=True)
    return np.asarray(m).astype(float) / 255


def clean(mask):
    m = (mask > 0.5).astype("uint8") * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    ff = m.copy()
    h, w = m.shape
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), "uint8"), (0, 0), 255)
    holes = cv2.bitwise_not(ff)             # regions not reachable from the border
    return ((m | holes) > 0).astype(float)


def tone_map(img, mask):
    rgb = np.asarray(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(float) / 255
    gray = cv2.bilateralFilter((gray * 255).astype("uint8"), 7, 40, 40).astype(float) / 255
    m = mask > 0.5
    lo, hi = np.percentile(gray[m], (1, 99.5))
    g = np.clip((gray - lo) / max(hi - lo, 1e-3), 0, 1) ** LIFT   # low-key photo: lift
    g8 = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(6, 6)).apply((g * 255).astype("uint8"))
    g = g8.astype(float) / 255
    g = np.where(m, g, 1.0)                 # outside subject -> white -> blank
    return g


def to_rows(g, invert):
    h, w = g.shape
    rows = max(1, int(COLS * (h / w) * 0.48))
    small = cv2.resize(g, (COLS, rows), interpolation=cv2.INTER_AREA).astype(np.float32)
    blur = cv2.GaussianBlur(small, (0, 0), 1.2)
    sharp = np.clip(small + SHARP * (small - blur), 0, 1)
    small = np.where(small >= 0.995, 1.0, sharp)   # never bleed ink into the background
    out = []
    n = len(RAMP) - 1
    for r in range(rows):
        line = []
        for c in range(COLS):
            v = float(small[r, c])
            if v >= 0.995:                  # background / pure white
                idx = 0
            else:
                ink = (1.0 - v ** GAMMA) if not invert else (v ** GAMMA)
                # invert (dark theme): lit areas get dense ink, shadows go sparse
                if invert:
                    ink = ink * 0.95
                idx = int(round(ink * n))
                idx = max(1 if v < 0.995 else 0, min(n, idx))
            line.append(RAMP[idx])
        out.append("".join(line).rstrip())
    return out


def ramp_face():
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.hinting = False
    font = subset.load_font(os.path.join(ROOT, "assets/fonts/JetBrainsMono-Regular.ttf"), opts)
    s = subset.Subsetter(opts)
    s.populate(text=RAMP)
    s.subset(font)
    buf = io.BytesIO()
    opts2 = subset.Options()
    opts2.flavor = "woff2"
    subset.save_font(font, buf, opts)
    import base64
    return font_face("JBM", base64.b64encode(buf.getvalue()).decode(), 400)


def build(rows, theme, faces):
    W = COLS * CHAR_W
    H = len(rows) * ROW_H + 6
    defs, body = [], []
    for i, line in enumerate(rows):
        y0 = i * ROW_H + 3
        base = y0 + ROW_H * 0.76
        begin = f"{i * STAGGER:.2f}s"
        end = f"{i * STAGGER + ROW_DUR:.2f}s"
        defs.append(
            f'<clipPath id="r{i}"><rect x="0" y="{y0:.2f}" width="0" height="{ROW_H:.2f}">'
            f'<animate attributeName="width" from="0" to="{W:.2f}" begin="{begin}" '
            f'dur="{ROW_DUR}s" fill="freeze"/></rect></clipPath>'
        )
        body.append(
            f'<text x="0" y="{base:.2f}" font-size="{FONT_SIZE}" xml:space="preserve" '
            f'clip-path="url(#r{i})">{esc(line)}</text>'
        )
        # cursor block riding the wipe edge, gone once the row is done
        body.append(
            f'<rect y="{y0 + 2:.2f}" width="{CHAR_W:.2f}" height="{ROW_H - 4:.2f}" '
            f'class="cur" opacity="0"><set attributeName="opacity" to="0.85" begin="{begin}"/>'
            f'<animate attributeName="x" from="0" to="{W:.2f}" begin="{begin}" dur="{ROW_DUR}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0" begin="{end}"/></rect>'
        )
    css = f".cur{{fill:{THEMES[theme]['accent']}}}"
    inner = "<defs>" + "".join(defs) + "</defs>" + "".join(body)
    return svg(round(W, 2), round(H, 2), inner, faces, theme, css, "ASCII portrait")


if __name__ == "__main__":
    photo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "source/photo.png")
    box = tuple(int(v) for v in (sys.argv[2].split(",") if len(sys.argv) > 2 else "200,330,830,890".split(",")))
    full = Image.open(photo).convert("RGB")
    mask = clean(mask_for(full))            # segment the WHOLE photo, then crop
    x0, y0, x1, y1 = box
    img = full.crop(box)
    mask = mask[y0:y1, x0:x1]
    g = tone_map(img, mask)
    faces = ramp_face()
    for theme, inv in (("light", False), ("dark", True)):
        rows = to_rows(g, inv)
        out = os.path.join(ROOT, "assets", f"portrait-{theme}.svg")
        with open(out, "w") as f:
            f.write(build(rows, theme, faces))
        with open(os.path.join(ROOT, "assets", f"portrait-{theme}.txt"), "w") as f:
            f.write("\n".join(rows))
        print(theme, len(rows), "rows ->", out, os.path.getsize(out) // 1024, "KB")
