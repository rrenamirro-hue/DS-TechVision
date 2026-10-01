"""Configuracion local de DS TechVision 0.2; sin acoplamiento a PortalBrain."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUALS_DIR = ROOT / 'data' / 'manuals'
INDEX_DIR = ROOT / 'data' / 'index'
MODELS = [
    {'id': 'CANON_IR1643I', 'label': 'Canon imageRUNNER 1643i'},
]
MANUALS = {
    'SM_R6': {
        'file': 'imageRUNNER_1643iF_1643i_SM_r6_211104.pdf',
        'title': 'Service Manual · Rev. 6 (2021-11-04)',
        'kind': 'servicio',
        'models': [x['id'] for x in MODELS],
    },
    'PC_R9': {
        'file': 'imageRUNNER_1643iF_1643i_PC_r9_250929.pdf',
        'title': 'Parts Catalog · Rev. 9 (2025-09-29)',
        'kind': 'repuestos',
        'models': [x['id'] for x in MODELS],
    },
}
