"""Procedimientos OEM estructurados y estado de ejecución persistente."""
import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pymupdf

from .config import MANUALS, MANUALS_DIR, ROOT

PROCEDURES_FILE = ROOT / 'data' / 'procedures' / 'adf_reader.json'


def state_root() -> Path:
    base = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / '.ds_techvision'))
    return base / 'DataSystems' / 'DS_TechVision' / 'state'


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    data = json.loads(PROCEDURES_FILE.read_text(encoding='utf-8'))
    required = {'step_id', 'procedure_id', 'model_id', 'title', 'instruction', 'preconditions',
                'safety_warnings', 'required_actions', 'target_components', 'part_numbers',
                'source_document', 'source_page', 'source_figure', 'reference_image',
                'visual_anchor', 'expected_confirmation'}
    for procedure in data['procedures']:
        for index, step in enumerate(procedure['steps']):
            missing = required - set(step)
            if missing:
                raise ValueError(f"Paso {step.get('step_id', index)} incompleto: {sorted(missing)}")
            if step['procedure_id'] != procedure['procedure_id']:
                raise ValueError(f"Paso {step['step_id']} asociado al procedimiento incorrecto")
    return data


def get_procedure(procedure_id: str) -> dict:
    for procedure in load_catalog()['procedures']:
        if procedure['procedure_id'] == procedure_id:
            return deepcopy(procedure)
    raise KeyError(procedure_id)


def get_step(procedure_id: str, step_id: str) -> dict:
    procedure = get_procedure(procedure_id)
    for step in procedure['steps']:
        if step['step_id'] == step_id:
            return step
    raise KeyError(step_id)


def public_catalog() -> dict:
    data = deepcopy(load_catalog())
    for procedure in data['procedures']:
        for step in procedure['steps']:
            step.pop('reference_crop', None)
        procedure['flow_steps'] = build_flow(procedure)
    return data


SAFETY_TITLES = {
    'power_disconnected': 'Aislar la alimentación eléctrica',
    'sharp_edges_acknowledged': 'Reconocer riesgos mecánicos',
    'qualified_technician': 'Confirmar personal autorizado',
}

PREPARATION_TITLES = {
    'rear_door_removed': 'Retirar la carcasa trasera',
    'cassette_removed': 'Retirar el cassette',
    'cartridge_removed': 'Retirar el cartridge',
    'right_cover_removed': 'Retirar la cubierta lateral derecha',
    'left_cover_removed': 'Retirar la cubierta lateral izquierda',
    'rear_top_cover_removed': 'Retirar la cubierta superior trasera',
}


def _reference_url(procedure_id: str, step_id: str) -> str:
    return f'/api/procedures/{procedure_id}/flow/{step_id}/reference'


