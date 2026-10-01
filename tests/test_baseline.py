import base64
import ipaddress
import json
from pathlib import Path

import fitz
from cryptography import x509
from fastapi.testclient import TestClient

from app.auth import password_hash
from app.config import MANUALS
from app.generate_tls import generate
from app.ingest import build_index
from app.main import app, get_retriever
from app.retriever import LocalRetriever
from app.procedures import (build_flow, calibration_store, get_calibration, get_progress,
                            load_catalog, progress_store, render_flow_reference, render_step_reference,
                            save_calibration, update_progress)


def _create_fixture_corpus(path: Path):
    path.mkdir(parents=True)
    text = {'SM_R6': 'Removing the Cassette Pickup Roller. Disconnect the power plug before disassembly.',
            'PC_R9': 'Part number RM2-5741-000 PAPER PICK-UP ROLLER ASSY. ROLLER TRANSFER.'}
    for name, info in MANUALS.items():
        pdf = fitz.open(); page = pdf.new_page(); page.insert_text((70, 70), text[name]); pdf.save(path / info['file']); pdf.close()


def _auth_config(path: Path, username='tecnico', password='correct horse battery staple'):
    salt = b'0123456789abcdef'
    path.write_text(json.dumps({'username': username,
                                'salt': base64.urlsafe_b64encode(salt).decode(),
                                'password_hash': base64.urlsafe_b64encode(password_hash(password, salt)).decode(),
                                'session_secret': base64.urlsafe_b64encode(b'x' * 32).decode().rstrip('=')}), encoding='utf-8')
    return username, password


def test_ingest_and_bilingual_retrieval(tmp_path):
    originals, index = tmp_path / 'manuals', tmp_path / 'index'; _create_fixture_corpus(originals)
    result = build_index(originals, index); assert result['chunks'] >= 2; assert result['documents']['SM_R6']['pages'] == 1
    hits = LocalRetriever(index).search('rodillo de recogida', 'CANON_IR1643I', limit=5)
    assert hits and hits[0]['document_id'] in {'SM_R6', 'PC_R9'}; assert hits[0]['pdf_page'] == 1; assert '?page=1' in hits[0]['source_url']
    assert LocalRetriever(index).search('rodillo de recogida', 'CANON_IR1643I', doc_id='PC_R9')[0]['document_id'] == 'PC_R9'
    assert json.loads((index / 'manifest.json').read_text())['documents']['PC_R9']['sha256']


def test_authentication_protects_app_search_and_manuals(tmp_path, monkeypatch):
    config = tmp_path / 'auth.json'; username, password = _auth_config(config); monkeypatch.setenv('DS_TECHVISION_AUTH_CONFIG', str(config))
    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/', follow_redirects=False).status_code == 303
        assert client.get('/api/status').status_code == 401
        assert client.get('/api/manual/SM_R6').status_code == 401
        assert client.get('/api/procedures').status_code == 401
        assert client.get('/api/vision/references').status_code == 401
        assert client.post('/api/auth/login', json={'username': username, 'password': 'wrong'}).status_code == 401
        login = client.post('/api/auth/login', json={'username': username, 'password': password})
        assert login.status_code == 200; assert 'HttpOnly' in login.headers['set-cookie']; assert 'Secure' in login.headers['set-cookie']; assert 'SameSite=lax' in login.headers['set-cookie']
        assert client.get('/').status_code == 200; assert client.get('/api/status').status_code == 200
        assert client.get('/api/procedures').status_code == 200
        visual = client.get('/api/vision/references')
        assert visual.status_code == 200 and len(visual.json()['references']) >= 7
        assert len(client.get('/api/vision/components').json()['components']) == 3
        assert client.get('/api/vision/reference/1643_right_service_open/image').headers['content-type'] == 'image/png'
        assert client.post('/api/vision/ocr', content=b'bad').status_code == 422
        reference = client.get('/api/procedures/ADF_READER_REMOVE/steps/ADF_REMOVE_01/reference')
        assert reference.status_code == 200 and reference.headers['content-type'] == 'image/png'
        preparation = client.get('/api/procedures/ADF_READER_REMOVE/flow/right_cover_removed/reference')
        assert preparation.status_code == 200 and preparation.headers['content-type'] == 'image/png'
        assert client.get('/api/manual/SM_R6').status_code == 200; assert client.get('/api/manual/not-allowed').status_code == 404
        assert client.post('/api/buscar', json={'question': 'ab'}).status_code == 422
        assert client.post('/api/buscar', json={'question': 'rodillo', 'model_id': 'CANON_IR1643II'}).status_code == 422
        result = client.post('/api/buscar', json={'question': 'rodillo de recogida'}); assert result.status_code == 200; assert result.json()['results']
        assert client.post('/api/auth/logout').status_code == 200
        get_retriever.cache_clear()


def test_pwa_headers_and_camera_contract():
    with TestClient(app, base_url='https://testserver') as client:
        assert client.get('/health').json()['version'] == '0.6-continuous-vision'
        manifest = client.get('/manifest.webmanifest'); assert manifest.status_code == 200; assert manifest.json()['display'] == 'standalone'
        assert client.get('/service-worker.js').status_code == 200
        assert client.get('/static/icons/icon-192.png').status_code == 200
        assert 'microphone=()' in client.get('/health').headers['permissions-policy']
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert "facing = 'environment'" in js; assert 'getUserMedia' in js; assert 'audio: false' in js
    assert "visibilitychange" in js; assert 'getTracks().forEach' in js; assert 'NotAllowedError' in js
    assert 'DSNaturalTracking.Tracker' in js and 'drawOverlay' in js and 'cameraFallback' in js
    service_worker = Path('app/static/service-worker.js').read_text(encoding='utf-8')
    assert "url.pathname.startsWith('/api/')" in service_worker; assert "url.pathname === '/'" in service_worker


