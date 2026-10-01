"""DS TechVision 0.4 - guía OEM con gemelo digital aproximado."""
import json
from html import escape
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .auth import (AuthenticationError, LoginThrottle, clear_session_cookie,
                   create_session, require_auth_config, set_session_cookie,
                   verify_credentials, verify_session)
from .config import INDEX_DIR, MANUALS, MANUALS_DIR, MODELS, ROOT
from .ingest import build_index
from .retriever import LocalRetriever
from .digital_twin import (dimensions as twin_dimensions, inventory_public, list_corrections,
                           model_public, save_correction, state_for_progress)
from .procedures import (create_intervention, get_calibration, get_flow_step, get_procedure, get_progress, get_step,
                         list_interventions,
                         public_catalog, render_flow_reference, render_step_reference,
                         save_calibration, update_progress)
from .vision import (components as visual_components, public_catalog as visual_catalog,
                     reference as visual_reference, reference_path, ocr_frame)
from .continuous_vision import (VISUAL_INDEX, build_visual_index, recognize_frame,
                                visual_model_name)

app = FastAPI(title='DS TechVision', version='0.6-continuous-vision', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=ROOT / 'app' / 'static'), name='static')
login_throttle = LoginThrottle()
PUBLIC_PATHS = {'/health', '/login', '/api/auth/login', '/manifest.webmanifest',
                '/service-worker.js', '/static/login.js', '/static/style.css',
                '/static/icons/icon-192.png', '/static/icons/icon-512.png'}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class SearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=400)
    model_id: Literal['CANON_IR1643I'] = 'CANON_IR1643I'
    document_id: Literal['SM_R6', 'PC_R9'] | None = None
    limit: int = Field(default=5, ge=1, le=8)


class ProgressRequest(BaseModel):
    action: Literal['start', 'confirm', 'pause', 'resume']
    confirmations: list[str] = Field(default_factory=list, max_length=20)
    note: str = Field(default='', max_length=500)
    step_id: str | None = Field(default=None, max_length=80)


class InterventionRequest(BaseModel):
    procedure_id: str = Field(min_length=1, max_length=80)
    model_id: Literal['CANON_IR1643I']


class CalibrationRequest(BaseModel):
    reference_id: str = Field(min_length=1, max_length=80)
    u: float = Field(ge=-5, le=5)
    v: float = Field(ge=-5, le=5)
    radius: float = Field(gt=0.01, le=5)


class TwinCorrectionRequest(BaseModel):
    model_id: Literal['CANON_IR1643I']
    component_id: str = Field(min_length=1, max_length=80)
    state_id: str = Field(min_length=1, max_length=80)
    scale: float = Field(default=1, ge=0.1, le=10)
    offset_mm: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    rotation_deg: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    anchor_offset: list[float] = Field(default_factory=lambda: [0, 0], min_length=2, max_length=2)


@lru_cache(maxsize=1)
def get_retriever():
    build_index()
    return LocalRetriever()


@app.middleware('http')
async def protected_local_app(request: Request, call_next):
    path = request.url.path
    if path not in PUBLIC_PATHS:
        try:
            request.state.user = verify_session(request.cookies.get('ds_session'))
        except AuthenticationError:
            if path.startswith('/api/'):
                return JSONResponse({'detail': 'Autenticacion requerida'}, status_code=401)
            return RedirectResponse('/login', status_code=303)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; "
        "script-src 'self'; style-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'self'")
    return response


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    try:
        verify_session(request.cookies.get('ds_session'))
        return RedirectResponse('/', status_code=303)
    except AuthenticationError:
        return (ROOT / 'app' / 'static' / 'login.html').read_text(encoding='utf-8')


@app.post('/api/auth/login')
def login(req: LoginRequest, request: Request, response: Response):
    client = request.client.host if request.client else 'unknown'
    if not login_throttle.allowed(client):
        raise HTTPException(429, detail='Demasiados intentos. Espera un minuto.')
    try:
        require_auth_config()
    except AuthenticationError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    if not verify_credentials(req.username, req.password):
        login_throttle.failed(client)
        raise HTTPException(401, detail='Usuario o clave incorrectos')
    login_throttle.succeeded(client)
    set_session_cookie(response, create_session(req.username), request.url.scheme == 'https')
    return {'authenticated': True, 'username': req.username}