def build_flow(procedure: dict) -> list[dict]:
    """Normaliza seguridad, preparaciones, OEM y cierre en una única secuencia."""
    procedure_id = procedure['procedure_id']
    if not procedure['steps']:
        return []
    flow = []
    for item in procedure['safety_gate']:
        page = item['source_page']
        flow.append({
            'id': item['id'], 'type': 'seguridad', 'phase': 'A', 'phase_label': 'Seguridad',
            'title': SAFETY_TITLES.get(item['id'], 'Control de seguridad'),
            'description': item['instruction'], 'warnings': item.get('safety_warnings', []),
            'actions': [item['instruction']], 'image_oem': _reference_url(procedure_id, item['id']),
            'state': 'pendiente', 'ar_available': False, 'visual_anchor': None,
            'source_document': item.get('source_document', procedure['source_document']),
            'source_page': page, 'source_figure': 'Safety instructions',
        })
    for item in sorted(procedure['preparations'], key=lambda value: value['order']):
        page = item['source_page']
        is_demo = item['id'] == 'right_cover_removed'
        if is_demo:
            page = {'printed': 121, 'pdf': 132}
        flow.append({
            'id': item['id'], 'type': 'preparacion', 'phase': 'B',
            'phase_label': 'Preparaciones previas',
            'title': PREPARATION_TITLES.get(item['id'], f"Preparación {item['order']}"),
            'description': ('Retirar la cubierta derecha siguiendo la secuencia OEM. La figura muestra un tornillo, la liberación inicial y el apoyo a 100 mm del borde.'
                            if is_demo else item['instruction']), 'warnings': item.get('safety_warnings', []),
            'actions': (['Retirar el tornillo indicado y liberar la cubierta según la figura OEM.',
                         'Verificar la secuencia completa en las páginas impresas 121 a 123 antes de confirmar.']
                        if is_demo else [item['instruction'], 'Verificar visualmente que la pieza quedó retirada antes de confirmar.']),
            'image_oem': _reference_url(procedure_id, item['id']), 'state': 'pendiente',
            'ar_available': is_demo, 'visual_anchor': ({'reference_id': '1643_right_service_open',
                'reference_image': '/api/vision/reference/1643_right_service_open/image',
                'tracking_mode': 'natural_orb_ransac'} if is_demo else None),
            'source_document': item.get('source_document', procedure['source_document']),
            'source_page': page, 'source_figure': f"Preparation {item['order']}",
        })
    for item in procedure['steps']:
        flow.append({
            'id': item['step_id'], 'type': 'procedimiento', 'phase': 'C',
            'phase_label': 'Procedimiento OEM principal', 'title': item['title'],
            'description': item['instruction'], 'warnings': item['safety_warnings'],
            'actions': item['required_actions'], 'image_oem': item['reference_image'],
            'state': 'pendiente', 'ar_available': False, 'visual_anchor': None,
            'target_name': ', '.join(item['target_components']),
            'source_document': item['source_document'], 'source_page': item['source_page'],
            'source_figure': item['source_figure'], 'expected_confirmation': item['expected_confirmation'],
        })
    final_page = procedure['source_pages'][-1]
    flow.append({
        'id': 'FINAL_REVIEW', 'type': 'finalizacion', 'phase': 'D',
        'phase_label': 'Finalización', 'title': 'Verificar y cerrar la intervención',
        'description': 'Comprobar que el conjunto fue retirado de forma segura, que no quedan cables bajo tensión y que las piezas y fijaciones están identificadas para el montaje.',
        'warnings': ['No energizar el equipo mientras el desmontaje permanezca abierto.'],
        'actions': ['Revisar el área intervenida.', 'Ordenar y etiquetar tornillos, cubiertas y conectores.', 'Registrar la intervención como finalizada.'],
        'image_oem': _reference_url(procedure_id, 'FINAL_REVIEW'), 'state': 'pendiente',
        'ar_available': False, 'visual_anchor': None, 'source_document': procedure['source_document'],
        'source_page': final_page, 'source_figure': 'Final OEM verification',
    })
    return flow


def get_flow_step(procedure_id: str, flow_step_id: str) -> dict:
    procedure = get_procedure(procedure_id)
    for step in build_flow(procedure):
        if step['id'] == flow_step_id:
            return step
    raise KeyError(flow_step_id)


@lru_cache(maxsize=32)
def render_step_reference(procedure_id: str, step_id: str) -> bytes:
    step = get_step(procedure_id, step_id)
    meta = MANUALS[step['source_document']]
    page_number = int(step['source_page']['pdf'])
    crop = pymupdf.Rect(*step['reference_crop'])
    with pymupdf.open(MANUALS_DIR / meta['file']) as document:
        page = document[page_number - 1]
        crop &= page.rect
        return page.get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7), clip=crop, alpha=False).tobytes('png')


@lru_cache(maxsize=64)
def render_flow_reference(procedure_id: str, flow_step_id: str) -> bytes:
    flow_step = get_flow_step(procedure_id, flow_step_id)
    if flow_step['type'] == 'procedimiento':
        return render_step_reference(procedure_id, flow_step_id)
    meta = MANUALS[flow_step['source_document']]
    page_number = int(flow_step['source_page']['pdf'])
    with pymupdf.open(MANUALS_DIR / meta['file']) as document:
        page = document[page_number - 1]
        if flow_step_id == 'right_cover_removed':
            return page.get_pixmap(matrix=pymupdf.Matrix(2.2, 2.2),
                                   clip=pymupdf.Rect(200, 88, 414, 246), alpha=False).tobytes('png')
        return page.get_pixmap(matrix=pymupdf.Matrix(1.15, 1.15), alpha=False).tobytes('png')


