# DS TechVision — 0.6 continuous vision

Prototipo local para la Canon imageRUNNER 1643i y la intervención **retirar ADF + Reader**. Conserva los 15 pasos OEM secuenciales, autenticación, PWA, cámara Android, ADB reverse, RAG y PDF originales. El Digital Twin sigue en Laboratorio como mapa conceptual, no como guía de posición física.

## Inicio

```powershell
.\Iniciar_DS_TechVision.ps1 -UsbAdb
# o en LAN privada:
.\Iniciar_DS_TechVision.ps1 -LanIP 192.168.1.20
```

Para la cámara Android, Chrome debe confiar en la CA local del servidor. Ver [diagnóstico HTTPS](docs/HTTPS_ANDROID_0.4.1.md).

Cada ejecución de ADF + Reader tiene un identificador `TV-AAAAMMDD-NNNN`: elegí **CONTINUAR** para retomar una abierta o **NUEVA INTERVENCIÓN** para empezar en 0/15. El progreso anterior se conserva aparte. **Ver manual** abre una página OEM autenticada dentro de la app, con enlace al PDF completo. La sesión usa cookie HttpOnly, SameSite=Lax, Path=/ y Secure en HTTPS.

La búsqueda utiliza `intfloat/multilingual-e5-small` local (384 dimensiones), más coincidencia exacta de identificadores OEM; ya no usa TF-IDF. El primer inicio descarga el modelo y calcula el índice; los siguientes muestran `EMBEDDING_INDEX_LOADED`. Para cambiar de modelo, establecer `DS_TECHVISION_EMBEDDING_MODEL` antes de iniciar. Los vectores y metadatos persistentes están en `data/index/`; los PDF originales no se modifican.

La cámara puede reconocer equipo, vista y estado desde el paso 1 mediante `openai/clip-vit-base-patch32` (embeddings de imagen, separados del RAG textual), OCR local y ORB para localización fina. El índice visual persiste en `data/vision/1643i/visual_index/`. La primera ejecución descarga CLIP y calcula los vectores; las siguientes cargan el índice. `DS_TECHVISION_VISUAL_MODEL` permite cambiar a otro checkpoint CLIP compatible y reconstruirlo. Se envía un JPEG reducido al servidor local autenticado aproximadamente cada 2,5 segundos; el video continuo no se guarda. La biblioteca activa proviene de los PDF Canon suministrados, con referencias frontal, derecha, izquierda, posterior, ADF e interior, más una ilustración de catálogo usada como ejemplo negativo. Los estados sin evidencia suficiente devuelven `UNKNOWN`. El catálogo de piezas conserva la autoridad para números y cantidades; la cámara no los deduce por apariencia.

## Demostración sin marcadores

1. Abrí la intervención y avanzá hasta **Retirar la cubierta lateral derecha** (paso 7 de 15).
2. Abrí **Foto de prueba** en otro monitor/tablet: es un recorte sin añadidos del Service Manual Rev. 6, PDF 132.
3. En Android, tocá **Abrir cámara** y apuntá a esa foto.
4. El cliente compara rasgos ORB de la imagen con la biblioteca OEM, calcula una homografía RANSAC y transforma el contorno, un tornillo y la flecha. Al perder la imagen, borra los overlays y muestra `UNKNOWN`.

La identificación indica coincidencia con una **referencia OEM** del modelo, no autenticación visual de cualquier equipo físico. El OCR es evidencia complementaria y puede no encontrar texto en la foto. Si el estado no coincide con el paso o la confianza es baja, no se dibuja AR. El manual muestra **un tornillo (`1x`)** en la fotografía de ese paso; no se inventa un segundo. La flecha es `SIMULATED_MOVEMENT`.

La biblioteca `data/vision/1643i/` contiene vistas derecha, posterior y ADF recortadas de los PDFs suministrados. Las carpetas `front/`, `left/` e `internal/` están reservadas, sin referencias confiables asignadas todavía. La [página oficial de Canon](https://www.cla.canon.com/en/p/imagerunner-1643i) queda como enlace de investigación, no se empaqueta ni se usa como autoridad técnica.

## Implementación y pruebas

El matching se ejecuta en el navegador con una copia local de JSFeat (MIT) y no envía video completo al servidor. Cada ~6 segundos, si ya hay una coincidencia, puede enviar **un JPEG temporal** al backend local para OCR; no se guarda. Ver [criterio de aceptación y límites](docs/MARKERLESS_GATE.md).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

La prueba de escritorio con imágenes sintéticas verifica identificación de referencia, traslación, rotación leve, homografía y pérdida. **El gate en Android apuntando a un monitor aún requiere ejecución y registro**; no se declara aprobado por las pruebas automatizadas.
