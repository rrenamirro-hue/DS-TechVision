"""Comprobaciones focalizadas para las correcciones 0.5.1."""
import base64
import json

from fastapi.testclient import TestClient

from app.auth import password_hash
from app.config import INDEX_DIR
from app.ingest import build_index
from app.main import app
from app.procedures import (build_flow, create_intervention, get_progress,
                            get_procedure, intervention_store, list_interventions,
                            progress_store, update_progress)
from app.retriever import LocalRetriever, build_embedding_index

PROCEDURE = 'ADF_READER_REMOVE'
MODEL = 'CANON_IR1643I'


def test_new_closed_repeat_resume_and_legacy_are_separate(tmp_path):
    old_progress, old_interventions = progress_store.path, intervention_store.path
    progress_store.path = tmp_path / 'progress.json'
    intervention_store.path = tmp_path / 'interventions.json'
    try:
        progress_store.put(f'tech:{PROCEDURE}', {'schema_version': 2, 'procedure_id': PROCEDURE,
                           'status': 'completed', 'current_step': 14, 'confirmed_steps': [],
                           'history': [], 'updated_at': None})
        first = create_intervention('tech', PROCEDURE, MODEL)
        # TEST 1: nueva intervención inicia 0/15 y paso 1.
        assert first['current_step'] == 0 and first['total_steps'] == 15
        assert first['current_step_id'] == 'power_disconnected'
        assert not first['confirmed_steps'] and first['status'] == 'in_progress'
        # TEST 3: el legado y la primera intervención permanecen intactos.
        assert get_progress('tech', PROCEDURE)['status'] == 'completed'
        assert progress_store.get(f'tech:{PROCEDURE}')['status'] == 'completed'
        assert list_interventions('tech', PROCEDURE)[0]['intervention_id'] == first['intervention_id']
        for step in build_flow(get_procedure(PROCEDURE)):
            update_progress('tech', PROCEDURE, 'confirm', [], step_id=step['id'],
                            intervention_id=first['intervention_id'])
        assert get_progress('tech', PROCEDURE, first['intervention_id'])['status'] == 'completed'
        second = create_intervention('tech', PROCEDURE, MODEL)
        # TEST 2: la instancia nueva vuelve a cero sin sobreescribir la cerrada.
        assert second['intervention_id'] != first['intervention_id']
        assert second['current_step'] == 0 and second['total_steps'] == 15
        assert get_progress('tech', PROCEDURE, first['intervention_id'])['status'] == 'completed'
        assert len(list_interventions('tech', PROCEDURE)) == 2
        # Reanudar conserva el progreso y acceso entre usuarios queda aislado.
        update_progress('tech', PROCEDURE, 'confirm', [], step_id='power_disconnected',
                        intervention_id=second['intervention_id'])
        assert get_progress('tech', PROCEDURE, second['intervention_id'])['current_step'] == 1
        try:
            get_progress('other', PROCEDURE, second['intervention_id'])
            assert False, 'Intervención ajena accesible'
        except KeyError:
            pass
    finally:
        progress_store.path, intervention_store.path = old_progress, old_interventions


def test_manual_authenticated_and_denied(tmp_path, monkeypatch):
    salt = b'0123456789abcdef'
    config = {'username': 'manualtest', 'salt': base64.urlsafe_b64encode(salt).decode(),
              'password_hash': base64.urlsafe_b64encode(password_hash('test-password', salt)).decode(),
              'session_secret': base64.urlsafe_b64encode(b'y' * 32).decode().rstrip('=')}
    path = tmp_path / 'auth.json'; path.write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setenv('DS_TECHVISION_AUTH_CONFIG', str(path))
    with TestClient(app, base_url='https://testserver') as client:
        # TEST 5: el visor, la imagen y el PDF siguen privados.
        assert client.get('/api/manual/SM_R6').status_code == 401
        assert client.get('/api/manual/SM_R6/page/132').status_code == 401
        assert client.get('/manual/view/SM_R6?page=132', follow_redirects=False).status_code == 303
        login = client.post('/api/auth/login', json={'username': 'manualtest', 'password': 'test-password'})
        assert 'HttpOnly' in login.headers['set-cookie']
        assert 'SameSite=lax' in login.headers['set-cookie']
        assert 'Secure' in login.headers['set-cookie']
        assert 'Path=/' in login.headers['set-cookie']
        # TEST 4: navegación directa con cookie ve página OEM y PDF completo.
        view = client.get('/manual/view/SM_R6?page=132')
        assert view.status_code == 200 and b'api/manual/SM_R6#page=132' in view.content
        image = client.get('/api/manual/SM_R6/page/132')
        assert image.status_code == 200 and image.content.startswith(b'\x89PNG')
        pdf = client.get('/api/manual/SM_R6')
        assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')


def test_real_semantic_exact_and_persistent_index():
    build_index()
    first = build_embedding_index()
    second = build_embedding_index()
    # TEST 8: índice persistente, mismo timestamp y sin recálculo.
    assert second['state'] == 'LOADED'
    assert first['created_at'] == second['created_at']
    assert second['embedding_dimension'] == 384
    retriever = LocalRetriever()
    # TEST 6: una pregunta española llega a la sección OEM inglesa.
    semantic = retriever.search('cómo retirar el rodillo de recogida del ADF', MODEL, 'SM_R6', 8)
    assert any(item['pdf_page'] in {157, 158} for item in semantic)
    # TEST 7: código literal gana a la semejanza semántica.
    exact = retriever.search('FC8-9251-000', MODEL, limit=3)
    assert exact and exact[0]['exact_identifier_match']
    assert 'FC8-9251-000' in exact[0]['excerpt']