def test_tls_certificate_contains_private_ip(tmp_path):
    address = ipaddress.ip_address('192.168.50.25'); generate(address, tmp_path)
    cert = x509.load_pem_x509_certificate((tmp_path / 'server-cert.pem').read_bytes())
    sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert address in sans.get_values_for_type(x509.IPAddress)
    assert cert.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
    assert (tmp_path / 'server-key.pem').is_file(); assert (tmp_path / 'ca-cert.cer').is_file()


def test_oem_procedure_traceability_and_order():
    catalog = load_catalog(); removal, separation = catalog['procedures']
    assert removal['procedure_id'] == 'ADF_READER_REMOVE'; assert separation['procedure_id'] == 'ADF_READER_SEPARATE'
    assert separation['steps'] == [] and separation['status'] == 'reference_only_not_enabled_for_ar'
    assert [item['order'] for item in removal['preparations']] == [1, 2, 3, 4, 5, 6]
    assert [(page['printed'], page['pdf']) for page in removal['source_pages']] == [(140, 151), (141, 152)]
    assert removal['related_parts_figure']['figure'].startswith('160')
    assert [step['step_id'] for step in removal['steps']] == [f'ADF_REMOVE_0{i}' for i in range(1, 6)]
    required = {'step_id','procedure_id','model_id','title','instruction','preconditions','safety_warnings','required_actions','target_components','part_numbers','source_document','source_page','source_figure','reference_image','visual_anchor','expected_confirmation'}
    for step in removal['steps']:
        assert required <= set(step); assert step['source_page']['pdf'] in {151, 152}; assert step['model_id'] == 'CANON_IR1643I'; assert step['visual_anchor']['tracking_mode'] == 'not_mapped'
    flow = build_flow(removal)
    assert len(flow) == 15
    assert [step['phase'] for step in flow] == ['A'] * 3 + ['B'] * 6 + ['C'] * 5 + ['D']
    assert [step['id'] for step in flow[3:9]] == [
        'rear_door_removed', 'cassette_removed', 'cartridge_removed', 'right_cover_removed',
        'left_cover_removed', 'rear_top_cover_removed',
    ]
    assert all({'id', 'type', 'title', 'description', 'warnings', 'actions', 'image_oem',
                'state', 'ar_available'} <= set(step) for step in flow)
    assert [step['id'] for step in flow if step['ar_available']] == ['right_cover_removed']
    assert flow[6]['source_page'] == {'printed': 121, 'pdf': 132}
    png = render_step_reference('ADF_READER_REMOVE', 'ADF_REMOVE_03')
    assert png.startswith(b'\x89PNG') and len(png) > 10_000
    preparation_png = render_flow_reference('ADF_READER_REMOVE', 'right_cover_removed')
    assert preparation_png.startswith(b'\x89PNG') and len(preparation_png) > 10_000


def test_progress_confirmation_and_calibration_persist(tmp_path):
    progress_store.path = tmp_path / 'progress.json'; calibration_store.path = tmp_path / 'calibration.json'
    flow = build_flow(load_catalog()['procedures'][0])
    progress_store.put('legacy:ADF_READER_REMOVE', {
        'procedure_id': 'ADF_READER_REMOVE', 'status': 'in_progress', 'current_step': 3,
        'confirmed_steps': ['ADF_REMOVE_01', 'ADF_REMOVE_02', 'ADF_REMOVE_03'], 'history': [], 'updated_at': None,
    })
    legacy = get_progress('legacy', 'ADF_READER_REMOVE')
    assert legacy['status'] == 'not_started' and legacy['current_step_id'] == 'power_disconnected'
    assert legacy['confirmed_steps'] == [] and legacy['history'][-1]['action'] == 'flow_v2_reset'
    state = update_progress('tech', 'ADF_READER_REMOVE', 'start', [])
    assert state['current_step'] == 0 and state['current_step_id'] == 'power_disconnected'
    assert state['flow_steps'][0]['state'] == 'en_curso' and state['flow_steps'][1]['state'] == 'bloqueado'
    try:
        update_progress('tech', 'ADF_READER_REMOVE', 'confirm', [], step_id='ADF_REMOVE_04')
        assert False, 'Un paso avanzado debió ser rechazado'
    except ValueError as exc:
        assert 'power_disconnected' in str(exc)
    for index, step in enumerate(flow[:-1]):
        state = update_progress('tech', 'ADF_READER_REMOVE', 'confirm', [], step_id=step['id'])
        assert state['current_step'] == index + 1
    assert state['current_step_id'] == 'FINAL_REVIEW'
    state = update_progress('tech', 'ADF_READER_REMOVE', 'pause', []); assert state['status'] == 'paused'
    try:
        update_progress('tech', 'ADF_READER_REMOVE', 'confirm', [], step_id='FINAL_REVIEW')
        assert False, 'Un flujo pausado no debe permitir confirmar'
    except ValueError:
        pass
    state = update_progress('tech', 'ADF_READER_REMOVE', 'resume', []); assert state['status'] == 'in_progress'
    state = update_progress('tech', 'ADF_READER_REMOVE', 'confirm', [], step_id='FINAL_REVIEW')
    assert state['status'] == 'completed' and len(state['confirmed_steps']) == 15
    assert get_progress('tech', 'ADF_READER_REMOVE')['history'][-1]['step_id'] == 'FINAL_REVIEW'
    try:
        save_calibration('tech', 'ADF_READER_REMOVE', 'ADF_REMOVE_02', {'reference_id':'ADF_REMOVE_02','u':1.4,'v':-.3,'radius':.25})
        assert False, 'No debe calibrarse un paso sin referencia natural mapeada'
    except ValueError:
        pass
