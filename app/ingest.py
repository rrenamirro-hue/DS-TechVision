"""Ingesta local de PDFs OEM. No copia los PDF al paquete ni llama a servicios remotos."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import fitz
from .config import INDEX_DIR, MANUALS, MANUALS_DIR

CHUNK_CONFIG = {'size': 1100, 'overlap': 150, 'min_chars': 35, 'sort_text': True,
                'record_schema': 2}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _split(text: str, size: int = 1100, overlap: int = 150):
    text = re.sub(r'[ \t]+', ' ', text.replace('\x00', '')).strip()
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(' ', start + int(size * .70), end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if len(chunk) >= 35:
            yield chunk
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)


def build_index(manuals_dir: Path = MANUALS_DIR, index_dir: Path = INDEX_DIR) -> dict:
    manuals_dir, index_dir = Path(manuals_dir), Path(index_dir)
    missing = [meta['file'] for meta in MANUALS.values() if not (manuals_dir / meta['file']).is_file()]
    if missing:
        raise FileNotFoundError('Faltan los PDF en data/manuals: ' + ', '.join(missing))
    index_dir.mkdir(parents=True, exist_ok=True)
    hashes = {doc_id: _sha256(manuals_dir / meta['file']) for doc_id, meta in MANUALS.items()}
    manifest_path = index_dir / 'manifest.json'
    if manifest_path.is_file() and (index_dir / 'chunks.jsonl').is_file():
        try:
            prior = json.loads(manifest_path.read_text(encoding='utf-8'))
            if (prior.get('chunk_config') == CHUNK_CONFIG and
                all(prior['documents'][doc_id]['sha256'] == value for doc_id, value in hashes.items())):
                return prior
        except (ValueError, KeyError):
            pass
    chunks, documents = [], {}
    for doc_id, meta in MANUALS.items():
        path = manuals_dir / meta['file']
        with fitz.open(path) as pdf:
            documents[doc_id] = {
                'name': meta['file'], 'title': meta['title'], 'kind': meta['kind'],
                'pages': len(pdf), 'sha256': hashes[doc_id], 'models': meta['models'],
            }
            for page_num, page in enumerate(pdf, start=1):
                # El texto es del PDF local. No se usa OCR ni se alteran las paginas originales.
                for pos, fragment in enumerate(_split(page.get_text('text', sort=True))):
                    chunks.append({
                        'id': f'{doc_id}:p{page_num:04d}:c{pos:03d}',
                        'chunk_id': f'{doc_id}:p{page_num:04d}:c{pos:03d}',
                        'doc_id': doc_id, 'document_name': meta['title'],
                        'page': page_num, 'text': fragment,
                        'models': meta['models'],
                    })
    if not chunks:
        raise ValueError('Los PDF no contienen texto extraible. Revisar antes de utilizar OCR.')
    tmp = index_dir / 'chunks.jsonl.tmp'
    with tmp.open('w', encoding='utf-8') as stream:
        for item in chunks:
            stream.write(json.dumps(item, ensure_ascii=False) + '\n')
    tmp.replace(index_dir / 'chunks.jsonl')
    manifest = {
        'product': 'DS TechVision', 'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'chunks': len(chunks), 'documents': documents, 'chunk_config': CHUNK_CONFIG,
        'retriever': 'local multilingual embeddings + exact OEM identifier matching',
    }
    (index_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    result = build_index()
    from .retriever import build_embedding_index
    embedding = build_embedding_index()
    print(f"INDICE_CREADO: {result['chunks']} fragmentos / {len(result['documents'])} documentos")
    print(f"EMBEDDING_INDEX_{embedding['state']}: {embedding['chunk_count']} vectores / {embedding['embedding_dimension']} dimensiones")
    for key, doc in result['documents'].items():
        print(f"{key}: {doc['pages']} paginas | SHA256={doc['sha256']}")
    print('PDF_ORIGINALES_MODIFICADOS: NO')
    print('PORTALBRAIN_MODIFICADO: NO')
