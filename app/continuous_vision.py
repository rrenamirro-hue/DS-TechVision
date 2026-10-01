"""Reconocimiento visual continuo local; la evidencia OEM sigue siendo autoridad técnica."""
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from .vision import VISION_ROOT, catalog, ocr_frame

VISUAL_INDEX = VISION_ROOT / 'visual_index'
DEFAULT_VISUAL_MODEL = 'openai/clip-vit-base-patch32'
MIN_VISUAL_SIMILARITY = 0.78
SCHEMA_VERSION = 1


def visual_model_name() -> str:
    return os.environ.get('DS_TECHVISION_VISUAL_MODEL', DEFAULT_VISUAL_MODEL).strip() or DEFAULT_VISUAL_MODEL


@lru_cache(maxsize=2)
def _encoder(name: str):
    from transformers import CLIPModel, CLIPProcessor
    import torch
    try:
        model = CLIPModel.from_pretrained(name, local_files_only=True).eval()
        processor = CLIPProcessor.from_pretrained(name, local_files_only=True)
    except Exception:
        try:
            model = CLIPModel.from_pretrained(name).eval()
            processor = CLIPProcessor.from_pretrained(name)
        except Exception as exc:
            raise RuntimeError(f'Modelo visual no disponible: {name}') from exc
    model.to('cpu')
    torch.set_num_threads(min(torch.get_num_threads(), 4))
    return model, processor


def _image_features(images: list[Image.Image], name: str) -> np.ndarray:
    import torch
    model, processor = _encoder(name)
    with torch.inference_mode():
        inputs = processor(images=images, return_tensors='pt')
        vectors = model.get_image_features(**inputs)
        if not isinstance(vectors, torch.Tensor):
            vectors = vectors.pooler_output
        vectors = vectors.float()
        vectors = vectors / vectors.norm(dim=-1, keepdim=True).clamp(min=1e-8)
    return vectors.cpu().numpy().astype(np.float32)


def _references() -> list[dict]:
    return catalog()['references']


def build_visual_index(index_dir: Path = VISUAL_INDEX) -> dict:
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    references = _references()
    if not references:
        raise ValueError('No hay referencias visuales OEM')
    name = visual_model_name()
    sources = {item['reference_id']: hashlib.sha256((VISION_ROOT / item['file']).read_bytes()).hexdigest()
               for item in references}
    expected = {'schema_version': SCHEMA_VERSION, 'visual_embedding_model': name,
                'references': sources, 'reference_ids': [item['reference_id'] for item in references]}
    metadata_path, matrix_path = index_dir / 'manifest.json', index_dir / 'embeddings.npy'
    if metadata_path.is_file() and matrix_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            matrix = np.load(matrix_path, mmap_mode='r', allow_pickle=False)
            if (all(metadata.get(key) == value for key, value in expected.items()) and
                matrix.shape == (len(references), metadata['embedding_dimension']) and
                matrix.dtype == np.float32):
                return {**metadata, 'state': 'LOADED'}
        except (OSError, ValueError, KeyError):
            pass
    images = []
    for item in references:
        with Image.open(VISION_ROOT / item['file']) as original:
            images.append(original.convert('RGB'))
    matrix = _image_features(images, name)
    if matrix.shape[0] != len(references) or not np.isfinite(matrix).all():
        raise ValueError('Embeddings visuales inválidos')
    metadata = {**expected, 'embedding_dimension': int(matrix.shape[1]),
                'created_at': datetime.now(timezone.utc).isoformat()}
    pending_matrix = index_dir / 'embeddings.pending.npy'
    np.save(pending_matrix, matrix, allow_pickle=False)
    pending_matrix.replace(matrix_path)
    pending_metadata = index_dir / 'manifest.pending.json'
    pending_metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    pending_metadata.replace(metadata_path)
    return {**metadata, 'state': 'CREATED'}


class VisualEmbeddingIndex:
    def __init__(self, index_dir: Path = VISUAL_INDEX):
        self.metadata = build_visual_index(index_dir)
        self.references = _references()
        self.matrix = np.load(Path(index_dir) / 'embeddings.npy', allow_pickle=False)

    def compare(self, image: Image.Image) -> dict:
        vector = _image_features([image.convert('RGB')], self.metadata['visual_embedding_model'])[0]
        similarities = self.matrix @ vector
        positive = [i for i, item in enumerate(self.references)
                    if item.get('recognition_role', 'equipment') == 'equipment']
        negative = [i for i, item in enumerate(self.references)
                    if item.get('recognition_role') == 'component_only']
        order = sorted(positive, key=lambda i: -similarities[i])
        matches = [{'reference_id': self.references[int(i)]['reference_id'],
                 'view': self.references[int(i)]['view'],
                 'state': self.references[int(i)]['state'],
                 'similarity': round(float(similarities[i]), 4)} for i in order[:3]]
        return {'top_matches': matches,
                'non_equipment_similarity': round(float(max((similarities[i] for i in negative), default=0)), 4)}


