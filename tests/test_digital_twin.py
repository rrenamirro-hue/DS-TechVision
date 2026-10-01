import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import password_hash
from app.digital_twin import (correction_store, dimensions, inventory, model,
                              save_correction, state_for_progress)
from app.main import app
from app.procedures import progress_store, update_progress


def test_oem_dimensions_inventory_and_hierarchy():
    variants = {item['id']: item for item in dimensions()['variants']}
    assert (variants['WITHOUT_NFC']['width_mm'], variants['WITHOUT_NFC']['depth_mm'], variants['WITHOUT_NFC']['height_mm']) == (480, 464, 452)
    assert variants['WITH_NFC']['width_mm'] == 494
    assert all(item['geometry_status'] == 'OEM_MEASURED' and not item['estimated'] for item in variants.values())
    parts = inventory()['parts']
    assert len(inventory()['service_pages']) == 437
    assert len(inventory()['service_mentions']) >= 1000
    assert len(parts) >= 273
    expected = {'FE8-3474-000': 1, 'FE8-3475-000': 1, 'FM1-N703-000': 1,
                'FC8-9251-000': 1, 'FL3-1023-000': 1, 'FM1-T197-000': 2,
                'FM1-P584-000': 1, 'FM1-N711-000': 1, 'XA9-0476-000': 15}
    figure_160 = {item['part_number']: item for item in parts if item['figure'] == '160'}
    assert {number: figure_160[number]['quantity'] for number in expected} == expected
    twin = model(); components = {item['id']: item for item in twin['components']}
    assert twin['overall_dimensions']['geometry_status'] == 'OEM_MEASURED'
    assert components['reader_adf']['parent_id'] == 'equipment'
    for category in ('covers', 'rollers', 'hinges', 'tray', 'screws', 'guides'):
        assert components[f'adf_{category}' if category != 'screws' else 'adf_fasteners']['parent_id'] == 'reader_adf'
    assert components['adf_rear_cover']['parent_id'] == 'adf_covers'
    assert all(item['geometry']['estimated'] and item['geometry_status'] == 'OEM_IMAGE_APPROXIMATED'
               for item in components.values() if item['geometry'])
    assert not any(item['geometry_status'] == 'PHYSICALLY_VALIDATED' for item in components.values())
    assert all(item['explosion']['distance_status'] == 'APPROXIMATED'
               for item in components.values() if item['geometry'])


def test_state_follows_confirmed_procedure_and_corrections_persist(tmp_path):
    old_progress, old_corrections = progress_store.path, correction_store.path
    progress_store.path = tmp_path / 'progress.json'; correction_store.path = tmp_path / 'corrections.json'
    try:
        update_progress('sim', 'ADF_READER_REMOVE', 'start', [])
        assert state_for_progress('sim', 'ADF_READER_REMOVE')['state']['id'] == 'STATE_00_COMPLETE'
        for step_id in ('power_disconnected', 'sharp_edges_acknowledged', 'qualified_technician', 'rear_door_removed'):
            update_progress('sim', 'ADF_READER_REMOVE', 'confirm', [], step_id=step_id)
        state = state_for_progress('sim', 'ADF_READER_REMOVE')
        assert state['state']['id'] == 'STATE_01_REAR_DOOR_REMOVED'
        assert 'rear_door' in state['state']['removed_components']
        for step_id in ('cassette_removed', 'cartridge_removed', 'right_cover_removed',
                        'left_cover_removed', 'rear_top_cover_removed'):
            update_progress('sim', 'ADF_READER_REMOVE', 'confirm', [], step_id=step_id)
        state = state_for_progress('sim', 'ADF_READER_REMOVE')
        assert state['state']['id'] == 'STATE_07_ADF_READER_ACCESS'
        assert state['step_visual']['component_id'] == 'adf_screws'
        assert state['state']['active_anchors'] == []
        update_progress('sim', 'ADF_READER_REMOVE', 'confirm', [], step_id='ADF_REMOVE_01')
        assert state_for_progress('sim', 'ADF_READER_REMOVE')['state']['id'] == 'STATE_08_ADF_FASTENERS_RELEASED'
        update_progress('sim', 'ADF_READER_REMOVE', 'confirm', [], step_id='ADF_REMOVE_02')
        assert state_for_progress('sim', 'ADF_READER_REMOVE')['state']['id'] == 'STATE_09_ADF_CABLING_RELEASED'
        correction = save_correction('sim', {'model_id': 'CANON_IR1643I', 'component_id': 'right_cover',
            'state_id': 'STATE_04_RIGHT_COVER_REMOVED', 'scale': 1.02,
            'offset_mm': [1, 2, 3], 'rotation_deg': [0, 0, 0], 'anchor_offset': [0, 0]})
        assert correction['geometry_status'] == 'PHYSICAL_VALIDATION_REQUIRED'
        assert list(correction_store.read_all().values())[0]['offset_mm'] == [1, 2, 3]
    finally:
        progress_store.path, correction_store.path = old_progress, old_corrections


def test_twin_api_and_simulation_target_are_authenticated(tmp_path, monkeypatch):
    salt = b'0123456789abcdef'
    config = tmp_path / 'auth.json'
    config.write_text(json.dumps({'username': 'sim', 'salt': base64.urlsafe_b64encode(salt).decode(),
        'password_hash': base64.urlsafe_b64encode(password_hash('temporary', salt)).decode(),
        'session_secret': base64.urlsafe_b64encode(b'z' * 32).decode().rstrip('=')}), encoding='utf-8')
    monkeypatch.setenv('DS_TECHVISION_AUTH_CONFIG', str(config))
    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/api/digital-twin').status_code == 401
        assert client.post('/api/auth/login', json={'username': 'sim', 'password': 'temporary'}).status_code == 200
        assert client.get('/api/digital-twin').json()['canonical_unit'] == 'mm'
        assert client.get('/api/digital-twin/inventory?figure=160').json()['parts'][0]['figure'] == '160'
        invalid = client.put('/api/digital-twin/corrections', json={'model_id': 'CANON_IR1643I',
            'component_id': 'unknown', 'state_id': 'STATE_00_COMPLETE'})
        assert invalid.status_code == 409
        target = client.get('/api/digital-twin/target/ADF_READER_REMOVE/right_cover_removed')
        assert target.status_code == 200 and 'Referencia OEM natural' in target.text
        assert '/api/vision/reference/1643_right_service_open/image' in target.text
        assert client.get('/api/digital-twin/target/ADF_READER_REMOVE/ADF_REMOVE_01').status_code == 409
        assert client.get('/api/digital-twin/target/ADF_READER_REMOVE/cassette_removed').status_code == 409
        assert client.get('/static/twin.js').status_code == 200


def test_webgl_and_ar_simulation_contracts():
    twin_js = Path('app/static/twin.js').read_text(encoding='utf-8')
    app_js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert "getContext('webgl'" in twin_js and 'gl.drawArrays' in twin_js
    assert 'setExploded' in twin_js and 'setHideCovers' in twin_js and 'animateStep' in twin_js
    assert 'DSNaturalTracking.Tracker' in app_js and 'drawOverlay' in app_js
    assert 'imageAnchor' in app_js and "currentStep?.id !== match.reference.procedure_step" in app_js
