'use strict';

const $ = (id) => document.getElementById(id);
const el = (tag, className = '', value) => { const node = document.createElement(tag); node.className = className; if (value !== undefined) node.textContent = value; return node; };
let catalog = [], selectedProcedure = null, progress = null, currentStep = null;
let interventions = [];
let view = 'guide', consultationMode = false, consultationIndex = 0;
let stream = null, facing = 'environment', installPrompt = null;
let trackingActive = false, trackingTimer = null, visionTracker = null, visionReady = null;
let currentMatch = null, globalRecognition = null, lastVisualAt = 0, visualInFlight = false;
let visionEpoch = 0;
let twinModel = null, twinViewer = null, twinLoaded = false;
const trackingCanvas = document.createElement('canvas');
trackingCanvas.width = 480; trackingCanvas.height = 360;

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 401) { location.assign('/login'); throw new Error('Sesión vencida'); }
  return response;
}
function sourceLink(doc, page, label) {
  const link = el('a', 'source-link', label);
  link.href = `/manual/view/${doc}?page=${page}`; return link;
}
function setView(next) {
  if (view === 'camera' && next !== 'camera') stopCamera({quiet: true});
  view = next;
  for (const name of ['guide', 'camera', 'manual', 'lab']) $(`${name}View`).hidden = name !== next;
  document.querySelectorAll('.bottom-nav button').forEach((button) => button.classList.toggle('active', button.dataset.view === next));
  if (next === 'lab') loadTwin();
  if (next === 'camera') syncCamera();
  scrollTo({top: 0, behavior: 'instant'});
}

