"""Extrae un índice verificable de los PDF OEM, sin modificar los originales."""
import json
import re
from pathlib import Path

import pymupdf

from app.config import MANUALS, MANUALS_DIR, ROOT

OUTPUT = ROOT / 'data' / 'digital_twin' / 'oem_inventory.json'
PART = re.compile(r'^[A-Z]{1,4}\d?\d?-[A-Z0-9]{3,5}-\d{3}$')
FIGURE = re.compile(r'^Figure\s+([0-9]{3}[A-Z]?|[A-Z]\d[A-Z]?)$', re.I)
MEASUREMENT = re.compile(r'\b\d+(?:\.\d+)?\s*(?:mm|cm)\b', re.I)
HEADING = re.compile(r'^(?:Removing|Installing|Replacing|Cleaning|Figure|External Cover|Original Exposure|[A-Z][A-Za-z /-]+Specifications)', re.I)
SERVICE_TERMS = {
    'cover': re.compile(r'\b(?:cover|door|carcass)\b', re.I),
    'adf': re.compile(r'\bADF\b', re.I),
    'reader': re.compile(r'\breader\b', re.I),
    'panel': re.compile(r'\bpanel\b', re.I),
    'tray': re.compile(r'\b(?:tray|cassette)\b', re.I),
    'roller': re.compile(r'\broller\b', re.I),
    'connector': re.compile(r'\bconnector\b', re.I),
    'pcb': re.compile(r'\bPCB\b', re.I),
    'hinge': re.compile(r'\bhinge\b', re.I),
    'screw': re.compile(r'\bscrew\b', re.I),
    'guide': re.compile(r'\bguide\b', re.I),
    'motor': re.compile(r'\bmotor\b', re.I),
    'sensor': re.compile(r'\bsensor\b', re.I),
    'assembly': re.compile(r'\bassembly\b', re.I),
}


def part_category(description: str) -> str:
    upper = description.upper()
    for name, words in {
        'cover': ('COVER', 'DOOR'), 'roller': ('ROLLER',), 'hinge': ('HINGE',),
        'tray': ('TRAY', 'CASSETTE'), 'screw': ('SCREW',), 'guide': ('GUIDE',),
        'motor': ('MOTOR',), 'sensor': ('SENSOR', 'PHOTO INTERRUPTER'),
        'pcb': ('PCB',), 'connector': ('CONNECTOR',), 'cable': ('CABLE',),
        'panel': ('PANEL', 'LCD'), 'assembly': ('ASSEMBLY', "ASS'Y"),
    }.items():
        if any(word in upper for word in words):
            return name
    return 'other'


