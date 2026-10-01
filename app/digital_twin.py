"""Datos OEM, simulación geométrica y correcciones locales separadas."""
import json
import math
from copy import deepcopy
from functools import lru_cache

from .config import ROOT
from .procedures import JsonStateStore, get_progress

DATA_ROOT = ROOT / 'data' / 'digital_twin'
correction_store = JsonStateStore('twin_corrections.json')


@lru_cache(maxsize=1)
def dimensions() -> dict:
    return json.loads((DATA_ROOT / 'equipment_dimensions.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def inventory() -> dict:
    return json.loads((DATA_ROOT / 'oem_inventory.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def model() -> dict:
    data = json.loads((DATA_ROOT / 'twin_model.json').read_text(encoding='utf-8'))
    ids = {part['id'] for part in data['components']}
    if len(ids) != len(data['components']):
        raise ValueError('Componentes 3D duplicados')
    if any(part['parent_id'] is not None and part['parent_id'] not in ids for part in data['components']):
        raise ValueError('Jerarquía 3D incompleta')
    if any(part.get('geometry_status') == 'PHYSICALLY_VALIDATED' for part in data['components']):
        raise ValueError('No se permite validar físicamente geometría sin equipo real')
    return data


def model_public() -> dict:
    return deepcopy(model())


def inventory_public(figure: str | None = None, category: str | None = None) -> dict:
    data = inventory()
    parts = [part for part in data['parts'] if 'CANON_IR1643I' in part['applicable_models']
             if (figure is None or part['figure'] == figure)
             and (category is None or part['category'] == category)]
    mentions = [item for item in data['service_mentions']
                if figure is None and (category is None or item['category'] == category)]
    return {'model_id': data['model_id'], 'figures': data['figures'], 'parts': parts,
            'returned_parts': len(parts), 'total_catalog_records': len(data['parts']),
            'service_pages_indexed': len(data['service_pages']),
            'service_mentions': mentions, 'returned_service_mentions': len(mentions)}


def state_for_progress(username: str, procedure_id: str, intervention_id: str | None = None) -> dict:
    progress = get_progress(username, procedure_id, intervention_id)
    data = model()
    confirmed = set(progress['confirmed_steps'])
    if 'ADF_REMOVE_05' in confirmed:
        state_id = 'STATE_10_ADF_READER_REMOVED'
    elif 'ADF_REMOVE_02' in confirmed or 'ADF_REMOVE_03' in confirmed or 'ADF_REMOVE_04' in confirmed:
        state_id = 'STATE_09_ADF_CABLING_RELEASED'
    else:
        state_id = 'STATE_00_COMPLETE'
        for step_id, candidate in [
            ('rear_door_removed', 'STATE_01_REAR_DOOR_REMOVED'),
            ('cassette_removed', 'STATE_02_CASSETTE_REMOVED'),
            ('cartridge_removed', 'STATE_03_CARTRIDGE_REMOVED'),
            ('right_cover_removed', 'STATE_04_RIGHT_COVER_REMOVED'),
            ('left_cover_removed', 'STATE_05_LEFT_COVER_REMOVED'),
            ('rear_top_cover_removed', 'STATE_06_REAR_TOP_COVER_REMOVED'),
            ('ADF_REMOVE_01', 'STATE_08_ADF_FASTENERS_RELEASED'),
        ]:
            if step_id in confirmed:
                state_id = candidate
        if 'rear_top_cover_removed' in confirmed and 'ADF_REMOVE_01' not in confirmed:
            state_id = 'STATE_07_ADF_READER_ACCESS'
    state = deepcopy(next(item for item in data['states'] if item['id'] == state_id))
    if state_id == 'STATE_09_ADF_CABLING_RELEASED' and 'ADF_REMOVE_03' in confirmed:
        state['removed_components'].append('adf_flat_cable')
        state['visible_components'].remove('adf_flat_cable')
    active_step = progress['flow_steps'][progress['current_step']] if progress['current_step_id'] else None
    state['active_anchors'] = [active_step['visual_anchor']['reference_id']] if active_step and active_step['ar_available'] else []
    step_visual = next((item for item in data['step_map']
                        if active_step and item['procedure_step'] == active_step['id']), None)
    return {'model_id': data['model_id'], 'state': state,
            'active_step': active_step, 'step_visual': deepcopy(step_visual),
            'progress_status': progress['status'],
            'notice': 'Estado visual aproximado; las fotografías y pasos OEM tienen prioridad.'}


def correction_key(username: str, model_id: str, component_id: str, state_id: str) -> str:
    return f'{username}:{model_id}:{component_id}:{state_id}'


def list_corrections(username: str) -> list[dict]:
    prefix = f'{username}:{model()["model_id"]}:'
    return [deepcopy(value) for key, value in correction_store.read_all().items() if key.startswith(prefix)]


def save_correction(username: str, payload: dict) -> dict:
    data = model()
    if payload['model_id'] != data['model_id']:
        raise ValueError('Modelo no autorizado')
    if payload['component_id'] not in {part['id'] for part in data['components']}:
        raise ValueError('Componente no autorizado')
    if payload['state_id'] not in {state['id'] for state in data['states']}:
        raise ValueError('Estado no autorizado')
    values = [payload['scale'], *payload['offset_mm'], *payload['rotation_deg'], *payload['anchor_offset']]
    if not all(math.isfinite(value) for value in values):
        raise ValueError('La corrección debe contener valores finitos')
    if any(abs(value) > 1000 for value in payload['offset_mm']):
        raise ValueError('Offset fuera del rango de simulación')
    if any(abs(value) > 360 for value in payload['rotation_deg']):
        raise ValueError('Rotación fuera del rango de simulación')
    if any(abs(value) > 5 for value in payload['anchor_offset']):
        raise ValueError('Anchor fuera del rango de simulación')
    record = {**payload, 'geometry_status': 'PHYSICAL_VALIDATION_REQUIRED',
              'estimated': True, 'source': 'LOCAL_CORRECTION_UNVALIDATED'}
    return correction_store.put(correction_key(username, payload['model_id'], payload['component_id'],
                                               payload['state_id']), record)
