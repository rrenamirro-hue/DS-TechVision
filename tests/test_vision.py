from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.vision import catalog, ocr_frame, reference_path


def test_visual_library_and_anchor_traceability():
    references = {item['reference_id']: item for item in catalog()['references']}
    assert {'1643_front_closed', '1643_right_service_open', '1643_rear_door_installed',
            '1643_adf_state_01', '1643_rear_door_removed'} <= set(references)
    right = references['1643_right_service_open']
    assert right['model'] == 'CANON_IR1643I' and right['view'] == 'right'
    assert right['source'] == 'SM_R6' and right['source_page'] == {'printed': 121, 'pdf': 132}
    assert reference_path(right['reference_id']).read_bytes().startswith(b'\x89PNG')
    screws = [anchor for anchor in right['anchors'] if anchor['type'] == 'screw']
    assert len(screws) == 1 and '1x' in screws[0]['evidence']
    assert any(anchor['type'] == 'cover' and len(anchor['points']) >= 4 for anchor in right['anchors'])
    assert any(anchor.get('movement_status') == 'SIMULATED_MOVEMENT' for anchor in right['anchors'])
    assert all(item['source_type'] == 'OEM_PDF' for item in references.values())


def test_local_ocr_is_evidence_not_sole_model_detection():
    image = Image.new('RGB', (900, 160), 'white')
    draw = ImageDraw.Draw(image)
    font_path = Path('C:/Windows/Fonts/arial.ttf')
    font = ImageFont.truetype(str(font_path), 58) if font_path.exists() else ImageFont.load_default()
    draw.text((20, 35), 'Canon imageRUNNER 1643i', fill='black', font=font)
    output = BytesIO(); image.save(output, format='JPEG', quality=85)
    result = ocr_frame(output.getvalue())
    if result['available']:
        assert 'CANON' in result['ocr_evidence']
        assert result['model_candidate'] == 'CANON_IR1643I'
    assert result['model_candidate'] in {'CANON_IR1643I', 'UNKNOWN'}


def test_tracking_implementation_is_markerless():
    code = Path('app/static/natural-tracking.js').read_text(encoding='utf-8')
    assert 'orb.describe' in code and 'motion_estimator.ransac' in code
    assert 'matchDescriptors' in code and 'project(matrix' in code
    html = Path('app/static/index.html').read_text(encoding='utf-8')
    assert '/static/natural-tracking.js' in html
    assert 'demo-tracking.js' not in html and 'BarcodeDetector' not in code
