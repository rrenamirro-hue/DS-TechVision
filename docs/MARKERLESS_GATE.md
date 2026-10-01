# Gate markerless — Canon imageRUNNER 1643i

## Alcance y trazabilidad

El único paso con anchors AR es `right_cover_removed`, paso 7 del flujo ADF + Reader de 15 pasos. La referencia `1643_right_service_open` es un recorte de la fotografía OEM del Service Manual Rev. 6, página impresa 121 / PDF 132. El manual marca **1x** tornillo en esta preparación; el prototipo dibuja un tornillo. El contorno se trazó manualmente sobre la foto y es aproximado. La flecha figura como `SIMULATED_MOVEMENT` y no representa una trayectoria medida por Canon. No hay segundo tornillo verificable en esa imagen; añadirlo falsearía la evidencia OEM.

La biblioteca de tres estados está en `data/vision/1643i/catalog.json`: derecha con cubierta instalada y acceso frontal abierto, puerta trasera instalada y estado ADF previo a liberación. Las vistas front/left/internal quedan vacías. `components.json` enlaza tres piezas de la figura 160 con número, cantidad y página OEM sin asociarlas a anchors que el catálogo no ubica físicamente.

## Pipeline del cliente

1. El cliente carga tres recortes OEM autenticados. Cada uno se procesa en escalas 1, 0,75 y 0,55.
2. JSFeat extrae keypoints YAPE06 y descriptores ORB. Los frames de cámara se reducen como máximo a 480 × 360; el video no se transmite.
3. Se aplica matching de Hamming con ratio, correspondencias únicas y RANSAC para una homografía. Se exige al menos 9 inliers, proporción mínima 0,28, dispersión espacial y cuadrilátero plausible.
4. El mejor estado recibe `model_candidate`, `visual_confidence`, `reference_candidate`, `state_candidate` y `ocr_evidence`. Si ninguna referencia supera los umbrales, el resultado es `UNKNOWN` y el overlay se limpia en ese mismo ciclo.
5. Los anchors normalizados se proyectan por la homografía. Solo se dibujan si la referencia reconocida corresponde al paso operativo. No hay coordenadas fijas de pantalla.
6. OCR opcional: un JPEG reducido, en memoria, se envía al servidor local como máximo cada ~6 segundos después del match. Tesseract busca Canon/imageRUNNER/1643i/1643iF. OCR no decide por sí solo el modelo y no se persiste el frame.

JSFeat proviene del [repositorio oficial](https://github.com/inspirit/jsfeat), commit `4c7b336bbeeb26e6cd4cdf3c7d414abe273846f3`, licencia MIT incluida en `app/static/vendor/JSFEAT_LICENSE.txt`; SHA-256 de `jsfeat-min.js`: `974327515D68C91258EFD3BEFA03622C41BBED8E3172771994604325799977A1`. Se usa su ORB y estimador de homografía RANSAC. Se eligió porque la distribución estándar de OpenCV.js puede no exponer ORB sin compilación específica; [documentación de JSFeat](https://inspirit.github.io/jsfeat/) y [tutorial de homografía de OpenCV](https://docs.opencv.org/4.x/d7/dff/tutorial_feature_homography.html).

## Evidencia actual y gate restante

En Chrome de escritorio, un frame sintético de 480 × 360 que contiene la foto derecha a 330 × 244 se identificó como `1643_right_service_open`; al trasladarla 20 px y rotarla 0,05 rad se mantuvo la referencia y cambió la homografía; al retirar la foto el resultado fue `null`/`UNKNOWN`. Las otras dos fotos OEM se identificaron con su estado correcto. Una deformación proyectiva sintética reconoció la referencia y proyectó el anchor probado a `(239,13; 204,77)` frente a `(239,05; 204,70)` esperado. En la interfaz completa se inyectó un stream de canvas: el modelo/estado apareció, el overlay tuvo píxeles visibles, el anchor avanzó ~26,5 px en pantalla ante 20 px de traslación de la fuente (por la escala `object-fit: cover`) y tanto el estado como el overlay desaparecieron al retirar la foto. Un match tomó aproximadamente 28–54 ms en esa PC; no hay medida Android. Las pruebas API/flujo están en `pytest`.

**Gate no aprobado todavía en Android:** abrir foto OEM en monitor, usar Chrome Android con CA confiada, apuntar, mover/rotar/inclinar el móvil y grabar overlay + estado. Confirmar que el contorno y el único tornillo siguen la foto, medir deriva y tiempo de pérdida; comprobar que en ausencia de la foto desaparecen. No se necesita una impresora física. Si el reconocimiento falla por reflejos, baja resolución o desenfoque, la guía debe permanecer en fallback OEM y no se declara gate superado.

## Fuentes web

La [página oficial Canon Latin America](https://www.cla.canon.com/en/p/imagerunner-1643i) se registró en `web_sources.json` con atribución y URL. No se empaquetó fotografía web por no haberse confirmado permiso de redistribución. Ninguna fuente web determina secuencia, tornillos, part numbers ni procedimiento.
