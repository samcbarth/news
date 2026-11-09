"""Generates assets/og.png (1200x630) and assets/logo.png (512x512) for The Quillmark. Needs Pillow.

  python make_images.py
"""
import pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent
PAPER, INK, ACCENT = (247, 244, 236), (27, 28, 31), (15, 92, 90)


def font(size, bold=True):
    for name in (["georgiab.ttf", "timesbd.ttf"] if bold else ["georgiai.ttf", "georgia.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


og = Image.new("RGB", (1200, 630), PAPER)
d = ImageDraw.Draw(og)
d.rectangle([0, 0, 1200, 18], fill=ACCENT)
d.line([80, 170, 1120, 170], fill=INK, width=3)
d.line([80, 178, 1120, 178], fill=INK, width=1)
f = font(132)
w = d.textlength("The Quillmark", font=f)
d.text(((1200 - w) / 2, 210), "The Quillmark", font=f, fill=INK)
d.line([80, 400, 1120, 400], fill=INK, width=1)
d.line([80, 408, 1120, 408], fill=INK, width=3)
t = "Seven beats, one front page"
ft = font(44, bold=False)
d.text(((1200 - d.textlength(t, font=ft)) / 2, 440), t, font=ft, fill=ACCENT)
s = "Real Estate  ·  Tools and Tech  ·  Gaming  ·  Streaming  ·  Home  ·  Deals"
fs = font(28)
d.text(((1200 - d.textlength(s, font=fs)) / 2, 530), s, font=fs, fill=INK)
og.save(ROOT / "assets" / "og.png", optimize=True)

logo = Image.new("RGB", (512, 512), ACCENT)
d = ImageDraw.Draw(logo)
fq = font(380)
w = d.textlength("Q", font=fq)
d.text(((512 - w) / 2, 30), "Q", font=fq, fill=PAPER)
logo.save(ROOT / "assets" / "logo.png", optimize=True)
print("wrote assets/og.png and assets/logo.png")
