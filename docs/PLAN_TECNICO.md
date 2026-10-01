# DS TechVision — Plan de ingeniería (0.1 → 0.2)

## Contexto

Proyecto autónomo para técnicos de servicio; la UI, las sesiones y los índices no dependen de PortalBrain. La versión 0.1 contiene búsqueda lexical reproducible para verificar los documentos cargados. **No se ha reutilizado aún el código semántico real de PortalBrain** porque no forma parte del material entregado a este repositorio.

## Documentos fuente

- `SM_R6`: manual de servicio, PDF de 437 páginas; procedimientos de mantenimiento y reparación.
- `PC_R9`: catálogo de repuestos, PDF de 67 páginas; números de pieza y dibujos de despiece.
- El nombre de cada documento, la revisión, SHA-256, la página física PDF y el modelo declarado se almacenan en `manifest.json` y `chunks.jsonl` locales. La página PDF puede diferir del número impreso en el manual.
- PDF y corpus derivado no se distribuyen con el código.

## Flujo previsto para un técnico

1. Confirmar modelo y variante mediante etiqueta o número de serie (a desarrollar).
2. Consultar síntoma y recuperar páginas trazables.
3. Seleccionar un procedimiento aprobado y revisar sus precauciones.
4. Capturar la vista real con cámara y reconocer referencia visual/objetivo calibrado.
5. Resaltar una pieza sólo si seguimiento y modelo son válidos; si se pierde el seguimiento, ocultar la anotación.
6. Registrar la confirmación manual de pasos y el resultado.
7. Adjuntar referencia al reporte de intervención.

## Separación de responsabilidades

- **Retrieval**: responde solo con extractos y coordenadas de página del documento; el futuro RAG semántico se sustituirá detrás de `LocalRetriever.search`.
- **Selector técnico**: decide qué procedimiento OEM es aplicable; jamás deducir procedimiento desde solo un diagrama de despiece.
- **Motor AR**: coordenadas y modelos 3D desde calibraciones versionadas, nunca desde una salida libre de LLM.
- **UI**: no afirma que una zona está reconocida si su posición es manual.

## Criterios para aprobar 0.2 (AR real)

- Datos fotográficos del equipo físico y objetivo de seguimiento para cada postura (cerrado, puerta abierta, bandeja retirada).
- Calibración robusta en el móvil, evaluación de pérdida y recuperación del seguimiento.
- Validación de componente por número de pieza contra el catálogo.
- Evidencia OEM exacta y aviso de seguridad antes de los pasos físicos.
- HTTPS confiable, login y permisos por rol; sin publicación de PDF sin autorización.
- Pruebas reproducibles con fotografías y escenarios de baja luz, inclinación y oclusión.
- Sin modificaciones a PortalBrain o SGS.

## Caso inicial

Identificación del **cassette paper pick-up roller**, enlazando catálogo de partes (PDF páginas 27/29, según voltaje) y procedimiento de servicio (PDF página 213 entre los resultados de búsqueda). Estas referencias son puntos de partida para revisión técnica; no se publican instrucciones de desmontaje hasta verificarlas página por página y probar físicamente la intervención.
