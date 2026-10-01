"""Modelo ilustrativo con topología OEM y geometría de simulación separadas."""
import json
from pathlib import Path

from app.config import ROOT

ROOT_DATA = ROOT / 'data' / 'digital_twin'
inventory = json.loads((ROOT_DATA / 'oem_inventory.json').read_text(encoding='utf-8'))
part_lookup = {(part['figure'], part['part_number']): part for part in inventory['parts']}

components = []


def group(component_id, parent_id, label, category, source_figure, source_page):
    components.append({
        'id': component_id, 'parent_id': parent_id, 'label': label, 'category': category,
        'part_number': None, 'quantity': None, 'source_document': 'PC_R9',
        'source_page': source_page, 'source_figure': source_figure,
        'geometry': None, 'geometry_status': 'PHYSICAL_VALIDATION_REQUIRED',
        'estimated': False, 'measurement_source': 'Topological group only; no metric geometry',
    })


def item(component_id, parent_id, label, kind, figure, number, position, size, explode,
         animation='REMOVE_LINEAR', direction=None, source_page=None):
    part = part_lookup.get((figure, number)) if number else None
    if number and part is None:
        raise ValueError(f'Part not found: {figure} {number}')
    components.append({
        'id': component_id, 'parent_id': parent_id, 'label': label, 'category': kind,
        'part_number': number, 'quantity': part['quantity'] if part else None,
        'oem_description': part['description'] if part else label,
        'source_document': 'PC_R9' if part else 'SM_R6',
        'source_page': part['source_page'] if part else (source_page or 21),
        'source_figure': f'Figure {figure}' if part else ('Service Manual procedure photograph' if source_page else 'Overall dimensions'),
        'geometry': {
            'primitive': 'cylinder' if kind in {'roller', 'screw', 'hinge'} else 'box',
            'position_mm': position, 'size_mm': size,
            'geometry_status': 'OEM_IMAGE_APPROXIMATED', 'estimated': True,
            'measurement_source': (f'Illustrative proportions from PC_R9 Figure {figure} and SM_R6 photographs; not metric OEM data'
                                   if figure else f'Illustrative proportions from SM_R6 PDF page {source_page or 21}; not metric OEM data'),
        },
        'geometry_status': 'OEM_IMAGE_APPROXIMATED', 'estimated': True,
        'measurement_source': 'Visual simulation only; internal dimensions/positions not specified by OEM',
        'explosion': {'direction': direction or explode, 'distance_mm': 90,
                      'distance_status': 'APPROXIMATED', 'estimated': True},
        'animation_type': animation,
    })


