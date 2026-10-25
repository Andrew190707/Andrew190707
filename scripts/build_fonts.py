"""One-off (local): subset JetBrains Mono into the small woff2 files the SVGs embed.
pip install fonttools brotli
"""
import os
from fontTools import subset

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, "assets", "fonts")
BASIC = "".join(chr(c) for c in range(0x20, 0x7F)) + "·—–→×…’“”"


def run(src, text, out):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.hinting = False
    opts.notdef_outline = True
    font = subset.load_font(os.path.join(F, src), opts)
    s = subset.Subsetter(opts)
    s.populate(text=text)
    s.subset(font)
    subset.save_font(font, os.path.join(F, out), opts)
    print(out, os.path.getsize(os.path.join(F, out)), "bytes")


if __name__ == "__main__":
    run("JetBrainsMono-Regular.ttf", BASIC, "jbm-400.woff2")
    run("JetBrainsMono-Bold.ttf", BASIC, "jbm-700.woff2")
