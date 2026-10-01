from pathlib import Path

from app.main import app
from app.procedures import build_flow, get_procedure


def test_single_ar_case_and_oem_source():
    flow = build_flow(get_procedure('ADF_READER_REMOVE'))
    assert len(flow) == 15
    assert [item['id'] for item in flow if item['ar_available']] == ['right_cover_removed']
    demo = next(item for item in flow if item['id'] == 'right_cover_removed')
    assert demo['source_document'] == 'SM_R6'
    assert demo['source_page'] == {'printed': 121, 'pdf': 132}
    assert demo['image_oem'].endswith('/right_cover_removed/reference')
    assert all(not item['ar_available'] for item in flow if item['phase'] == 'C')


def test_reference_uses_natural_features_without_markers():
    route = next(route for route in app.routes if getattr(route, 'path', '') == '/api/vision/reference/{reference_id}/display')
    html = route.endpoint('1643_right_service_open')
    assert 'Referencia OEM natural' in html and 'rasgos naturales' in html
    assert 'corner orange' not in html and 'QR' not in html
    tracker = Path('app/static/natural-tracking.js').read_text(encoding='utf-8')
    assert 'orb.describe' in tracker and 'motion_estimator.ransac' in tracker
    assert 'function project' in tracker and 'return null' in tracker


def test_step_first_mobile_structure_and_lab_is_separate():
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    script = Path('app/static/app.js').read_text(encoding='utf-8')
    assert 'Ver todos los pasos' in script
    assert all(f'data-view="{name}"' in html for name in ('guide', 'camera', 'manual'))
    assert 'id="labView" class="technician-view" hidden' in html
    assert 'if (next === \'lab\') loadTwin()' in script
    assert 'evidence-details' in script and 'technical-summary' in script