group('equipment', None, 'Canon imageRUNNER 1643i', 'equipment', 'Service Manual overall dimensions', 21)
item('body', 'equipment', 'Cuerpo principal', 'body', None, None, [0, 145, 0], [480, 290, 464], [0, 0, 0], 'NONE')
item('rear_door', 'equipment', 'Rear Door Unit', 'cover', '100B', 'FM1-T491-000', [0, 144, -234], [438, 232, 14], [0, 0, -1])
item('cassette', 'equipment', 'Cassette', 'tray', '102A', 'FM1-N488-000', [0, 52, 205], [405, 92, 350], [0, 0, 1], 'SLIDE')
item('right_cover', 'equipment', 'Right Cover Unit', 'cover', '100B', 'FM1-T493-000', [233, 160, 0], [13, 255, 424], [1, 0, 0])
item('left_cover', 'equipment', 'Left Cover Unit', 'cover', '100B', 'FM1-T492-000', [-233, 160, 0], [13, 255, 424], [-1, 0, 0])
item('rear_top_cover', 'equipment', 'Rear Top Cover', 'cover', '100B', 'FE8-6707-000', [0, 298, -189], [435, 18, 78], [0, 1, -1])
item('cartridge', 'equipment', 'Cartridge (posición ilustrativa)', 'assembly', None, None, [0, 174, 110], [284, 112, 190], [0, 0, 1], 'SLIDE', source_page=130)
item('control_panel', 'equipment', 'Control Panel Assembly', 'panel', '130B', 'FM1-R686-020', [165, 308, 215], [135, 40, 78], [0, 1, 1], 'ROTATE_OPEN')
item('controller_pcb', 'equipment', 'DC Controller PCB', 'pcb', '103', 'FM2-M824-000', [100, 178, -64], [118, 150, 6], [1, 0, 0])
item('main_motor', 'equipment', 'Main Motor', 'motor', '102A', 'RM2-9531-000', [-127, 123, -98], [70, 70, 68], [-1, 0, 0])
item('transfer_roller', 'equipment', 'Transfer Roller', 'roller', '103', 'RM1-4023-000', [0, 135, 30], [300, 20, 20], [0, 1, 0])
group('reader_adf', 'equipment', 'Reader/ADF Assembly', 'assembly', 'Figure 160', 44)
item('reader', 'reader_adf', 'Reader Assembly', 'assembly', '400A', 'FM1-U532-000', [0, 335, 0], [476, 72, 450], [0, 1, 0], 'LIFT')
item('adf', 'reader_adf', 'ADF Unit (envolvente simulada)', 'assembly', None, None, [0, 416, 0], [470, 72, 445], [0, 1, 0], 'LIFT', source_page=151)
group('adf_covers', 'reader_adf', 'Covers', 'cover', 'Figure 160', 44)
group('adf_rollers', 'reader_adf', 'Rollers', 'roller', 'Figure 160', 44)
group('adf_hinges', 'reader_adf', 'Hinges', 'hinge', 'Figure 160', 44)
group('adf_tray', 'reader_adf', 'Tray', 'tray', 'Figure 160', 44)
group('adf_fasteners', 'reader_adf', 'Screws', 'screw', 'Figure 160', 44)
group('adf_guides', 'reader_adf', 'Guides', 'guide', 'Figure 160', 44)
item('adf_rear_cover', 'adf_covers', 'COVER, REAR', 'cover', '160', 'FE8-3474-000', [0, 447, -205], [330, 19, 26], [0, 1, -1])
item('adf_front_cover', 'adf_covers', 'COVER, FRONT', 'cover', '160', 'FE8-3475-000', [0, 447, 205], [330, 19, 26], [0, 1, 1])
item('adf_separation_roller_assembly', 'adf_rollers', 'SEPARATION ROLLER ASSEMBLY', 'roller', '160', 'FM1-N703-000', [-54, 414, 32], [80, 26, 26], [0, 1, 0])
item('adf_pickup_roller', 'adf_rollers', 'ROLLER, PICK-UP', 'roller', '160', 'FC8-9251-000', [30, 424, 57], [54, 17, 17], [0, 1, 0])
item('adf_separation_roller', 'adf_rollers', 'ROLLER, SEPARATION', 'roller', '160', 'FL3-1023-000', [-25, 423, 57], [54, 17, 17], [0, 1, 0])
item('adf_hinge_left', 'adf_hinges', 'HINGE (representación izquierda)', 'hinge', '160', 'FM1-T197-000', [-173, 372, -174], [32, 45, 30], [-1, 0, -1], 'ROTATE_OPEN')
item('adf_hinge_right', 'adf_hinges', 'HINGE (representación derecha)', 'hinge', '160', 'FM1-T197-000', [173, 372, -174], [32, 45, 30], [1, 0, -1], 'ROTATE_OPEN')
item('adf_document_tray', 'adf_tray', 'DOCUMENT TRAY ASSEMBLY', 'tray', '160', 'FM1-N711-000', [0, 439, 120], [320, 13, 190], [0, 1, 1], 'ROTATE_OPEN')
item('adf_screws', 'adf_fasteners', 'SCREW, TP M3X8 (grupo)', 'screw', '160', 'XA9-0476-000', [0, 369, -160], [22, 12, 12], [0, 1, -1], 'UNSCREW')
item('adf_paper_feed_guide', 'adf_guides', 'PAPER FEED GUIDE ASSEMBLY', 'guide', '160', 'FM1-P584-000', [0, 405, 90], [170, 17, 28], [0, 1, 0])
item('adf_cable_guide', 'adf_guides', 'GUIDE, CABLE', 'guide', '160', 'FE8-3462-000', [143, 382, -128], [70, 13, 14], [1, 0, 0])
item('adf_connectors', 'reader_adf', 'Conectores del paso OEM (4x)', 'connector', None, None, [166, 330, -49], [58, 24, 20], [1, 0, 0], 'DISCONNECT', source_page=151)
item('adf_flat_cable', 'reader_adf', 'Cable plano del paso OEM', 'cable', None, None, [137, 342, 0], [90, 5, 18], [1, 0, 0], 'DISCONNECT', source_page=152)

