# Seguimiento visual 0.3

## Implementación

La primera etapa usa `BarcodeDetector` de Chrome para detectar un QR por paso. El detector entrega las cuatro esquinas de la referencia. DS TechVision proyecta el ancla calibrada mediante interpolación bilineal sobre ese cuadrilátero, por lo que el indicador acompaña traslación, escala y cambio de perspectiva del marcador.

La calibración requiere dos toques humanos mientras la referencia está seguida: centro del objetivo y radio del contorno. Se almacenan coordenadas relativas al marcador, nunca coordenadas fijas de pantalla. La pérdida de referencia durante más de 800 ms limpia flechas y contornos. Cambiar de paso cambia también el identificador QR esperado.

## Límites explícitos

- `BarcodeDetector` continúa siendo una API experimental/de disponibilidad limitada. El prototipo comprueba soporte y formato QR en ejecución.
- Un marcador QR prueba seguimiento de una referencia planar; no reconoce la impresora ni sus piezas.
- La posición física del marcador respecto del objetivo debe definirse y validarse sobre el equipo real.
- Las calibraciones quedan marcadas `LOCAL_UNVALIDATED`; no se presentan como espacialmente verificadas.
- Retirar una cubierta o completar un paso invalida la suposición del estado anterior. Por eso hay un QR y una calibración independientes por paso.

## Evaluación de MindAR y Three.js

MindAR ofrece image tracking con integración Three.js y sería la siguiente etapa cuando existan fotografías reales, controladas y representativas de cada estado físico. Requiere compilar targets y validar estabilidad/precisión sobre la Canon real. No se incorporó ahora porque usar capturas del manual como target no demostraría reconocimiento confiable del equipo físico.

Three.js sirve para renderizar objetos 3D/WebXR, pero por sí solo no aporta reconocimiento de piezas ni targets calibrados. Añadirlo antes de obtener anclas físicas verificadas aumentaría complejidad sin resolver la incertidumbre espacial.

La etapa QR es deliberadamente temporal y degradable: ante cualquier duda, la autoridad es la fotografía/PDF OEM.