def extract_parts(document):
    parts = []
    figures = []
    current_figure = None
    for page_number in range(1, len(document) + 1):
        lines = [line.strip() for line in document[page_number - 1].get_text().splitlines() if line.strip()]
        for line in lines:
            match = FIGURE.match(line)
            if match:
                current_figure = match.group(1)
                figures.append({'figure': match.group(1), 'source_document': 'PC_R9',
                                'source_page': page_number,
                                'description': next((s for s in lines[lines.index(line) + 1:] if s.isupper()), '')})
        if not (len(lines) > 10 and lines[0] == 'FIGURE' and 'PART NUMBER' in lines[:7]):
            continue
        candidate = lines[12] if lines[11] == '/REMARKS' else lines[11]
        figure_id = candidate if re.fullmatch(r'(?:\d{3}[A-Z]?|SNL|[A-Z]\d[A-Z]?)', candidate) else current_figure
        if figure_id == 'NPN':
            continue
        first_part_line = next((i for i in range(len(lines) - 1) if PART.match(lines[i + 1])), len(lines))
        header = ' '.join(lines[12:first_part_line])
        if 'iR 1643iF' in header and 'iR 1643i ' not in header:
            applicable_models = ['CANON_IR1643IF']
        elif 'iR 1643i' in header and 'iR 1643iF' not in header:
            applicable_models = ['CANON_IR1643I']
        else:
            applicable_models = ['CANON_IR1643I', 'CANON_IR1643IF']
        index = 0
        while index + 3 < len(lines):
            if lines[index].isdigit() and PART.match(lines[index + 1]) and lines[index + 2].isdigit():
                key, number, quantity = lines[index], lines[index + 1], int(lines[index + 2])
                description = lines[index + 3]
                if description == '':
                    index += 1
                    continue
                parts.append({
                    'id': f'{figure_id}:{key}:{number}', 'figure': figure_id, 'figure_key': int(key),
                    'part_number': number, 'description': description, 'quantity': quantity,
                    'category': part_category(description), 'source_document': 'PC_R9',
                    'source_page': page_number, 'source_figure': f'Figure {figure_id}',
                    'figure_page': page_number - 1, 'confidence': 'OEM_EXPLICIT',
                    'applicable_models': applicable_models,
                    'measurement_source': 'Parts Catalog parts list; no metric position supplied',
                    'geometry_status': 'PHYSICAL_VALIDATION_REQUIRED',
                })
                index += 4
            else:
                index += 1
    for figure_id, page_number, number, description, quantity in [
        ('400A', 50, 'FM1-U532-000', 'READER ASSEMBLY', 1),
        ('930B', 54, 'FM1-Y349-010', "MAIN CONTROLLER PCB ASS'Y SET", 1),
    ]:
        parts.append({
            'id': f'{figure_id}:assembly:{number}', 'figure': figure_id, 'figure_key': None,
            'part_number': number, 'description': description, 'quantity': quantity,
            'category': part_category(description), 'source_document': 'PC_R9',
            'source_page': page_number, 'source_figure': f'Figure {figure_id}',
            'figure_page': page_number - 1, 'confidence': 'OEM_EXPLICIT',
            'applicable_models': ['CANON_IR1643I'] if figure_id == '930B' else ['CANON_IR1643I', 'CANON_IR1643IF'],
            'measurement_source': 'Parts Catalog top-level assembly line; no metric position supplied',
            'geometry_status': 'PHYSICAL_VALIDATION_REQUIRED',
        })
    return figures, parts


def extract_service_pages(document):
    pages = []
    mentions = []
    for page_number, page in enumerate(document, 1):
        lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
        headings = [line for line in lines if HEADING.match(line)][:10]
        measurements = sorted(set(MEASUREMENT.findall(' '.join(lines))))[:25]
        categories = []
        for category, pattern in SERVICE_TERMS.items():
            matching = [line for line in lines if pattern.search(line) and len(line) >= 8][:2]
            if matching:
                categories.append(category)
            for line in matching:
                mentions.append({
                    'category': category, 'description': line[:280],
                    'source_document': 'SM_R6', 'source_page': page_number,
                    'source_figure': headings[0] if headings else None,
                    'part_number': None, 'quantity': None,
                    'confidence': 'OEM_TEXT_MENTION',
                    'measurement_source': 'Service Manual extracted text; no dimensional inference',
                })
        pages.append({
            'source_document': 'SM_R6', 'source_page': page_number,
            'printed_page': int(lines[-1]) if lines and lines[-1].isdigit() else None,
            'headings': headings, 'measurements_mentioned': measurements,
            'component_categories_mentioned': categories,
            'embedded_images': len(page.get_images(full=True)),
            'confidence': 'TEXT_AND_IMAGE_INDEX_ONLY',
            'measurement_source': 'Service Manual PDF page scan; measurements require contextual interpretation',
        })
    return pages, mentions


def main():
    with pymupdf.open(MANUALS_DIR / MANUALS['PC_R9']['file']) as parts_document:
        figures, parts = extract_parts(parts_document)
    with pymupdf.open(MANUALS_DIR / MANUALS['SM_R6']['file']) as service_document:
        service_pages, service_mentions = extract_service_pages(service_document)
    data = {
        'schema_version': 1, 'model_id': 'CANON_IR1643I',
        'notice': 'Inventario documental. Los listados de piezas no proporcionan posiciones métricas.',
        'figures': figures, 'parts': parts, 'service_pages': service_pages,
        'service_mentions': service_mentions,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(OUTPUT), 'figures': len(figures),
                      'parts': len(parts), 'service_pages': len(service_pages),
                      'service_mentions': len(service_mentions)}))


if __name__ == '__main__':
    main()
