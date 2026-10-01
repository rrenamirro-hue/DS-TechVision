"""Búsqueda OEM local: embeddings E5 normalizados y coincidencia exacta de códigos."""
import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import INDEX_DIR, MANUALS

SCHEMA_VERSION = 1
DEFAULT_MODEL = 'intfloat/multilingual-e5-small'
IDENTIFIER = re.compile(r'(?<![A-Za-z0-9])(?:[A-Z0-9]{2,}(?:-[A-Z0-9]{2,})+|[A-Z]{1,4}\d[A-Z0-9]{2,})(?![A-Za-z0-9])', re.I)


def model_name() -> str:
    return os.environ.get('DS_TECHVISION_EMBEDDING_MODEL', DEFAULT_MODEL).strip() or DEFAULT_MODEL


@lru_cache(maxsize=2)
def _model(name: str):
    from sentence_transformers import SentenceTransformer
    try:
        return SentenceTransformer(name, local_files_only=True)
    except Exception:
        try:
            # Aprovisionamiento inicial; una vez cacheado, el uso es completamente local.
            return SentenceTransformer(name)
        except Exception as exc:
            raise RuntimeError(f'Modelo de embeddings no disponible: {name}. Instalarlo antes de buscar.') from exc


def _chunks(index_dir: Path) -> list[dict]:
    path = index_dir / 'chunks.jsonl'
    if not path.is_file():
        raise FileNotFoundError('Índice OEM ausente. Ejecutar: python -m app.ingest')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not rows:
        raise ValueError('Índice OEM vacío')
    return rows


def build_embedding_index(index_dir: Path = INDEX_DIR) -> dict:
    """Reutiliza vectores si coinciden PDF, modelo, configuración de chunks y filas."""
    index_dir = Path(index_dir)
    corpus = json.loads((index_dir / 'manifest.json').read_text(encoding='utf-8'))
    chunks = _chunks(index_dir)
    name = model_name()
    expected = {
        'schema_version': SCHEMA_VERSION, 'embedding_model': name,
        'service_manual_sha256': corpus['documents']['SM_R6']['sha256'],
        'parts_catalog_sha256': corpus['documents']['PC_R9']['sha256'],
        'chunk_config': corpus['chunk_config'], 'chunk_count': len(chunks),
    }
    meta_path, vectors_path = index_dir / 'embedding-manifest.json', index_dir / 'embeddings.npy'
    if meta_path.is_file() and vectors_path.is_file():
        try:
            prior = json.loads(meta_path.read_text(encoding='utf-8'))
            matrix = np.load(vectors_path, mmap_mode='r', allow_pickle=False)
            if (all(prior.get(key) == value for key, value in expected.items()) and
                matrix.shape == (len(chunks), prior['embedding_dimension']) and
                matrix.dtype == np.float32 and prior.get('chunk_ids') == [c['id'] for c in chunks]):
                return {**prior, 'state': 'LOADED'}
        except (OSError, ValueError, KeyError):
            pass
    model = _model(name)
    matrix = np.asarray(model.encode([f"passage: {row['text']}" for row in chunks],
                                     batch_size=16, normalize_embeddings=True,
                                     show_progress_bar=False), dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(chunks) or not np.isfinite(matrix).all():
        raise ValueError('Embeddings inválidos')
    metadata = {**expected, 'embedding_dimension': int(matrix.shape[1]),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'chunk_ids': [c['id'] for c in chunks]}
    pending_vectors = index_dir / 'embeddings.pending.npy'
    np.save(pending_vectors, matrix, allow_pickle=False)
    pending_vectors.replace(vectors_path)
    pending_meta = index_dir / 'embedding-manifest.pending.json'
    pending_meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    pending_meta.replace(meta_path)
    return {**metadata, 'state': 'CREATED'}


class LocalRetriever:
    def __init__(self, index_dir: Path = INDEX_DIR):
        self.index_dir = Path(index_dir)
        self.metadata = build_embedding_index(self.index_dir)
        self.chunks = _chunks(self.index_dir)
        self.matrix = np.load(self.index_dir / 'embeddings.npy', allow_pickle=False)
        self.model = _model(self.metadata['embedding_model'])

    def search(self, query: str, model_id: str, doc_id: str | None = None, limit: int = 5) -> list[dict]:
        query_vector = np.asarray(self.model.encode([f'query: {query.strip()}'],
                                                     normalize_embeddings=True), dtype=np.float32)[0]
        scores = self.matrix @ query_vector
        exact_ids = {match.upper() for match in IDENTIFIER.findall(query)}
        matching = [i for i, c in enumerate(self.chunks)
                    if model_id in c['models'] and (doc_id is None or doc_id == c['doc_id'])]

        def relevance(i):
            chunk = self.chunks[i]
            text = chunk['text'].upper()
            exact = sum(1 for identifier in exact_ids if identifier in text)
            score = float(scores[i])
            if chunk['doc_id'] == 'SM_R6' and 5 <= chunk['page'] <= 11:
                score *= 0.2  # Evitar que el índice de contenidos desplace el procedimiento.
            return (exact, score)

        ranked = sorted(matching, key=relevance, reverse=True)
        output, seen_pages = [], set()
        for i in ranked:
            if len(output) >= limit:
                break
            entry = self.chunks[i]
            page_key = (entry['doc_id'], entry['page'])
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            meta = MANUALS[entry['doc_id']]
            exact = any(identifier in entry['text'].upper() for identifier in exact_ids)
            output.append({
                'id': entry['id'], 'document_id': entry['doc_id'], 'document_title': meta['title'],
                'source_kind': meta['kind'], 'pdf_page': entry['page'],
                'score': round(float(scores[i]), 4), 'exact_identifier_match': exact,
                'excerpt': entry['text'][:900],
                'source_url': f"/manual/view/{entry['doc_id']}?page={entry['page']}",
            })
        return output
