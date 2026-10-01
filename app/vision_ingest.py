"""Recortes visuales OEM reproducibles; nunca modifica los PDF originales."""
from pathlib import Path

import pymupdf

from .config import MANUALS, MANUALS_DIR
from .vision import VISION_ROOT


CROPS = [
    ('SM_R6', 17, (183, 386, 412, 602), 'equipment/1643_front_closed.png'),
    ('SM_R6', 1, (257, 181, 557, 541), 'equipment/1643_front_threequarter.png'),
    ('SM_R6', 128, (199, 343, 414, 511), 'states/1643_rear_door_removed.png'),
    ('SM_R6', 133, (199, 509, 414, 669), 'states/1643_right_cover_releasing.png'),
    ('SM_R6', 139, (231, 102, 443, 263), 'equipment/1643_left_cover_installed.png'),
    ('SM_R6', 152, (200, 257, 414, 382), 'states/1643_internal_adf_access.png'),
    ('PC_R9', 44, (54, 96, 550, 737), 'components/reader_adf_figure160.png'),
]


def build_visual_crops(root: Path = VISION_ROOT) -> list[Path]:
    written = []
    for doc_id, page_number, bounds, relative in CROPS:
        destination = Path(root) / relative
        if destination.is_file():
            written.append(destination)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(MANUALS_DIR / MANUALS[doc_id]['file']) as pdf:
            page = pdf[page_number - 1]
            clip = pymupdf.Rect(*bounds) & page.rect
            if clip.is_empty:
                raise ValueError(f'Recorte OEM vacío: {relative}')
            page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip,
                            alpha=False).save(destination)
        written.append(destination)
    return written


if __name__ == '__main__':
    for image in build_visual_crops():
        print(image)
