#!/usr/bin/env python3
"""Crea due sfondi QUTEC a partire da una fotografia.

Esempio:
    python3 crea_sfondi_qutec.py codioful-formerly-gradienta-QWutu2BRpOs-unsplash.jpg \
        --font /percorso/al/font-del-sito.woff2

Genera nella stessa cartella dell'immagine:
  - <nome>_qutec_centro.jpg
  - <nome>_qutec_basso_sinistra.jpg

Il file del font e' opzionale: se omesso viene usato Fira Sans ExtraBold,
normalmente disponibile su Linux. Per riprodurre con precisione il lettering
del sito, passa qui il file .ttf, .otf o .woff2 del font autorizzato QUTEC.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FONT_CANDIDATES = (
    "/usr/share/fonts/TTF/FiraSans-ExtraBold.ttf",
    "/usr/share/fonts/TTF/OpenSans-ExtraBold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggiunge la scritta QUTEC a uno sfondo.")
    parser.add_argument("image", type=Path, help="Immagine sorgente (JPG, PNG, WebP ...)")
    parser.add_argument(
        "--font",
        type=Path,
        help="Font QUTEC in formato TTF, OTF o WOFF2. Se omesso usa il fallback di sistema.",
    )
    parser.add_argument("--text", default="QuTec", help="Testo da inserire (predefinito: QuTec)")
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument("-w", dest="color", action="store_const", const="#FFFFFF", help="Logo bianco (predefinito)")
    color_group.add_argument("-b", dest="color", action="store_const", const="#000000", help="Logo nero")
    parser.set_defaults(color="#FFFFFF")
    parser.add_argument(
        "--center-size",
        type=float,
        default=0.115,
        help="Larghezza massima del testo centrale come quota della tela (predefinito: 0.115)",
    )
    parser.add_argument(
        "--corner-size",
        type=float,
        default=0.055,
        help="Larghezza massima del testo in basso come quota della tela (predefinito: 0.055)",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.055,
        help="Margine laterale come quota della larghezza (predefinito: 0.055)",
    )
    parser.add_argument(
        "--bottom-margin",
        type=float,
        default=0.15,
        help="Spazio sotto al logo basso come quota dell'altezza (predefinito: 0.15)",
    )
    return parser.parse_args()


def font_path(user_font: Path | None) -> Path:
    if user_font:
        if not user_font.is_file():
            raise FileNotFoundError(f"Font non trovato: {user_font}")
        return user_font
    for candidate in map(Path, DEFAULT_FONT_CANDIDATES):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Nessun font di fallback trovato. Indica un file con --font.")


def fitted_font(draw: ImageDraw.ImageDraw, text: str, path: Path, target_width: int) -> ImageFont.FreeTypeFont:
    """Trova la dimensione piu' grande che rientra nella larghezza richiesta."""
    low, high = 1, max(2, target_width)
    while low < high:
        size = (low + high + 1) // 2
        font = ImageFont.truetype(path, size)
        if draw.textbbox((0, 0), text, font=font)[2] <= target_width:
            low = size
        else:
            high = size - 1
    return ImageFont.truetype(path, low)


def add_wordmark(image: Image.Image, text: str, font: ImageFont.FreeTypeFont, color: str, xy: tuple[int, int]) -> Image.Image:
    result = image.copy()
    ImageDraw.Draw(result).text(xy, text, font=font, fill=color)
    return result


def main() -> int:
    args = parse_args()
    if not args.image.is_file():
        print(f"Immagine non trovata: {args.image}", file=sys.stderr)
        return 2
    if (
        not 0 < args.center_size <= 1
        or not 0 < args.corner_size <= 1
        or not 0 <= args.margin < 0.5
        or not 0 <= args.bottom_margin < 0.5
    ):
        print(
            "center-size e corner-size devono essere tra 0 e 1; margin e bottom-margin tra 0 e 0.5.",
            file=sys.stderr,
        )
        return 2

    try:
        selected_font = font_path(args.font)
        with Image.open(args.image) as source:
            # RGB evita errori durante l'esportazione JPEG da PNG con trasparenza.
            background = source.convert("RGB")
    except (OSError, FileNotFoundError) as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 2

    width, height = background.size
    measure = ImageDraw.Draw(background)
    center_font = fitted_font(measure, args.text, selected_font, int(width * args.center_size))
    corner_font = fitted_font(measure, args.text, selected_font, int(width * args.corner_size))

    center_box = measure.textbbox((0, 0), args.text, font=center_font)
    center_width = center_box[2] - center_box[0]
    center_height = center_box[3] - center_box[1]
    center_xy = ((width - center_width) // 2 - center_box[0], (height - center_height) // 2 - center_box[1])

    corner_box = measure.textbbox((0, 0), args.text, font=corner_font)
    side_margin = int(width * args.margin)
    bottom_margin = int(height * args.bottom_margin)
    corner_xy = (
        side_margin - corner_box[0],
        height - bottom_margin - (corner_box[3] - corner_box[1]) - corner_box[1],
    )

    stem = args.image.with_suffix("")
    center_output = stem.with_name(f"{stem.name}_qutec_centro.jpg")
    corner_output = stem.with_name(f"{stem.name}_qutec_basso_sinistra.jpg")
    add_wordmark(background, args.text, center_font, args.color, center_xy).save(center_output, quality=95, subsampling=0)
    add_wordmark(background, args.text, corner_font, args.color, corner_xy).save(corner_output, quality=95, subsampling=0)

    print(f"Font: {selected_font}")
    print(f"Creato: {center_output}")
    print(f"Creato: {corner_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
