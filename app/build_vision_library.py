"""Extract the permitted OEM photo crops without changing source PDFs."""
import json
from pathlib import Path

import pymupdf

from .config import MANUALS, MANUALS_DIR, ROOT


def build() -> list[Path]:
    root = ROOT / 'data' / 'vision' / '1643i'
    catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8'))
    written = []
    for reference in catalog['references']:
        if reference['source_type'] != 'OEM_PDF':
            continue
        source = MANUALS_DIR / MANUALS[reference['source']]['file']
        destination = (root / reference['file']).resolve()
        if root.resolve() not in destination.parents:
            raise ValueError('Image output outside visual library')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(source) as pdf:
            page = pdf[reference['source_page']['pdf'] - 1]
            crop = pymupdf.Rect(*reference['source_crop_pdf_points']) & page.rect
            if crop.is_empty:
                raise ValueError(reference['reference_id'])
            page.get_pixmap(matrix=pymupdf.Matrix(2.2, 2.2), clip=crop, alpha=False).save(destination)
        written.append(destination)
    return written


if __name__ == '__main__':
    for path in build():
        print(path)
