"""Local, authenticated visual reference library and optional OCR of a single frame."""
import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from .config import ROOT

VISION_ROOT = ROOT / 'data' / 'vision' / '1643i'


@lru_cache(maxsize=1)
def catalog() -> dict:
    data = json.loads((VISION_ROOT / 'catalog.json').read_text(encoding='utf-8'))
    if data['model'] != 'CANON_IR1643I':
        raise ValueError('Unsupported visual model')
    for reference in data['references']:
        path = (VISION_ROOT / reference['file']).resolve()
        if VISION_ROOT.resolve() not in path.parents or not path.is_file():
            raise ValueError(f'Missing visual reference: {reference["reference_id"]}')
    return data


def public_catalog() -> dict:
    data = json.loads(json.dumps(catalog()))
    for reference in data['references']:
        reference['image_url'] = f'/api/vision/reference/{reference["reference_id"]}/image'
        reference['display_url'] = f'/api/vision/reference/{reference["reference_id"]}/display'
    return data


def reference(reference_id: str) -> dict:
    for item in catalog()['references']:
        if item['reference_id'] == reference_id:
            return item
    raise KeyError(reference_id)


def reference_path(reference_id: str) -> Path:
    return (VISION_ROOT / reference(reference_id)['file']).resolve()


@lru_cache(maxsize=1)
def components() -> dict:
    data = json.loads((VISION_ROOT / 'components.json').read_text(encoding='utf-8'))
    inventory = json.loads((ROOT / 'data' / 'digital_twin' / 'oem_inventory.json').read_text(encoding='utf-8'))
    records = {item['id']: item for item in inventory['parts']}
    for item in data['components']:
        record = records[item['inventory_id']]
        if (record['part_number'] != item['part_number'] or record['quantity'] != item['quantity']
                or record['figure'] != item['figure']):
            raise ValueError(f"Referencia de componente inconsistente: {item['component_id']}")
    data['inventory_total'] = len(records)
    data['linked_count'] = len(data['components'])
    return data


def ocr_frame(image_bytes: bytes) -> dict:
    """Process one voluntary JPEG snapshot in memory, never store it or send it externally."""
    if len(image_bytes) > 300_000 or len(image_bytes) < 100 or not image_bytes.startswith(b'\xff\xd8'):
        raise ValueError('JPEG snapshot inválido o demasiado grande')
    binary = shutil.which('tesseract')
    if binary is None:
        return {'available': False, 'ocr_evidence': [], 'model_candidate': 'UNKNOWN'}
    try:
        result = subprocess.run([binary, 'stdin', 'stdout', '--psm', '11', '-l', 'eng'],
                                input=image_bytes, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {'available': False, 'ocr_evidence': [], 'model_candidate': 'UNKNOWN'}
    if result.returncode != 0:
        return {'available': False, 'ocr_evidence': [], 'model_candidate': 'UNKNOWN'}
    text = result.stdout.decode('utf-8', errors='replace').upper()
    evidence = [term for term, pattern in [('CANON', r'\bCANON\b'),
                                           ('IMAGERUNNER', r'IMAGE\s*RUNNER'),
                                           ('1643I', r'\b1643\s*I\b'),
                                           ('1643IF', r'\b1643\s*IF\b')]
                if re.search(pattern, text)]
    return {'available': True, 'ocr_evidence': evidence,
            'model_candidate': 'CANON_IR1643I' if ('1643I' in evidence or '1643IF' in evidence) else 'UNKNOWN'}