async function loadStatus() {
  try {
    const response = await apiFetch('/api/status'); const data = await response.json();
    $('indexBadge').textContent = data.indexed ? 'EMBEDDINGS DISPONIBLES' : 'FALTA INDEXAR';
    $('indexBadge').className = `pill ${data.indexed ? 'ok' : 'bad'}`;
    $('manualStatus').replaceChildren();
    for (const [key, item] of Object.entries(data.manuals)) {
      const row = el('div', 'manual-line'); row.append(el('span', '', key === 'SM_R6' ? 'Service Manual · Rev. 6' : 'Parts Catalog · Rev. 9'), el('span', item.present ? 'state-ok' : 'state-bad', item.present ? '● CARGADO' : '○ AUSENTE')); $('manualStatus').append(row);
    }
    $('manualStatus').append(el('p', 'microcopy', data.indexed ? `Recuperación semántica local mediante embeddings · ${data.embedding_model} · ${data.chunk_count} fragmentos.` : 'Índice de embeddings no disponible.'));
  } catch (error) { $('indexBadge').textContent = 'SIN CONEXIÓN'; }
}
async function loadProcedures() {
  try {
    const response = await apiFetch('/api/procedures');
    if (!response.ok) throw new Error('No se pudieron cargar las intervenciones');
    catalog = (await response.json()).procedures;
    $('procedureSelect').replaceChildren();
    for (const procedure of catalog) { const option = el('option', '', procedure.title); option.value = procedure.procedure_id; $('procedureSelect').append(option); }
    await selectProcedure(catalog[0].procedure_id);
  } catch (error) { $('procedureContent').textContent = error.message; }
}
async function selectProcedure(id) {
  stopCamera({quiet: true}); selectedProcedure = catalog.find((item) => item.procedure_id === id);
  consultationMode = false; consultationIndex = 0; currentStep = null;
  progress = null; interventions = [];
  if (selectedProcedure?.status !== 'reference_only_not_enabled_for_ar') {
    const response = await apiFetch(`/api/interventions?procedure_id=${encodeURIComponent(id)}`);
    if (response.ok) interventions = (await response.json()).interventions;
  }
  renderProcedure();
}
async function newIntervention() {
  const response = await apiFetch('/api/interventions', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({procedure_id: selectedProcedure.procedure_id, model_id: $('model').value})});
  const data = await response.json(); if (!response.ok) { alert(data.detail || 'No se pudo crear la intervenciÃ³n'); return; }
  progress = data; currentStep = null; renderProcedure(); refreshTwinState();
}
async function continueIntervention(id) {
  const response = await apiFetch(`/api/interventions/${encodeURIComponent(id)}/progress?procedure_id=${encodeURIComponent(selectedProcedure.procedure_id)}`);
  if (!response.ok) { alert('No se pudo reanudar la intervenciÃ³n'); return; }
  progress = await response.json(); renderProcedure(); refreshTwinState();
}
function renderPhases() {
  const root = $('flowPhases'); root.replaceChildren();
  const flow = progress?.flow_steps || selectedProcedure?.flow_steps || [];
  for (const [phase, label] of [['A', 'Seguridad'], ['B', 'Preparación'], ['C', 'OEM'], ['D', 'Cierre']]) {
    const steps = flow.filter((step) => step.phase === phase), complete = steps.filter((step) => step.state === 'completado').length;
    if (!steps.length) continue;
    const chip = el('div', 'phase-chip');
    if (complete === steps.length) chip.classList.add('complete');
    if (steps.some((step) => step.state === 'en_curso')) chip.classList.add('current');
    chip.append(el('strong', '', phase), el('span', '', label), el('small', '', `${complete}/${steps.length}`)); root.append(chip);
  }
}
function renderProcedure() {
  const root = $('procedureContent'); root.replaceChildren(); renderPhases();
  if (!selectedProcedure) return;
  const referenceOnly = selectedProcedure.status === 'reference_only_not_enabled_for_ar';
  const statusLabels = {not_started: 'SIN INICIAR', in_progress: 'EN CURSO', paused: 'PAUSADO', completed: 'COMPLETADO'};
  $('procedureBadge').textContent = referenceOnly ? 'SOLO REFERENCIA' : (statusLabels[progress?.status] || 'SIN INICIAR');
  $('procedureBadge').className = `pill ${referenceOnly ? 'wait' : 'cyan'}`;
  if (referenceOnly) {
    root.append(el('p', 'warning-box', 'Esta intervención está disponible únicamente como referencia OEM.'));
    selectedProcedure.source_pages.forEach((page) => root.append(sourceLink('SM_R6', page.pdf, `Abrir manual · PDF ${page.pdf}`)));
    currentStep = null; syncCamera(); return;
  }
  const flow = progress?.flow_steps || selectedProcedure.flow_steps || [];
  if (!progress) {
    root.append(el('h2', '', 'Retirar el conjunto ADF + Reader'));
    root.append(el('p', 'step-instruction', `15 pasos en secuencia: seguridad, preparaciones, procedimiento OEM y cierre. El siguiente paso se desbloquea al confirmar el actual.`));
    const active = interventions.filter((item) => item.status === 'in_progress' || item.status === 'paused');
    if (active.length) root.append(el('p', 'step-instruction', 'Existe una intervención en curso. Elegí si querés continuarla o iniciar una nueva.'));
    active.forEach((item) => { const button = el('button', 'secondary full-button', `CONTINUAR ${item.intervention_id}`); button.type = 'button'; button.addEventListener('click', () => continueIntervention(item.intervention_id)); root.append(button); });
    const start = el('button', 'primary full-button', 'NUEVA INTERVENCIÓN'); start.type = 'button'; start.addEventListener('click', newIntervention); root.append(start);
    appendAllSteps(root, flow); currentStep = null; syncCamera(); return;
  }
  root.append(el('p', 'microcopy', `Intervención ${progress.intervention_id}`));
  if (progress.status === 'completed') {
    const start = el('button', 'primary full-button', 'NUEVA INTERVENCIÓN'); start.type = 'button'; start.addEventListener('click', newIntervention); root.append(start);
    root.append(el('div', 'success-box', 'Intervención completada. Revisá el procedimiento OEM antes del montaje.'));
    appendAllSteps(root, flow); currentStep = null; syncCamera(); return;
  }
  const active = flow[progress.current_step];
  currentStep = active;
  if (!consultationMode) consultationIndex = progress.current_step;
  const index = consultationMode ? consultationIndex : progress.current_step;
  renderStep(root, flow[index], index);
  syncCamera();
}
function appendAllSteps(root, flow) {
  const details = el('details', 'all-steps'), summary = el('summary', '', 'Ver todos los pasos');
  details.append(summary); const list = el('ol', 'flow-summary');
  flow.forEach((step, index) => list.append(el('li', step.state, `${index + 1}. ${step.title} · ${step.state.replace('_', ' ')}`)));
  details.append(list); root.append(details);
}
function renderStep(root, step, index) {
  const flow = progress.flow_steps;
  const heading = el('div', 'step-heading');
  heading.append(el('span', 'step-counter', `PASO ${index + 1} / ${flow.length} · ${step.phase_label}`), el('h2', '', step.title)); root.append(heading);
  if (consultationMode) root.append(el('p', 'consultation-notice', 'Consulta libre: este paso no es el operativo y no puede confirmarse.'));
  const image = document.createElement('img'); image.className = 'oem-reference'; image.src = step.image_oem; image.alt = `Imagen OEM de ${step.title}`; root.append(image);
  root.append(el('span', 'section-label', 'ACCIÓN'), el('p', 'step-instruction', step.actions[0] || step.description));
  if (step.actions.length > 1) { const details = el('details', 'step-detail'); details.append(el('summary', '', 'Más instrucciones')); const list = el('ol', 'action-list'); step.actions.slice(1).forEach((action) => list.append(el('li', '', action))); details.append(list); root.append(details); }
  if (step.warnings.length) { const warnings = el('div', 'warning-box'); warnings.append(el('strong', '', 'Precaución')); step.warnings.forEach((item) => warnings.append(el('p', '', item))); root.append(warnings); }
  const actions = el('div', 'step-actions');
  const camera = el('button', 'secondary', 'Abrir cámara'); camera.type = 'button'; camera.disabled = consultationMode; camera.addEventListener('click', () => { setView('camera'); startCamera(); });
  actions.append(camera, sourceLink(step.source_document, step.source_page.pdf, 'Ver manual'), el('button', 'primary', 'Completar paso'));
  actions.lastChild.type = 'button'; actions.lastChild.disabled = consultationMode || progress.status !== 'in_progress';
  actions.lastChild.addEventListener('click', () => changeProgress('confirm', step.id)); root.append(actions);
  const adjacent = el('div', 'adjacent-steps');
  if (index > 0) adjacent.append(el('span', '', `← ${flow[index - 1].title}`));
  if (index + 1 < flow.length) adjacent.append(el('span', '', `${flow[index + 1].title} → ${flow[index + 1].state.replace('_', ' ')}`));
  root.append(adjacent);
  const navigation = el('div', 'flow-navigation'), consult = el('button', 'secondary', consultationMode ? 'Volver al paso actual' : 'Consulta libre');
  consult.type = 'button'; consult.addEventListener('click', () => { consultationMode = !consultationMode; consultationIndex = progress.current_step; renderProcedure(); }); navigation.append(consult);
  const pause = el('button', 'secondary', progress.status === 'paused' ? 'Reanudar' : 'Pausar'); pause.type = 'button'; pause.disabled = consultationMode; pause.addEventListener('click', () => changeProgress(progress.status === 'paused' ? 'resume' : 'pause')); navigation.append(pause);
  if (consultationMode) {
    for (const [label, delta] of [['Anterior', -1], ['Siguiente', 1]]) {
      const button = el('button', 'secondary', label); button.type = 'button'; button.disabled = index + delta < 0 || index + delta >= flow.length;
      button.addEventListener('click', () => { consultationIndex += delta; renderProcedure(); }); navigation.append(button);
    }
  }
  root.append(navigation); appendAllSteps(root, flow);
}
async function changeProgress(action, stepId = null) {
  const response = await apiFetch(`/api/interventions/${encodeURIComponent(progress.intervention_id)}/progress?procedure_id=${encodeURIComponent(selectedProcedure.procedure_id)}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action, step_id: stepId})});
  const data = await response.json(); if (!response.ok) { alert(data.detail || 'No se pudo registrar el avance'); return; }
  const wasCamera = view === 'camera'; progress = data; consultationMode = false;
  if (progress.status === 'completed') stopCamera({quiet: true});
  renderProcedure(); refreshTwinState();
  if (!wasCamera || progress.status === 'completed') setView('guide');
}

function renderVisionIdentity() {
  const result = globalRecognition, labels = {
    FRONT: 'Frontal', REAR: 'Posterior', LEFT: 'Lateral izquierda', RIGHT: 'Lateral derecha',
    ADF: 'ADF', INTERNAL: 'Interior', UNKNOWN: 'UNKNOWN',
    MACHINE_CLOSED: 'Equipo cerrado', REAR_COVER_REMOVED: 'Cubierta posterior retirada',
    RIGHT_COVER_RELEASING: 'Cubierta derecha en liberación',
    LEFT_COVER_INSTALLED: 'Cubierta izquierda instalada', ADF_READER_READY: 'Acceso ADF/Reader preparado',
    right_cover_installed_front_access_open: 'Cubierta derecha instalada',
    rear_door_installed: 'Puerta posterior instalada',
    covers_removed_before_adf_release: 'Acceso ADF preparado'
  };
  const model = result?.model || 'UNKNOWN', recognizedView = labels[result?.view] || 'UNKNOWN';
  const state = labels[result?.state] || 'UNKNOWN';
  $('visionIdentity').textContent = `EQUIPO  ${model}\nVISTA  ${recognizedView}\nESTADO  ${state}`;
  const visual = result?.evidence?.visual_embedding?.top_matches?.[0]?.similarity;
  const ocr = result?.evidence?.ocr?.ocr_evidence || [];
  $('visionEvidence').textContent = result ?
    `CLIP ${visual === undefined ? '—' : Math.round(visual * 100) + '%'} · OCR ${ocr.join('/') || 'sin lectura'} · ORB ${currentMatch ? Math.round(currentMatch.confidence * 100) + '%' : 'sin localización'} · ${result.procedure_visual_guidance === 'NONE' ? 'Sin overlay para este paso' : 'Referencia OEM del paso'}` :
    'Embeddings visuales, OCR y localización fina pendientes.';
  window.DSVisionResult = {model_candidate: result?.model_id || 'UNKNOWN',
    visual_confidence: result?.confidence || 0, ocr_evidence: ocr,
    reference_candidate: result?.reference_id || 'UNKNOWN',
    state_candidate: result?.state || 'UNKNOWN'};
}

function syncCamera() {
  const step = currentStep, demo = step?.id === 'right_cover_removed';
  $('activeStepLabel').textContent = step ? `PASO ${progress.current_step + 1} / ${progress.total_steps}` : 'SIN PASO ACTIVO';
  $('workspaceTitle').textContent = step?.title || 'Canon imageRUNNER 1643i';
  $('activeAction').textContent = step?.actions?.[0] || 'Iniciá la guía para activar la cámara.';
  $('manualCurrent').href = step ? `/manual/view/${step.source_document}?page=${step.source_page.pdf}` : '#';
  $('completeCurrent').disabled = !step || progress.status !== 'in_progress';
  $('cameraOemImage').src = step?.image_oem || '';
  $('cameraFallback').hidden = !step || (demo && currentMatch?.reference.reference_id === '1643_right_service_open');
  $('demoControls').hidden = !demo;
  $('referenceLink').href = demo ? '/api/vision/reference/1643_right_service_open/display' : '#';
  $('calibrateAnchor').disabled = !demo || !stream;
  $('manualStepContext').replaceChildren();
  if (step) $('manualStepContext').append(el('strong', '', `${step.title} · `), sourceLink(step.source_document, step.source_page.pdf, `Service Manual Rev. 6 · PDF ${step.source_page.pdf}`));
  if (!trackingActive) { $('trackingStatus').textContent = 'NO DISPONIBLE'; $('calibrationStatus').textContent = 'PENDIENTE'; }
  renderVisionIdentity();
  $('cameraNotice').textContent = demo ? 'Apuntá a la fotografía OEM de la cubierta derecha en otra pantalla. Se buscan rasgos naturales, sin marcadores.' : 'La cámara intentará reconocer referencias OEM. Si el estado no coincide con el paso, usá la imagen y el manual.';
}
function stopTracking() {
  trackingActive = false; currentMatch = null; globalRecognition = null; lastVisualAt = 0; visualInFlight = false; visionEpoch += 1;
  if (trackingTimer) clearTimeout(trackingTimer); trackingTimer = null;
  const canvas = $('arOverlay'); canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  $('trackingStatus').textContent = 'NO DISPONIBLE'; $('calibrationStatus').textContent = 'PENDIENTE'; $('cameraFallback').hidden = !currentStep;
  window.DSVisionComponents = [];
  renderVisionIdentity();
}
function stopCamera(options = {}) {
  stopTracking(); if (stream) stream.getTracks().forEach((track) => track.stop()); stream = null;
  $('camera').srcObject = null; $('cameraPlaceholder').hidden = false; $('cameraStatus').textContent = 'CÁMARA DETENIDA';
  $('openCamera').textContent = 'Iniciar cámara';
  document.querySelector('.live-dot').classList.remove('active'); $('calibrateAnchor').disabled = true;
  if (!options.quiet) $('cameraNotice').textContent = 'Cámara detenida. La referencia OEM sigue disponible.';
}
function videoToStage(point) {
  const rect = $('cameraStage').getBoundingClientRect(), video = $('camera');
  const scale = Math.max(rect.width / video.videoWidth, rect.height / video.videoHeight);
  return {x: point.x * scale + (rect.width - video.videoWidth * scale) / 2, y: point.y * scale + (rect.height - video.videoHeight * scale) / 2};
}
function frameToStage(point) {
  const video = $('camera');
  return videoToStage({x: point.x * video.videoWidth / trackingCanvas.width,
    y: point.y * video.videoHeight / trackingCanvas.height});
}
function imageAnchor(match, u, v) {
  const point = window.DSNaturalTracking.project(match.matrix, u * match.reference.width, v * match.reference.height);
  return point ? frameToStage(point) : null;
}
function locateScrewCandidate(match, anchor) {
  const expected = window.DSNaturalTracking.project(match.matrix,
    anchor.x * match.reference.width, anchor.y * match.reference.height);
  if (!expected || match.confidence < .5) return null;
  const frame = trackingCanvas.getContext('2d', {willReadFrequently: true})
    .getImageData(0, 0, trackingCanvas.width, trackingCanvas.height);
  const gray = (x, y) => {
    const px = Math.round(x), py = Math.round(y);
    if (px < 0 || py < 0 || px >= frame.width || py >= frame.height) return 0;
    const k = (py * frame.width + px) * 4;
    return .299 * frame.data[k] + .587 * frame.data[k + 1] + .114 * frame.data[k + 2];
  };
  let best = {score: 0, point: null};
  for (let dy = -9; dy <= 9; dy += 3) for (let dx = -9; dx <= 9; dx += 3) {
    const x = expected.x + dx, y = expected.y + dy;
    for (const radius of [4, 6, 8]) {
      let contrast = 0;
      for (let n = 0; n < 16; n++) {
        const angle = n * Math.PI / 8, co = Math.cos(angle), si = Math.sin(angle);
        contrast += Math.abs(gray(x + (radius - 2) * co, y + (radius - 2) * si) -
          gray(x + (radius + 2) * co, y + (radius + 2) * si));
      }
      const score = contrast / 16;
      if (score > best.score) best = {score, point: {x, y}};
    }
  }
  return best.score >= 36 ? {point: frameToStage(best.point), confidence: Math.min(1, best.score / 80)} : null;
}
function drawOverlay() {
  const canvas = $('arOverlay'), rect = $('cameraStage').getBoundingClientRect(), ratio = devicePixelRatio || 1;
  if (canvas.width !== Math.round(rect.width * ratio) || canvas.height !== Math.round(rect.height * ratio)) { canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio); }
  const context = canvas.getContext('2d'); context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, rect.width, rect.height);
  window.DSVisionComponents = [];
  const match = currentMatch;
  if (!match) {
    $('trackingStatus').textContent = 'NO DISPONIBLE'; $('calibrationStatus').textContent = 'PENDIENTE';
    $('cameraFallback').hidden = !currentStep;
    if (trackingActive) $('cameraNotice').textContent = globalRecognition?.model_id === 'CANON_IR1643I' ?
      'Equipo/vista reconocidos; localización fina no disponible. Seguimos con evidencia OEM.' :
      'Equipo no identificado con confianza. Seguimos con imagen e instrucción OEM.';
    renderVisionIdentity();
    return;
  }
  renderVisionIdentity();
  $('trackingStatus').textContent = `ESTABLE · ${Math.round(match.confidence * 100)}%`;
  $('calibrationStatus').textContent = 'HOMOGRAFÍA';
  if (globalRecognition?.model_id !== 'CANON_IR1643I' ||
      globalRecognition.reference_id !== match.reference.reference_id ||
      currentStep?.id !== match.reference.procedure_step || !match.reference.anchors.length) {
    $('cameraFallback').hidden = !currentStep; return;
  }
  $('cameraFallback').hidden = true;
  $('cameraNotice').textContent = 'Referencia OEM localizada. Contorno aproximado; movimiento ilustrativo.';
  for (const anchor of match.reference.anchors) {
    context.lineWidth = 3; context.strokeStyle = '#E73F1D'; context.fillStyle = 'rgba(231,63,29,.18)';
    context.shadowColor = '#041836'; context.shadowBlur = 6;
    if (anchor.type === 'cover') {
      const points = anchor.points.map(([u,v]) => imageAnchor(match,u,v)); if (points.some((point) => !point)) continue;
      context.beginPath(); points.forEach((point,index) => index ? context.lineTo(point.x,point.y) : context.moveTo(point.x,point.y));
      context.closePath(); context.fill(); context.stroke();
      window.DSVisionComponents.push({component_id: anchor.id, component_type: 'COVER',
        polygon: points, bbox: null, confidence: match.confidence,
        part_number: null, source: anchor.evidence, localization_status: 'ORB_PROJECTED_OEM_ANCHOR'});
    } else if (anchor.type === 'screw') {
      const point = imageAnchor(match,anchor.x,anchor.y); if (!point) continue;
      const candidate = locateScrewCandidate(match, anchor);
      if (candidate) {
        context.fillStyle = '#E73F1D'; context.beginPath(); context.arc(candidate.point.x,candidate.point.y,13,0,Math.PI*2); context.fill();
        context.fillStyle = '#FFFFFF'; context.font = '800 13px system-ui'; context.textAlign = 'center'; context.fillText(anchor.label,candidate.point.x,candidate.point.y+5);
        window.DSVisionComponents.push({component_id: anchor.id, component_type: 'SCREW',
          polygon: null, bbox: {x: candidate.point.x - 13, y: candidate.point.y - 13, width: 26, height: 26},
          confidence: candidate.confidence, expected_count: anchor.expected_count || 1,
          part_number: null, source: anchor.evidence, localization_status: 'VISUAL_CANDIDATE_NEAR_OEM_ANCHOR'});
        $('cameraNotice').textContent = `Candidato visual de tornillo en la zona OEM (${anchor.expected_count || 1}x). Confirmá en la foto y el manual.`;
      } else {
        context.setLineDash([6, 4]); context.beginPath(); context.arc(point.x,point.y,25,0,Math.PI*2); context.stroke(); context.setLineDash([]);
        window.DSVisionComponents.push({component_id: anchor.id, component_type: 'SCREW',
          polygon: null, bbox: {x: point.x - 25, y: point.y - 25, width: 50, height: 50},
          confidence: null, expected_count: anchor.expected_count || 1,
          part_number: null, source: anchor.evidence, localization_status: 'APPROXIMATE_OEM_ZONE'});
        $('cameraNotice').textContent = `Se espera ${anchor.expected_count || 1} tornillo en esta zona aproximada. No se localizó un punto exacto con confianza.`;
      }
    } else if (anchor.type === 'remove') {
      const from = imageAnchor(match,...anchor.from), to = imageAnchor(match,...anchor.to); if (!from || !to) continue;
      const phase = (Date.now() % 900) / 900, x = from.x + (to.x-from.x)*phase, y = from.y + (to.y-from.y)*phase;
      context.strokeStyle = '#E73F1D'; context.lineWidth = 4; context.beginPath(); context.moveTo(from.x,from.y); context.lineTo(to.x,to.y); context.stroke();
      context.fillStyle = '#FFFFFF'; context.beginPath(); context.arc(x,y,5,0,Math.PI*2); context.fill();
    }
  }
}
async function loadVision() {
  if (visionTracker) return visionTracker;
  if (!visionReady) visionReady = (async () => {
    const response = await apiFetch('/api/vision/references'); if (!response.ok) throw new Error('Biblioteca visual no disponible');
    const data = await response.json(), tracker = new window.DSNaturalTracking.Tracker(
      data.references.filter((item) => item.recognition_role !== 'component_only'));
    await tracker.initialize(); visionTracker = tracker; return tracker;
  })();
  try { return await visionReady; } catch (error) { visionReady = null; throw error; }
}
async function recognizeSnapshot() {
  if (!stream || visualInFlight || Date.now() - lastVisualAt < 2500) return;
  lastVisualAt = Date.now(); visualInFlight = true; const epoch = visionEpoch;
  const blob = await new Promise((resolve) => trackingCanvas.toBlob(resolve, 'image/jpeg', .55));
  if (!blob || blob.size > 300000) { if (epoch === visionEpoch) visualInFlight = false; return; }
  try {
    const params = new URLSearchParams();
    if (selectedProcedure && progress?.intervention_id) {
      params.set('procedure_id', selectedProcedure.procedure_id);
      params.set('intervention_id', progress.intervention_id);
    }
    if (currentMatch) { params.set('feature_reference_id', currentMatch.reference.reference_id); params.set('feature_confidence', String(currentMatch.confidence)); }
    const response = await apiFetch(`/api/vision/recognize?${params}`, {method: 'POST', headers: {'Content-Type': 'image/jpeg'}, body: blob});
    if (!response.ok) throw new Error(`Reconocimiento visual HTTP ${response.status}`);
    const data = await response.json();
    if (stream && epoch === visionEpoch) { globalRecognition = data; renderVisionIdentity(); }
  } catch (error) { if (stream && epoch === visionEpoch) { globalRecognition = null; $('cameraNotice').textContent = `Reconocimiento global no disponible: ${error.message}`; renderVisionIdentity(); } }
  finally { if (epoch === visionEpoch) visualInFlight = false; }
}
function trackingLoop() {
  if (!trackingActive || !stream) return;
  const video = $('camera');
  if (video.readyState >= 2 && video.videoWidth) {
    try {
      const context = trackingCanvas.getContext('2d', {willReadFrequently: true});
      context.drawImage(video, 0, 0, trackingCanvas.width, trackingCanvas.height);
      recognizeSnapshot();
      const candidates = globalRecognition?.model_id === 'CANON_IR1643I' ?
        globalRecognition.evidence.visual_embedding.top_matches.map((item) => item.reference_id) : null;
      currentMatch = candidates ? visionTracker?.match(context.getImageData(0, 0, trackingCanvas.width, trackingCanvas.height), candidates) || null : null;
    } catch (error) { currentMatch = null; $('cameraNotice').textContent = 'No se pudo procesar la imagen. Se mantiene la referencia OEM.'; }
  } else currentMatch = null;
  drawOverlay(); trackingTimer = setTimeout(trackingLoop, 300);
}
function cameraError(error) {
  const messages = {NotAllowedError: 'Permiso de cámara denegado.', NotFoundError: 'No se encontró una cámara.', NotReadableError: 'La cámara está ocupada.', SecurityError: 'La cámara requiere HTTPS confiable.'};
  return messages[error.name] || `No se pudo abrir la cámara (${error.name || 'error'}).`;
}
async function startCamera() {
  if (!currentStep) { $('cameraNotice').textContent = 'Iniciá el flujo guiado antes de abrir la cámara.'; return; }
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) { $('cameraNotice').textContent = 'Cámara no disponible: verificá HTTPS y confianza del certificado.'; return; }
  stopCamera({quiet: true}); $('openCamera').disabled = true;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: false, video: {facingMode: {ideal: facing}, width: {ideal: 1280}, height: {ideal: 720}}});
    stream.getVideoTracks()[0].addEventListener('ended', () => stopCamera({quiet: true}), {once: true});
    $('camera').srcObject = stream; await $('camera').play(); $('cameraPlaceholder').hidden = true;
    $('cameraStatus').textContent = 'CÁMARA ACTIVA'; document.querySelector('.live-dot').classList.add('active');
    $('openCamera').textContent = 'Reiniciar cámara';
    $('calibrateAnchor').disabled = currentStep.id !== 'right_cover_removed';
    trackingCanvas.width = Math.min(480, $('camera').videoWidth || 480);
    trackingCanvas.height = Math.min(360, Math.round(($('camera').videoHeight || 360) * trackingCanvas.width / ($('camera').videoWidth || 480)));
    trackingActive = true; trackingLoop();
    loadVision().catch(() => { $('calibrationStatus').textContent = 'ORB NO DISPONIBLE'; });
  } catch (error) { stopCamera({quiet: true}); $('cameraNotice').textContent = `${cameraError(error)} Imagen OEM disponible.`; }
  finally { $('openCamera').disabled = false; }
}

function technicalSummary(query, result) {
  const topic = query.trim().replace(/[.!?]+$/, '');
  const document = result.document_id === 'PC_R9' ? 'catálogo de piezas' : 'manual de servicio';
  if (/rodillo.*recogida|recogida.*rodillo/i.test(topic) && /pick[ -]?up.{0,20}roller|roller.{0,20}pick[ -]?up/i.test(result.excerpt)) {
    return `El ${document} identifica el rodillo de recogida en la alimentación de papel (PDF ${result.pdf_page}). Esta referencia ayuda a ubicarlo; verificá el procedimiento OEM específico antes de retirarlo.`;
  }
  return `Encontré una referencia sobre “${topic}” en el ${document}, página PDF ${result.pdf_page}. Revisá la evidencia original antes de identificar la pieza o iniciar una intervención; esta búsqueda no confirma un diagnóstico.`;
}
function partMetadata(result, query) {
  if (result.document_id !== 'PC_R9') return null;
  const terms = query.toLowerCase().includes('recogida') ? ['pickup', 'pick-up', 'pick up']
    : query.toLowerCase().includes('transferencia') ? ['transfer'] : [];
  if (!terms.length) return null;
  const line = result.excerpt.split(/\r?\n/).find((value) => terms.some((term) => value.toLowerCase().includes(term)) && /^\s*\d+\s+[A-Z0-9]+-[A-Z0-9-]+\s+\d+\s+/i.test(value));
  if (!line) return null;
  const match = line.match(/^\s*\d+\s+([A-Z0-9-]+)\s+(\d+)\s+(.+)$/i);
  if (!match) return null;
  const figure = result.excerpt.match(/^\s*(\d+[A-Z]?)\s+NPN\b/m);
  return `${match[3].trim()} · Part Number: ${match[1]} · Cantidad: ${match[2]}${figure ? ` · Figura: ${figure[1]}` : ''}`;
}
async function search(event) {
  event.preventDefault(); const query = $('question').value.trim(); if (query.length < 3) return;
  $('searchButton').disabled = true; $('resultCount').textContent = 'Buscando…'; $('results').replaceChildren();
  try {
    const response = await apiFetch('/api/buscar', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question: query, model_id: $('model').value, document_id: $('document').value || null, limit: 3})});
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    $('resultCount').textContent = `${data.results.length} referencias`;
    if (!data.results.length) { $('results').append(el('p', 'empty-state', 'No se recuperó evidencia. Reformulá la consulta; no infieras un procedimiento.')); return; }
    data.results.forEach((item, index) => {
      const article = el('article', 'result');
      article.append(el('p', 'technical-summary', technicalSummary(query, item)));
      article.append(el('div', 'result-meta', `FUENTE OEM · ${item.document_title} · PDF ${item.pdf_page}`));
      const parts = partMetadata(item, query); if (parts) article.append(el('p', 'part-metadata', parts));
      article.append(sourceLink(item.document_id, item.pdf_page, 'Ver evidencia original ↗'));
      const details = el('details', 'evidence-details'); details.append(el('summary', '', 'Texto OEM recuperado'), el('pre', '', item.excerpt)); article.append(details); $('results').append(article);
    });
  } catch (error) { $('resultCount').textContent = 'Error'; $('results').append(el('p', 'empty-state', error.message)); }
  finally { $('searchButton').disabled = false; }
}

function showTwinComponent(component) {
  $('twinComponentName').textContent = component.label;
  $('twinComponentData').textContent = `Part Number: ${component.part_number || 'No especificado'} · Figura: ${component.source_figure} · Cantidad: ${component.quantity ?? 'No especificada'} · PDF ${component.source_page}`;
  $('twinOemLink').href = `/manual/view/${component.source_document}?page=${component.source_page}`; $('twinOemLink').hidden = false;
  $('twinProcedureAction').disabled = !twinModel.step_map.some((item) => item.component_id === component.id);
}
async function loadTwin() {
  if (twinLoaded) return; twinLoaded = true;
  try {
    const response = await apiFetch('/api/digital-twin'); if (!response.ok) throw new Error('Modelo no disponible');
    twinModel = await response.json(); twinViewer = new window.DSTwin.Viewer($('twinCanvas'), twinModel, {onSelect: showTwinComponent});
    $('twinStateBadge').textContent = 'APROXIMADO';
    await refreshTwinState();
  } catch (error) { $('twinStateBadge').textContent = 'NO DISPONIBLE'; $('twinComponentData').textContent = error.message; }
}
async function refreshTwinState() {
  if (!twinViewer || selectedProcedure?.procedure_id !== 'ADF_READER_REMOVE' || !progress?.intervention_id) return;
  const response = await apiFetch(`/api/digital-twin/state/${selectedProcedure.procedure_id}?intervention_id=${encodeURIComponent(progress.intervention_id)}`);
  if (response.ok) twinViewer.setState((await response.json()).state);
}

$('procedureSelect').addEventListener('change', (event) => selectProcedure(event.target.value));
$('searchForm').addEventListener('submit', search);
document.querySelectorAll('.bottom-nav button').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
$('openLab').addEventListener('click', () => setView(view === 'lab' ? 'guide' : 'lab'));
$('cameraGuide').addEventListener('click', () => setView('guide'));
$('completeCurrent').addEventListener('click', () => { if (currentStep) changeProgress('confirm', currentStep.id); });
$('openCamera').addEventListener('click', startCamera); $('closeCamera').addEventListener('click', () => stopCamera());
$('startCameraInStage').addEventListener('click', startCamera);
$('flipCamera').addEventListener('click', async () => { facing = facing === 'environment' ? 'user' : 'environment'; if (stream) await startCamera(); });
$('calibrateAnchor').addEventListener('click', () => { currentMatch = null; drawOverlay(); $('cameraNotice').textContent = 'Seguimiento reiniciado. Enfocá la fotografía OEM completa.'; });
$('assembledView').addEventListener('click', () => { if (!twinViewer) return; twinViewer.setExploded(false); $('assembledView').classList.add('active'); $('explodedView').classList.remove('active'); });
$('explodedView').addEventListener('click', () => { if (!twinViewer) return; twinViewer.setExploded(true); $('explodedView').classList.add('active'); $('assembledView').classList.remove('active'); });
$('hideCovers').addEventListener('click', () => { if (!twinViewer) return; twinViewer.setHideCovers(!twinViewer.hideCovers); $('hideCovers').classList.toggle('active', twinViewer.hideCovers); });
$('componentSearch').addEventListener('input', (event) => { if (!twinModel || !twinViewer) return; const query = event.target.value.trim().toLowerCase(); if (query.length < 2) return; const part = twinModel.components.find((item) => item.label.toLowerCase().includes(query) || item.part_number?.toLowerCase().includes(query)); if (part) { twinViewer.setSelected(part.id); showTwinComponent(part); } });
$('twinProcedureAction').addEventListener('click', async () => { if ($('procedureSelect').value !== 'ADF_READER_REMOVE') { $('procedureSelect').value = 'ADF_READER_REMOVE'; await selectProcedure('ADF_READER_REMOVE'); } setView('guide'); });
$('logout').addEventListener('click', async () => { stopCamera({quiet: true}); await apiFetch('/api/auth/logout', {method: 'POST'}); location.assign('/login'); });
document.addEventListener('visibilitychange', () => { if (document.hidden && stream) stopCamera({quiet: true}); });
window.addEventListener('pagehide', () => stopCamera({quiet: true}));
window.addEventListener('beforeinstallprompt', (event) => { event.preventDefault(); installPrompt = event; $('installApp').hidden = false; });
$('installApp').addEventListener('click', async () => { if (!installPrompt) return; installPrompt.prompt(); await installPrompt.userChoice; installPrompt = null; $('installApp').hidden = true; });
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(() => {});
loadStatus(); loadProcedures();