class EquipmentRecognizer:
    """Fusiona CLIP, OCR y coincidencia local ORB; no autentica número de serie."""
    def __init__(self, visual_index: VisualEmbeddingIndex):
        self.visual_index = visual_index

    def recognize(self, image_bytes: bytes, feature_match: dict | None = None) -> dict:
        if len(image_bytes) < 100 or len(image_bytes) > 300_000 or not image_bytes.startswith(b'\xff\xd8'):
            raise ValueError('JPEG de cámara inválido o demasiado grande')
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            if image.width * image.height > 2_000_000:
                raise ValueError('Resolución de cámara demasiado grande')
        except (OSError, ValueError) as exc:
            raise ValueError('Imagen de cámara inválida') from exc
        comparison = self.visual_index.compare(image)
        matches = comparison['top_matches']
        top = matches[0]
        ocr = ocr_frame(image_bytes)
        known = {item['reference_id'] for item in self.visual_index.references}
        feature = feature_match if feature_match and feature_match.get('reference_id') in known else None
        feature_confidence = min(1.0, max(0.0, float(feature.get('confidence', 0)))) if feature else 0.0
        if not np.isfinite(feature_confidence):
            feature_confidence = 0.0
        visual = top['similarity']
        margin = visual - comparison['non_equipment_similarity']
        selected = top
        if feature_confidence >= 0.55:
            corroborated = next((item for item in matches
                                 if item['reference_id'] == feature['reference_id']
                                 and top['similarity'] - item['similarity'] <= 0.05), None)
            if corroborated:
                selected = corroborated
        ocr_confirmed = ocr['model_candidate'] == 'CANON_IR1643I'
        accepted = margin >= 0.03 and (visual >= MIN_VISUAL_SIMILARITY or
                    (ocr_confirmed and visual >= 0.66) or
                    (feature_confidence >= 0.55 and visual >= 0.69))
        confidence = min(0.99, max(0.0, (visual - 0.55) / 0.45) * 0.75 +
                         (0.15 if ocr_confirmed else 0.0) + feature_confidence * 0.1) if accepted else 0.0
        return {
            'model': 'Canon imageRUNNER 1643i' if accepted else 'UNKNOWN',
            'model_id': 'CANON_IR1643I' if accepted else 'UNKNOWN',
            'confidence': round(confidence, 3),
            'evidence': {'visual_embedding': {'model': self.visual_index.metadata['visual_embedding_model'],
                                               'top_matches': matches,
                                               'non_equipment_similarity': comparison['non_equipment_similarity'],
                                               'margin': round(margin, 4)},
                         'ocr': ocr, 'feature_match': feature},
            'view': ViewRecognizer().recognize(selected, accepted),
            'state': StateRecognizer().recognize(selected, accepted),
            'reference_id': selected['reference_id'] if accepted else None,
            'notice': 'Coincidencia con biblioteca de imágenes OEM; no confirma identidad de equipo físico.',
        }


class ViewRecognizer:
    def recognize(self, top_match: dict, model_accepted: bool) -> str:
        return top_match['view'].upper() if model_accepted else 'UNKNOWN'


class StateRecognizer:
    def recognize(self, top_match: dict, model_accepted: bool) -> str:
        return top_match['state'] if model_accepted else 'UNKNOWN'


class ComponentRecognizer:
    """Devuelve solo componentes anclados al paso; no infiere part numbers por apariencia."""
    COMPONENT_TYPES = {'COVER', 'SCREW', 'CONNECTOR', 'ROLLER', 'ADF',
                       'CASSETTE', 'CARTRIDGE', 'HINGE'}
    def recognize(self, reference_id: str | None, step_id: str | None) -> list[dict]:
        if not reference_id or not step_id:
            return []
        reference = next((item for item in catalog()['references']
                          if item['reference_id'] == reference_id), None)
        if not reference or reference.get('procedure_step') != step_id:
            return []
        found = []
        for anchor in reference['anchors']:
            if anchor['type'] not in {'cover', 'screw'}:
                continue
            found.append({'component_id': anchor['id'],
                          'component_type': 'SCREW' if anchor['type'] == 'screw' else 'COVER',
                          'polygon': anchor.get('points'),
                          'bbox': None,
                          'reference_point': [anchor['x'], anchor['y']] if anchor['type'] == 'screw' else None,
                          'confidence': None, 'expected_count': anchor.get('expected_count'),
                          'part_number': None,
                          'source': {'document': reference['source'], 'page': reference['source_page']['pdf'],
                                     'evidence': anchor['evidence']},
                          'localization_status': 'REFERENCE_ANCHOR_REQUIRES_ORB_PROJECTION'})
        return found


@lru_cache(maxsize=1)
def recognizer() -> EquipmentRecognizer:
    return EquipmentRecognizer(VisualEmbeddingIndex())


def recognize_frame(image_bytes: bytes, step_id: str | None = None,
                    feature_match: dict | None = None) -> dict:
    result = recognizer().recognize(image_bytes, feature_match)
    result['components'] = ComponentRecognizer().recognize(result['reference_id'], step_id)
    result['procedure_visual_guidance'] = 'OEM_ANCHORS' if result['components'] else 'NONE'
    return result