state_specs = [
    ('STATE_00_COMPLETE', None, [], 'SM_R6', 151),
    ('STATE_01_REAR_DOOR_REMOVED', 'rear_door_removed', ['rear_door'], 'SM_R6', 127),
    ('STATE_02_CASSETTE_REMOVED', 'cassette_removed', ['rear_door', 'cassette'], 'SM_R6', 151),
    ('STATE_03_CARTRIDGE_REMOVED', 'cartridge_removed', ['rear_door', 'cassette', 'cartridge'], 'SM_R6', 130),
    ('STATE_04_RIGHT_COVER_REMOVED', 'right_cover_removed', ['rear_door', 'cassette', 'cartridge', 'right_cover'], 'SM_R6', 131),
    ('STATE_05_LEFT_COVER_REMOVED', 'left_cover_removed', ['rear_door', 'cassette', 'cartridge', 'right_cover', 'left_cover'], 'SM_R6', 138),
    ('STATE_06_REAR_TOP_COVER_REMOVED', 'rear_top_cover_removed', ['rear_door', 'cassette', 'cartridge', 'right_cover', 'left_cover', 'rear_top_cover'], 'SM_R6', 142),
    ('STATE_07_ADF_READER_ACCESS', 'ADF_REMOVE_01', ['rear_door', 'cassette', 'cartridge', 'right_cover', 'left_cover', 'rear_top_cover'], 'SM_R6', 151),
    ('STATE_08_ADF_FASTENERS_RELEASED', 'ADF_REMOVE_02', ['rear_door', 'cassette', 'cartridge', 'right_cover', 'left_cover', 'rear_top_cover', 'adf_screws'], 'SM_R6', 151),
    ('STATE_09_ADF_CABLING_RELEASED', 'ADF_REMOVE_03', ['rear_door', 'cassette', 'cartridge', 'right_cover', 'left_cover', 'rear_top_cover', 'adf_screws', 'adf_connectors'], 'SM_R6', 151),
    ('STATE_10_ADF_READER_REMOVED', 'FINAL_REVIEW', ['rear_door', 'cassette', 'cartridge', 'right_cover', 'left_cover', 'rear_top_cover', 'adf_screws', 'adf_connectors', 'adf_flat_cable', 'reader_adf', 'reader', 'adf', 'adf_rear_cover', 'adf_front_cover', 'adf_separation_roller_assembly', 'adf_pickup_roller', 'adf_separation_roller', 'adf_hinge_left', 'adf_hinge_right', 'adf_document_tray', 'adf_paper_feed_guide', 'adf_cable_guide'], 'SM_R6', 152),
]

physical_ids = [item['id'] for item in components if item['geometry']]
states = []
for state_id, step_id, removed, source, page in state_specs:
    states.append({
        'id': state_id, 'procedure_step': step_id,
        'visible_components': [component for component in physical_ids if component not in removed],
        'hidden_components': [], 'removed_components': removed,
        'active_anchors': [step_id] if step_id and step_id.startswith('ADF_REMOVE_') else [],
        'oem_source': {'source_document': source, 'source_page': page},
        'geometry_status': 'SIMULATION_ONLY', 'estimated': True,
    })

animations = {
    'rear_door_removed': ('rear_door', 'REMOVE_LINEAR', [0, 0, -1]),
    'cassette_removed': ('cassette', 'SLIDE', [0, 0, 1]),
    'cartridge_removed': ('cartridge', 'SLIDE', [0, 0, 1]),
    'right_cover_removed': ('right_cover', 'REMOVE_LINEAR', [1, 0, 0]),
    'left_cover_removed': ('left_cover', 'REMOVE_LINEAR', [-1, 0, 0]),
    'rear_top_cover_removed': ('rear_top_cover', 'REMOVE_LINEAR', [0, 1, -1]),
    'ADF_REMOVE_01': ('adf_screws', 'UNSCREW', [0, 1, 0]),
    'ADF_REMOVE_02': ('adf_connectors', 'DISCONNECT', [1, 0, 0]),
    'ADF_REMOVE_03': ('adf_flat_cable', 'DISCONNECT', [1, 0, 0]),
    'ADF_REMOVE_04': ('adf_screws', 'UNSCREW', [0, 1, 0]),
    'ADF_REMOVE_05': ('reader_adf', 'LIFT', [0, 1, 0]),
}

procedure_data = json.loads((ROOT / 'data' / 'procedures' / 'adf_reader.json').read_text(encoding='utf-8'))['procedures'][0]
source_pages = {step['id']: step['source_page']['pdf'] for step in procedure_data['safety_gate'] + procedure_data['preparations']}
source_pages.update({step['step_id']: step['source_page']['pdf'] for step in procedure_data['steps']})
step_map = []
for step_id, (component_id, animation_type, direction) in animations.items():
    step_map.append({
        'procedure_step': step_id, 'component_id': component_id,
        'animation_type': animation_type, 'direction': direction,
        'distance_mm': 90, 'distance_status': 'APPROXIMATED', 'estimated': True,
        'geometry_status': 'SIMULATION_ONLY',
        'oem_source': {'source_document': 'SM_R6', 'source_page': source_pages[step_id]},
    })

model = {
    'schema_version': 1, 'model_id': 'CANON_IR1643I', 'variant': 'WITHOUT_NFC',
    'canonical_unit': 'mm', 'overall_dimensions': {'width_mm': 480, 'depth_mm': 464, 'height_mm': 452,
        'geometry_status': 'OEM_MEASURED', 'estimated': False, 'source_document': 'SM_R6', 'source_page': 21},
    'notice': 'Modelo visual aproximado. La geometría interna y las trayectorias no son medidas OEM.',
    'components': components, 'states': states, 'step_map': step_map,
    'correction_schema': {'key': ['model_id', 'component_id', 'state_id'],
                          'fields': ['scale', 'offset_mm', 'rotation_deg', 'anchor_offset']},
}

output = ROOT_DATA / 'twin_model.json'
output.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'output': str(output), 'components': len(components), 'states': len(states),
                  'step_mappings': len(step_map)}))