@app.post('/api/auth/logout')
def logout(response: Response):
    clear_session_cookie(response)
    return {'authenticated': False}


@app.get('/', response_class=HTMLResponse)
def index():
    return (ROOT / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')


@app.get('/manifest.webmanifest')
def web_manifest():
    return FileResponse(ROOT / 'app' / 'static' / 'manifest.webmanifest', media_type='application/manifest+json')


@app.get('/service-worker.js')
def service_worker():
    return FileResponse(ROOT / 'app' / 'static' / 'service-worker.js', media_type='application/javascript')


@app.get('/health')
def health():
    return {'status': 'ok', 'app': 'DS TechVision', 'version': '0.6-continuous-vision', 'environment': 'LOCAL_SECURE'}


@app.get('/api/status')
def status():
    files = {key: {'present': (MANUALS_DIR / meta['file']).is_file(), 'name': meta['file']}
             for key, meta in MANUALS.items()}
    manifest = INDEX_DIR / 'manifest.json'
    data = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else None
    embedding = INDEX_DIR / 'embedding-manifest.json'
    embedding_data = json.loads(embedding.read_text(encoding='utf-8')) if embedding.exists() else None
    visual_manifest = VISUAL_INDEX / 'manifest.json'
    visual_data = json.loads(visual_manifest.read_text(encoding='utf-8')) if visual_manifest.exists() else None
    return {'indexed': embedding_data is not None and (INDEX_DIR / 'embeddings.npy').exists(),
            'chunk_count': data['chunks'] if data else 0, 'manuals': files,
            'mode': 'LOCAL_LAN_AUTHENTICATED', 'semantic_adapter': 'LOCAL_MULTILINGUAL_EMBEDDINGS',
            'embedding_model': embedding_data['embedding_model'] if embedding_data else None,
            'visual_embedding_model': visual_data['visual_embedding_model'] if visual_data else visual_model_name(),
            'visual_indexed': visual_data is not None and (VISUAL_INDEX / 'embeddings.npy').exists(),
            'visual_references': len(visual_data['reference_ids']) if visual_data else 0,
            'ar_tracking': 'NATURAL_ORB_RANSAC_REFERENCE_PROTOTYPE', 'spatial_calibration': 'REFERENCE_IMAGE_ONLY'}


@app.get('/api/equipos')
def equipos():
    return {'models': MODELS}


@app.post('/api/buscar')
def buscar(req: SearchRequest):
    try:
        retriever = get_retriever()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return {'question': req.question, 'model_id': req.model_id,
            'method': 'MULTILINGUAL_E5_COSINE_EXACT_HYBRID',
            'results': retriever.search(req.question, req.model_id, req.document_id, req.limit),
            'notice': 'Evidencia recuperada; no es un diagnostico confirmado ni un procedimiento generado.'}


@app.get('/api/procedures')
def procedures():
    return public_catalog()


@app.get('/api/digital-twin')
def digital_twin_model():
    return model_public()


@app.get('/api/digital-twin/dimensions')
def digital_twin_dimensions():
    return twin_dimensions()


@app.get('/api/digital-twin/inventory')
def digital_twin_inventory(figure: str | None = None, category: str | None = None):
    return inventory_public(figure, category)


@app.get('/api/digital-twin/state/{procedure_id}')
def digital_twin_state(procedure_id: str, request: Request, intervention_id: str | None = None):
    try:
        return state_for_progress(request.state.user, procedure_id, intervention_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Procedimiento no autorizado') from exc


@app.get('/api/digital-twin/target/{procedure_id}/{step_id}', response_class=HTMLResponse)
def digital_twin_target(procedure_id: str, step_id: str):
    try:
        step = get_flow_step(procedure_id, step_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Paso no autorizado') from exc
    if not step['ar_available']:
        raise HTTPException(409, detail='Este paso no tiene referencia AR')
    if step_id != 'right_cover_removed':
        raise HTTPException(409, detail='No existe referencia natural para este paso')
    return RedirectResponse('/api/vision/reference/1643_right_service_open/display', status_code=303)


@app.get('/api/vision/references')
def vision_references():
    return visual_catalog()


@app.get('/api/vision/components')
def vision_components():
    return visual_components()


@app.get('/api/vision/reference/{reference_id}/image')
def vision_reference_image(reference_id: str):
    try:
        path = reference_path(reference_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Referencia no autorizada') from exc
    return FileResponse(path, media_type='image/png', headers={'Cache-Control': 'no-store, private'})


@app.get('/api/vision/reference/{reference_id}/display', response_class=HTMLResponse)
def vision_reference_display(reference_id: str):
    try:
        item = visual_reference(reference_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Referencia no autorizada') from exc
    title = escape(reference_id)
    image = f'/api/vision/reference/{reference_id}/image'
    page = item['source_page']['pdf']
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>Referencia OEM · {title}</title>'
            f'<link rel="stylesheet" href="/static/vision-reference.css"></head><body><main>'
            f'<h1>Referencia OEM natural · {title}</h1>'
            f'<p>Mostrá esta fotografía en otra pantalla. El reconocimiento intenta seguir sus rasgos naturales; '
            f'no requiere marcadores. Las indicaciones solo se refieren a esta imagen.</p>'
            f'<img src="{image}" alt="Fotografía OEM de la Canon imageRUNNER 1643i">'
            f'<p>Service Manual Rev. 6 · PDF {page}. '
            f'<a href="/manual/view/SM_R6?page={page}">Ver documento original</a></p>'
            f'</main></body></html>')


@app.post('/api/vision/ocr')
async def vision_ocr(request: Request):
    payload = await request.body()
    try:
        return ocr_frame(payload)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@app.post('/api/vision/recognize')
async def vision_recognize(request: Request, procedure_id: str | None = None,
                           intervention_id: str | None = None,
                           feature_reference_id: str | None = None,
                           feature_confidence: float = 0):
    step_id = None
    if intervention_id and procedure_id:
        try:
            progress = get_progress(request.state.user, procedure_id, intervention_id)
            step_id = progress['current_step_id']
        except KeyError as exc:
            raise HTTPException(404, detail='Intervención no autorizada') from exc
    payload = await request.body()
    feature = ({'reference_id': feature_reference_id, 'confidence': feature_confidence}
               if feature_reference_id else None)
    try:
        return await run_in_threadpool(recognize_frame, payload, step_id, feature)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(503, detail=str(exc)) from exc


@app.get('/api/digital-twin/corrections')
def digital_twin_corrections(request: Request):
    return {'corrections': list_corrections(request.state.user)}


@app.put('/api/digital-twin/corrections')
def update_digital_twin_correction(payload: TwinCorrectionRequest, request: Request):
    try:
        return save_correction(request.state.user, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@app.get('/api/procedures/{procedure_id}')
def procedure(procedure_id: str):
    try:
        return get_procedure(procedure_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Procedimiento no autorizado') from exc


@app.get('/api/interventions')
def interventions(request: Request, procedure_id: str):
    try:
        return {'interventions': list_interventions(request.state.user, procedure_id)}
    except KeyError as exc:
        raise HTTPException(404, detail='Procedimiento no autorizado') from exc


@app.post('/api/interventions')
def new_intervention(payload: InterventionRequest, request: Request):
    try:
        return create_intervention(request.state.user, payload.procedure_id, payload.model_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Procedimiento no autorizado') from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@app.get('/api/interventions/{intervention_id}/progress')
def intervention_progress(intervention_id: str, procedure_id: str, request: Request):
    try:
        return get_progress(request.state.user, procedure_id, intervention_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Intervención no autorizada') from exc


@app.post('/api/interventions/{intervention_id}/progress')
def change_intervention_progress(intervention_id: str, procedure_id: str,
                                 payload: ProgressRequest, request: Request):
    try:
        if payload.action == 'start':
            raise ValueError('La intervención ya fue iniciada')
        return update_progress(request.state.user, procedure_id, payload.action, payload.confirmations,
                               payload.note, payload.step_id, intervention_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Intervención no autorizada') from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@app.get('/api/procedures/{procedure_id}/progress')
def procedure_progress(procedure_id: str, request: Request):
    try:
        return get_progress(request.state.user, procedure_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Procedimiento no autorizado') from exc


@app.post('/api/procedures/{procedure_id}/progress')
def change_procedure_progress(procedure_id: str, payload: ProgressRequest, request: Request):
    try:
        return update_progress(request.state.user, procedure_id, payload.action, payload.confirmations,
                               payload.note, payload.step_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Procedimiento no autorizado') from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@app.get('/api/procedures/{procedure_id}/steps/{step_id}/reference')
def step_reference(procedure_id: str, step_id: str):
    try:
        content = render_step_reference(procedure_id, step_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Referencia no autorizada') from exc
    return Response(content=content, media_type='image/png', headers={'Cache-Control': 'no-store, private'})


@app.get('/api/procedures/{procedure_id}/flow/{flow_step_id}/reference')
def flow_step_reference(procedure_id: str, flow_step_id: str):
    try:
        content = render_flow_reference(procedure_id, flow_step_id)
    except KeyError as exc:
        raise HTTPException(404, detail='Referencia no autorizada') from exc
    return Response(content=content, media_type='image/png', headers={'Cache-Control': 'no-store, private'})


@app.get('/api/procedures/{procedure_id}/steps/{step_id}/calibration')
def step_calibration(procedure_id: str, step_id: str, request: Request):
    try:
        return {'calibration': get_calibration(request.state.user, procedure_id, step_id)}
    except KeyError as exc:
        raise HTTPException(404, detail='Paso no autorizado') from exc


@app.put('/api/procedures/{procedure_id}/steps/{step_id}/calibration')
def calibrate_step(procedure_id: str, step_id: str, payload: CalibrationRequest, request: Request):
    try:
        return save_calibration(request.state.user, procedure_id, step_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(404, detail='Paso no autorizado') from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@app.get('/api/manual/{document_id}')
def open_manual(document_id: str):
    meta = MANUALS.get(document_id)
    if meta is None:
        raise HTTPException(404, detail='Documento no autorizado')
    path = MANUALS_DIR / meta['file']
    if not path.is_file():
        raise HTTPException(404, detail='PDF no cargado')
    return FileResponse(path, media_type='application/pdf', filename=meta['file'],
                        content_disposition_type='inline', headers={'Cache-Control': 'no-store, private'})


@app.get('/manual/view/{document_id}', response_class=HTMLResponse)
def manual_view(document_id: str, page: int = Query(default=1, ge=1)):
    import pymupdf
    meta = MANUALS.get(document_id)
    if not meta:
        raise HTTPException(404, detail='Documento no autorizado')
    path = MANUALS_DIR / meta['file']
    if not path.is_file():
        raise HTTPException(404, detail='PDF no cargado')
    with pymupdf.open(path) as pdf:
        if page > len(pdf):
            raise HTTPException(404, detail='Página no disponible')
    title = escape(meta['title'])
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title} · Página {page}</title><style>'
            'body{font:16px system-ui;background:#061935;color:white;margin:0;padding:1rem}'
            'main{max-width:900px;margin:auto}img{display:block;width:100%;height:auto;background:white}'
            'a{color:#83ddff;margin-right:1rem}nav{padding:1rem 0}</style></head><body><main>'
            f'<h1>{title}</h1><p>Página PDF {page}</p><nav><a href="/">Volver a la guía</a>'
            f'<a href="/api/manual/{document_id}#page={page}" target="_blank" rel="noopener">Abrir PDF completo</a></nav>'
            f'<img src="/api/manual/{document_id}/page/{page}" alt="Página OEM {page}">'
            '</main></body></html>')


@app.get('/api/manual/{document_id}/page/{page}')
def manual_page(document_id: str, page: int):
    import pymupdf
    meta = MANUALS.get(document_id)
    if not meta:
        raise HTTPException(404, detail='Documento no autorizado')
    path = MANUALS_DIR / meta['file']
    if not path.is_file():
        raise HTTPException(404, detail='PDF no cargado')
    with pymupdf.open(path) as pdf:
        if page < 1 or page > len(pdf):
            raise HTTPException(404, detail='Página no disponible')
        content = pdf[page - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).tobytes('png')
    return Response(content=content, media_type='image/png', headers={'Cache-Control': 'no-store, private'})
