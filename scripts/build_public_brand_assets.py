#!/usr/bin/env python3
"""Build deterministic FlipGuard public-brand SVG and PNG assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "docs" / "assets" / "brand"

NAVY = "#0D2A52"
BLUE = "#1F6FEB"
CYAN = "#2F9ECA"
DARK = "#0D1117"
WHITE = "#FFFFFF"
MUTED = "#B6C2CF"

GLYPHS = {
    " ": ("00000",) * 7,
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "N": ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
}


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_document(width: int, height: int, title: str, description: str, body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">\n'
        f'  <title id="title">{esc(title)}</title>\n'
        f'  <desc id="desc">{esc(description)}</desc>\n'
        f'{body}\n</svg>\n'
    )


def mark_body(*, x: float = 0, y: float = 0, scale: float = 1, dark: bool = False, mono: bool = False) -> str:
    shield = WHITE if dark else NAVY
    split = BLUE if dark else BLUE
    arrow_a = DARK if dark else WHITE
    arrow_b = WHITE if dark else CYAN
    if mono:
        shield = DARK
        split = DARK
        arrow_a = WHITE
        arrow_b = WHITE
    transform = f'translate({x} {y}) scale({scale})'
    return f'''  <g transform="{transform}">
    <path fill="{shield}" d="M32 3 55 12v17c0 14.5-8.9 25.4-23 32C17.9 54.4 9 43.5 9 29V12L32 3Z"/>
    <path fill="{split}" d="M32 7.2 51 14.6V29c0 11.8-6.8 21-19 27V7.2Z"/>
    <path fill="none" stroke="{arrow_a}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="M18 27c4.1-6.1 13.5-8.6 21.1-4.3L43 25"/>
    <path fill="none" stroke="{arrow_b}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="m38 18 5 7-8 2"/>
    <path fill="none" stroke="{arrow_b}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="M46 37c-4.1 6.1-13.5 8.6-21.1 4.3L21 39"/>
    <path fill="none" stroke="{arrow_a}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" d="m26 46-5-7 8-2"/>
    <circle cx="19" cy="16" r="2.3" fill="{arrow_a}"/>
    <circle cx="45" cy="48" r="2.3" fill="{arrow_b}"/>
  </g>'''


def pixel_text_svg(text: str, x: float, y: float, cell: float, color: str) -> str:
    rects: list[str] = []
    cursor = x
    for char in text.upper():
        glyph = GLYPHS.get(char)
        if glyph is None:
            raise ValueError(f"unsupported vector glyph: {char!r}")
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    rects.append(
                        f'<rect x="{cursor + col * cell:.3f}" y="{y + row * cell:.3f}" '
                        f'width="{cell * 0.82:.3f}" height="{cell * 0.82:.3f}" rx="{cell * 0.12:.3f}"/>'
                    )
        cursor += 6 * cell
    return f'  <g fill="{color}">\n    ' + "\n    ".join(rects) + "\n  </g>"


def write_svg(name: str, width: int, height: int, title: str, description: str, body: str) -> None:
    (BRAND_DIR / name).write_text(svg_document(width, height, title, description, body), encoding="utf-8")


def draw_mark(draw: ImageDraw.ImageDraw, size: int, *, offset: tuple[int, int] = (0, 0), dark: bool = False) -> None:
    ox, oy = offset
    s = size / 64
    point = lambda x, y: (ox + round(x * s), oy + round(y * s))
    shield = WHITE if dark else NAVY
    draw.polygon([point(32, 3), point(55, 12), point(55, 29), point(51, 43), point(42, 53), point(32, 61), point(22, 56), point(13, 45), point(9, 29), point(9, 12)], fill=shield)
    draw.polygon([point(32, 7), point(51, 15), point(51, 29), point(47, 41), point(40, 50), point(32, 56)], fill=BLUE)
    width = max(2, round(4 * s))
    draw.line([point(18, 27), point(24, 22), point(32, 21), point(39, 23), point(43, 25)], fill=DARK if dark else WHITE, width=width, joint="curve")
    draw.line([point(38, 18), point(43, 25), point(35, 27)], fill=WHITE if dark else CYAN, width=width, joint="curve")
    draw.line([point(46, 37), point(40, 42), point(32, 43), point(25, 41), point(21, 39)], fill=WHITE if dark else CYAN, width=width, joint="curve")
    draw.line([point(26, 46), point(21, 39), point(29, 37)], fill=DARK if dark else WHITE, width=width, joint="curve")
    r = max(2, round(2.3 * s))
    for (cx, cy, color) in [(19, 16, DARK if dark else WHITE), (45, 48, WHITE if dark else CYAN)]:
        px, py = point(cx, cy)
        draw.ellipse((px-r, py-r, px+r, py+r), fill=color)


def draw_pixel_text(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, cell: int, color: str) -> None:
    cursor = x
    for char in text.upper():
        glyph = GLYPHS[char]
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    x0 = cursor + col * cell
                    y0 = y + row * cell
                    draw.rounded_rectangle((x0, y0, x0 + int(cell * 0.8), y0 + int(cell * 0.8)), radius=max(1, cell // 10), fill=color)
        cursor += 6 * cell


def save_pngs() -> None:
    for size in (128, 512):
        scale = 4
        canvas = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
        draw_mark(ImageDraw.Draw(canvas), size * scale)
        canvas.resize((size, size), Image.Resampling.LANCZOS).save(BRAND_DIR / f"flipguard-mark-{size}.png", optimize=True)

    scale = 2
    canvas = Image.new("RGB", (1280 * scale, 640 * scale), DARK)
    draw = ImageDraw.Draw(canvas)
    draw_mark(draw, 260 * scale, offset=(86 * scale, 146 * scale), dark=True)
    draw_pixel_text(draw, "FLIPGUARD", 412 * scale, 182 * scale, 13 * scale, WHITE)
    draw_pixel_text(
        draw,
        "DIRECT SYNTHESIS AND VALIDATION UNDER DECISION INTEGRITY CONTRACTS",
        416 * scale,
        370 * scale,
        2 * scale,
        CYAN,
    )
    canvas.resize((1280, 640), Image.Resampling.LANCZOS).save(BRAND_DIR / "flipguard-social-preview.png", optimize=True)


def main() -> int:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    description = "A split shield with bidirectional arrows and circuit nodes, representing decision integrity for encrypted computation."
    write_svg("flipguard-mark.svg", 64, 64, "FlipGuard mark", description, mark_body())
    write_svg("flipguard-mark-dark.svg", 64, 64, "FlipGuard mark for dark backgrounds", description, mark_body(dark=True))
    write_svg("flipguard-mark-mono.svg", 64, 64, "Monochrome FlipGuard mark", description, mark_body(mono=True))
    write_svg("flipguard-favicon.svg", 64, 64, "FlipGuard favicon", description, mark_body())

    for filename, dark in (("flipguard-wordmark.svg", False), ("flipguard-wordmark-dark.svg", True)):
        color = WHITE if dark else NAVY
        body = mark_body(x=10, y=8, scale=1.25, dark=dark) + "\n" + pixel_text_svg("FLIPGUARD", 112, 27, 7.1, color)
        write_svg(filename, 520, 96, "FlipGuard wordmark", description, body)

    social_body = (
        f'  <rect width="1280" height="640" fill="{DARK}"/>\n'
        + mark_body(x=86, y=146, scale=4.0625, dark=True)
        + "\n"
        + pixel_text_svg("FLIPGUARD", 412, 182, 13, WHITE)
        + "\n"
        + pixel_text_svg(
            "DIRECT SYNTHESIS AND VALIDATION UNDER DECISION INTEGRITY CONTRACTS",
            416,
            370,
            2,
            CYAN,
        )
    )
    write_svg("flipguard-social-preview.svg", 1280, 640, "FlipGuard social preview", "FlipGuard name and decision-integrity tagline on a dark background.", social_body)
    save_pngs()

    manifest = {}
    for path in sorted(BRAND_DIR.glob("flipguard-*")):
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (BRAND_DIR / "asset-digests.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
