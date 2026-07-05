"""Generate the IEVR app icon: a football with a golden lightning bolt
(Inazuma = lightning) on a rounded deep-blue tile.

Run: .venv\\Scripts\\python tools\\make_icon.py
Writes assets/logo.png (512px, for in-app use) and assets/icon.ico
(multi-size, for the exe / window icon). Deterministic — safe to re-run.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"

S = 512  # master canvas size

NAVY_TOP = (30, 58, 138)      # #1e3a8a
NAVY_BOT = (13, 24, 66)       # #0d1842
WHITE = (245, 247, 252)
BLACK = (24, 28, 40)
GOLD = (255, 196, 0)
GOLD_DARK = (196, 138, 0)


def _rounded_gradient(d: ImageDraw.ImageDraw, img: Image.Image) -> None:
    # Vertical gradient, then punch out rounded corners via mask.
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOT))
        d.line([(0, y), (S, y)], fill=c)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                           radius=S // 5, fill=255)
    img.putalpha(mask)


def _pentagon(cx, cy, r, rot=-90):
    return [(cx + r * math.cos(math.radians(rot + i * 72)),
             cy + r * math.sin(math.radians(rot + i * 72))) for i in range(5)]


def _ball(d: ImageDraw.ImageDraw) -> None:
    cx, cy, r = S * 0.5, S * 0.54, S * 0.30
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE,
              outline=BLACK, width=int(S * 0.018))
    # centre pentagon + seams to suggest a football without clutter
    pr = r * 0.42
    pent = _pentagon(cx, cy, pr)
    d.polygon(pent, fill=BLACK)
    for px, py in pent:
        vx, vy = px - cx, py - cy
        n = math.hypot(vx, vy)
        ex, ey = cx + vx / n * r * 0.97, cy + vy / n * r * 0.97
        d.line([(px, py), (ex, ey)], fill=BLACK, width=int(S * 0.016))


def _bolt(d: ImageDraw.ImageDraw) -> None:
    # Lightning bolt slashing from top-right to bottom-left across the ball.
    def pts(scale=1.0, dx=0.0, dy=0.0):
        raw = [(0.72, 0.06), (0.42, 0.44), (0.55, 0.47),
               (0.30, 0.88), (0.66, 0.42), (0.52, 0.40)]
        return [((x - 0.5) * scale + 0.5 + dx) * S if False else
                (x * S * scale + dx * S, y * S * scale + dy * S)
                for x, y in raw]
    d.polygon(pts(), fill=GOLD, outline=GOLD_DARK, width=int(S * 0.012))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    img = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(img)
    _rounded_gradient(d, img)
    d = ImageDraw.Draw(img)  # re-bind after putalpha
    _ball(d)
    _bolt(d)

    logo = OUT / "logo.png"
    img.save(logo)
    ico = OUT / "icon.ico"
    img.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                         (64, 64), (128, 128), (256, 256)])
    print(f"wrote {logo}\nwrote {ico}")


if __name__ == "__main__":
    sys.exit(main())
