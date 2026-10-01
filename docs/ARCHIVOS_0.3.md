# Archivos DS TechVision 0.3

## Añadidos

- `data/procedures/adf_reader.json`: procedimiento OEM estructurado.
- `app/procedures.py`: catálogo, imágenes OEM, progreso y calibración.
- `app/ar_geometry.py`: geometría planar verificable.
- `app/generate_markers.py`: generación reproducible de QR por paso.
- `app/static/ar-tracking.js`: proyección y timeout de tracking.
- `app/static/ar.css`: interfaz de procedimiento/AR.
- `app/static/markers/ADF_REMOVE_01.png` a `ADF_REMOVE_05.png`.
- `Configurar_ADB_Reverse.ps1`.
- `docs/AR_TRACKING_0.3.md`, `docs/CHECKLIST_0.3.md` y este informe.

## Modificados

- `app/main.py`: API 0.3 autenticada.
- `app/static/index.html` y `app/static/app.js`: motor paso a paso y cámara AR.
- `app/static/manifest.webmanifest` y `service-worker.js`.
- `Iniciar_DS_TechVision.ps1`, `requirements.txt`, `tests/test_baseline.py`, `README.md`.

No se modificaron los PDF, PortalBrain ni SGS.
