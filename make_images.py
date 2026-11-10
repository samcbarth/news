"""Generates assets/og.png (1200x630) and assets/logo.png (512x512) for The Quillmark in the samcbarth.com brand. Needs Pillow.

  python make_images.py
"""
import pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent
BLACK, WHITE, PURPLE, SOFT = (0, 0, 0), (255, 255, 255), (154, 0, 255), (142, 124, 195)


def font(size, names=("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf")):
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def grad_bar(img, y0, y1, x0=0, x1=None):
    x1 = x1 or img.width
    d = ImageDraw.Draw(img)
    for x in range(x0, x1):
        t = (x - x0) / max(1, x1 - x0 - 1)
        d.line([x, y0, x, y1], fill=(int(PURPLE[0] * t), int(PURPLE[1] * t), int(PURPLE[2] * t)))


og = Image.new("RGB", (1200, 630), BLACK)
d = ImageDraw.Draw(og)
fe = font(30)
eyebrow = "SEVEN BEATS, ONE FRONT PAGE"
d.text(((1200 - d.textlength(eyebrow, font=fe)) / 2, 170), eyebrow, font=fe, fill=SOFT)
f = font(120)
name = "THE QUILLMARK"
w = d.textlength(name, font=f)
d.ellipse([(1200 - w) / 2 - 44, 270, (1200 - w) / 2 - 22, 292], fill=PURPLE)
d.text(((1200 - w) / 2, 222), name, font=f, fill=WHITE)
grad_bar(og, 380, 384, 160, 1040)
s = "REAL ESTATE  /  TOOLS AND TECH  /  GAMING  /  STREAMING  /  HOME  /  DEALS"
fs = font(24)
d.text(((1200 - d.textlength(s, font=fs)) / 2, 420), s, font=fs, fill=(200, 200, 200))
grad_bar(og, 622, 630)
og.save(ROOT / "assets" / "og.png", optimize=True)

logo = Image.new("RGB", (512, 512), BLACK)
d = ImageDraw.Draw(logo)
fq = font(360)
w = d.textlength("Q", font=fq)
d.text(((512 - w) / 2 - 16, 40), "Q", font=fq, fill=WHITE)
d.ellipse([400, 70, 450, 120], fill=PURPLE)
grad_bar(logo, 440, 452, 60, 452)
logo.save(ROOT / "assets" / "logo.png", optimize=True)
print("wrote assets/og.png and assets/logo.png")
