"""Gates de escritorio para cámara continua sin marcadores."""
import io
import json
import base64

from PIL import Image
from fastapi.testclient import TestClient

from app.auth import password_hash
from app.continuous_vision import (ComponentRecognizer, build_visual_index,
                                   recognize_frame, recognizer)
from app.main import app
from app.procedures import intervention_store, progress_store
from app.vision import VISION_ROOT, catalog, components


def _jpeg(relative: str) -> bytes:
    with Image.open(VISION_ROOT / relative) as image:
        output = io.BytesIO()
        image.convert('RGB').save(output, format='JPEG', quality=78)
        return output.getvalue()


def test_visual_embeddings_persist_and_are_distinct_from_text_index():
    first = build_visual_index()
    again = build_visual_index()
    assert again['state'] == 'LOADED' and first['created_at'] == again['created_at']
    assert again['visual_embedding_model'] == 'openai/clip-vit-base-patch32'
    assert again['embedding_dimension'] == 512 and len(again['reference_ids']) == 10
    assert (VISION_ROOT / 'visual_index' / 'embeddings.npy').is_file()


def test_front_right_and_rear_state_change_without_step_seven():
    front = recognize_frame(_jpeg('equipment/1643_front_closed.png'), 'power_disconnected')
    assert front['model_id'] == 'CANON_IR1643I'
    assert front['view'] == 'FRONT' and front['state'] == 'MACHINE_CLOSED'
    assert front['procedure_visual_guidance'] == 'NONE' and not front['components']
    right = recognize_frame(_jpeg('right/1643_right_service_open.png'), 'right_cover_removed')
    assert right['model_id'] == 'CANON_IR1643I' and right['view'] == 'RIGHT'
    assert right['state'] == 'right_cover_installed_front_access_open'
    assert right['procedure_visual_guidance'] == 'OEM_ANCHORS'
    assert {item['component_type'] for item in right['components']} == {'COVER', 'SCREW'}
    rear = recognize_frame(_jpeg('states/1643_rear_door_removed.png'), 'rear_door_removed')
    assert rear['view'] == 'REAR' and rear['state'] == 'REAR_COVER_REMOVED'
    left = recognize_frame(_jpeg('equipment/1643_left_cover_installed.png'), 'left_cover_removed')
    assert left['view'] == 'LEFT' and left['state'] == 'LEFT_COVER_INSTALLED'
    internal = recognize_frame(_jpeg('states/1643_internal_adf_access.png'), 'ADF_REMOVE_03')
    assert internal['view'] == 'INTERNAL' and internal['state'] == 'ADF_READER_READY'


def test_unknown_image_is_not_claimed_as_canon():
    image = Image.new('RGB', (480, 360), '#202020')
    output = io.BytesIO(); image.save(output, format='JPEG')
    result = recognize_frame(output.getvalue(), 'right_cover_removed')
    assert result['model_id'] == 'UNKNOWN' and result['view'] == 'UNKNOWN'
    assert result['state'] == 'UNKNOWN' and not result['components']
    diagram = recognize_frame(_jpeg('components/reader_adf_figure160.png'))
    assert diagram['model_id'] == 'UNKNOWN', diagram['evidence']['visual_embedding']['top_matches']


def test_rotated_oem_photos_keep_view_and_state():
    for relative, expected in [('equipment/1643_front_closed.png', 'FRONT'),
                               ('right/1643_right_service_open.png', 'RIGHT')]:
        with Image.open(VISION_ROOT / relative) as source:
            image = source.convert('RGB').rotate(8, expand=False, fillcolor='white')
            output = io.BytesIO(); image.save(output, format='JPEG', quality=70)
        result = recognize_frame(output.getvalue())
        assert result['model_id'] == 'CANON_IR1643I' and result['view'] == expected


def test_screw_count_and_parts_catalog_link_are_oem_only():
    right = next(item for item in catalog()['references'] if item['reference_id'] == '1643_right_service_open')
    anchors = ComponentRecognizer().recognize(right['reference_id'], 'right_cover_removed')
    screw = next(item for item in anchors if item['component_type'] == 'SCREW')
    assert screw['expected_count'] == 1 and screw['source']['page'] == 132
    assert screw['part_number'] is None and screw['localization_status'].startswith('REFERENCE_ANCHOR')
    assert ComponentRecognizer().recognize(right['reference_id'], 'power_disconnected') == []
    part = next(item for item in components()['components'] if item['component_id'] == 'adf_pickup_roller')
    inventory = json.loads((VISION_ROOT.parents[1] / 'digital_twin' / 'oem_inventory.json').read_text(encoding='utf-8'))
    assert len(inventory['parts']) == components()['inventory_total'] == 273
    record = next(item for item in inventory['parts'] if item['id'] == part['inventory_id'])
    assert record['part_number'] == part['part_number'] == 'FC8-9251-000'
    assert record['quantity'] == part['quantity'] == 1


def test_authenticated_camera_api_from_first_step(tmp_path, monkeypatch):
    salt = b'0123456789abcdef'
    config = {'username': 'visiontest', 'salt': base64.urlsafe_b64encode(salt).decode(),
              'password_hash': base64.urlsafe_b64encode(password_hash('test-password', salt)).decode(),
              'session_secret': base64.urlsafe_b64encode(b'z' * 32).decode().rstrip('=')}
    path = tmp_path / 'auth.json'; path.write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setenv('DS_TECHVISION_AUTH_CONFIG', str(path))
    old_progress, old_interventions = progress_store.path, intervention_store.path
    progress_store.path = tmp_path / 'progress.json'; intervention_store.path = tmp_path / 'interventions.json'
    try:
        with TestClient(app, base_url='https://testserver') as client:
            frame = _jpeg('equipment/1643_front_closed.png')
            assert client.post('/api/vision/recognize', content=frame).status_code == 401
            client.post('/api/auth/login', json={'username': 'visiontest', 'password': 'test-password'})
            created = client.post('/api/interventions', json={'procedure_id': 'ADF_READER_REMOVE',
                                                               'model_id': 'CANON_IR1643I'}).json()
            response = client.post('/api/vision/recognize', params={'procedure_id': 'ADF_READER_REMOVE',
                'intervention_id': created['intervention_id']}, content=frame)
            assert response.status_code == 200
            result = response.json()
            assert result['model_id'] == 'CANON_IR1643I' and result['view'] == 'FRONT'
            assert result['procedure_visual_guidance'] == 'NONE'
    finally:
        progress_store.path, intervention_store.path = old_progress, old_interventions