class JsonStateStore:
    def __init__(self, filename: str):
        self.path = state_root() / filename
        self.lock = threading.Lock()

    def read_all(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {}

    def write_all(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_suffix('.pending')
        pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        pending.replace(self.path)

    def get(self, key: str, default=None):
        with self.lock:
            return deepcopy(self.read_all().get(key, default))

    def put(self, key: str, value: dict):
        with self.lock:
            data = self.read_all(); data[key] = value; self.write_all(data)
        return deepcopy(value)


progress_store = JsonStateStore('progress.json')
intervention_store = JsonStateStore('interventions.json')
calibration_store = JsonStateStore('calibration.json')


def initial_progress(procedure_id: str) -> dict:
    return {'schema_version': 2, 'procedure_id': procedure_id, 'status': 'not_started',
            'current_step': 0, 'confirmed_steps': [], 'history': [], 'updated_at': None}


def progress_key(username: str, procedure_id: str, intervention_id: str | None = None) -> str:
    return f'{username}:{intervention_id}:{procedure_id}' if intervention_id else f'{username}:{procedure_id}'


def get_progress(username: str, procedure_id: str, intervention_id: str | None = None) -> dict:
    procedure = get_procedure(procedure_id)
    if intervention_id:
        require_intervention(username, intervention_id, procedure_id)
    state = progress_store.get(progress_key(username, procedure_id, intervention_id), initial_progress(procedure_id))
    state = _migrate_progress(state, procedure)
    view = _progress_view(state, procedure)
    view['intervention_id'] = intervention_id
    return view


def list_interventions(username: str, procedure_id: str) -> list[dict]:
    get_procedure(procedure_id)
    return sorted((deepcopy(item) for item in intervention_store.read_all().values()
                   if item['username'] == username and item['procedure_id'] == procedure_id),
                  key=lambda item: item['created_at'], reverse=True)


def require_intervention(username: str, intervention_id: str, procedure_id: str) -> dict:
    item = intervention_store.get(intervention_id)
    if not item or item['username'] != username or item['procedure_id'] != procedure_id:
        raise KeyError(intervention_id)
    return item


def create_intervention(username: str, procedure_id: str, model_id: str) -> dict:
    procedure = get_procedure(procedure_id)
    if procedure.get('status') == 'reference_only_not_enabled_for_ar' or not build_flow(procedure):
        raise ValueError('Este procedimiento está disponible solo como referencia OEM')
    if load_catalog()['model_id'] != model_id:
        raise ValueError('Modelo no corresponde al procedimiento')
    now = datetime.now(timezone.utc).isoformat()
    day = datetime.now().strftime('%Y%m%d')
    with intervention_store.lock:
        records = intervention_store.read_all()
        sequence = max((int(key.rsplit('-', 1)[1]) for key in records
                        if key.startswith(f'TV-{day}-') and key.rsplit('-', 1)[1].isdigit()), default=0) + 1
        intervention_id = f'TV-{day}-{sequence:04d}'
        item = {'intervention_id': intervention_id, 'username': username,
                'procedure_id': procedure_id, 'model_id': model_id, 'status': 'in_progress',
                'created_at': now, 'updated_at': now, 'closed_at': None}
        progress = initial_progress(procedure_id)
        progress.update(status='in_progress', updated_at=now)
        progress['history'].append({'action': 'start', 'step_index': 0, 'step_id': None, 'note': '', 'at': now})
        progress_store.put(progress_key(username, procedure_id, intervention_id), progress)
        records[intervention_id] = item
        intervention_store.write_all(records)
    return get_progress(username, procedure_id, intervention_id)


def _migrate_progress(state: dict, procedure: dict) -> dict:
    if state.get('schema_version') == 2:
        return state
    migrated = initial_progress(procedure['procedure_id'])
    migrated['history'] = deepcopy(state.get('history', []))
    migrated['history'].append({
        'action': 'flow_v2_reset', 'step_index': 0, 'step_id': None,
        'note': 'El flujo anterior se reinició para exigir seguridad y preparaciones paso a paso.',
        'at': datetime.now(timezone.utc).isoformat(),
    })
    return migrated


def _progress_view(state: dict, procedure: dict) -> dict:
    view = deepcopy(state)
    flow = build_flow(procedure)
    confirmed = set(state.get('confirmed_steps', []))
    for index, step in enumerate(flow):
        if step['id'] in confirmed:
            step['state'] = 'completado'
        elif state['status'] in {'in_progress', 'paused'} and index == state['current_step']:
            step['state'] = 'en_curso'
        elif state['status'] == 'not_started' and index == 0:
            step['state'] = 'pendiente'
        else:
            step['state'] = 'bloqueado'
    view['flow_steps'] = flow
    view['total_steps'] = len(flow)
    view['current_step_id'] = flow[state['current_step']]['id'] if flow and state['status'] != 'completed' else None
    return view


def update_progress(username: str, procedure_id: str, action: str, confirmations: list[str],
                    note: str = '', step_id: str | None = None,
                    intervention_id: str | None = None) -> dict:
    procedure = get_procedure(procedure_id)
    flow = build_flow(procedure)
    if not flow:
        raise ValueError('Este procedimiento está disponible solo como referencia OEM')
    if intervention_id:
        require_intervention(username, intervention_id, procedure_id)
    key = progress_key(username, procedure_id, intervention_id)
    state = _migrate_progress(progress_store.get(key, initial_progress(procedure_id)), procedure)
    now = datetime.now(timezone.utc).isoformat()
    if action == 'start':
        if state['status'] != 'not_started':
            raise ValueError('El procedimiento ya fue iniciado')
        state.update(status='in_progress', current_step=0, confirmed_steps=[])
    elif action == 'confirm':
        if state['status'] not in {'in_progress', 'paused'}:
            raise ValueError('El procedimiento no está iniciado')
        if state['status'] == 'paused':
            raise ValueError('Reanude el procedimiento antes de confirmar el paso')
        index = state['current_step']; expected_id = flow[index]['id']
        if step_id != expected_id:
            raise ValueError(f'Paso bloqueado: debe completar primero {expected_id}')
        if expected_id not in state['confirmed_steps']:
            state['confirmed_steps'].append(expected_id)
        if index + 1 >= len(flow):
            state['status'] = 'completed'
        else:
            state['current_step'] = index + 1; state['status'] = 'in_progress'
    elif action == 'pause':
        if state['status'] == 'in_progress': state['status'] = 'paused'
    elif action == 'resume':
        if state['status'] == 'paused': state['status'] = 'in_progress'
    else:
        raise ValueError('Acción de progreso no válida')
    state['history'].append({'action': action, 'step_index': state['current_step'],
                             'step_id': step_id, 'note': note, 'at': now})
    state['updated_at'] = now
    progress_store.put(key, state)
    if intervention_id:
        with intervention_store.lock:
            records = intervention_store.read_all()
            item = records[intervention_id]
            item['status'] = state['status']; item['updated_at'] = now
            if state['status'] == 'completed': item['closed_at'] = now
            intervention_store.write_all(records)
    view = _progress_view(state, procedure)
    view['intervention_id'] = intervention_id
    return view


def calibration_key(username: str, procedure_id: str, step_id: str) -> str:
    return f'{username}:{procedure_id}:{step_id}'


def get_calibration(username: str, procedure_id: str, step_id: str):
    get_step(procedure_id, step_id)
    return calibration_store.get(calibration_key(username, procedure_id, step_id))


def save_calibration(username: str, procedure_id: str, step_id: str, anchor: dict) -> dict:
    step = get_step(procedure_id, step_id)
    if anchor['reference_id'] != step['visual_anchor']['reference_id']:
        raise ValueError('La referencia no corresponde al paso')
    record = {'procedure_id': procedure_id, 'step_id': step_id, 'reference_id': anchor['reference_id'],
              'u': anchor['u'], 'v': anchor['v'], 'radius': anchor['radius'],
              'status': 'LOCAL_UNVALIDATED', 'updated_at': datetime.now(timezone.utc).isoformat()}
    return calibration_store.put(calibration_key(username, procedure_id, step_id), record)
