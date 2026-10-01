# Aceptación UX/AR — 0.4.1

Los criterios siguientes separan evidencia de navegador de escritorio emulando 412 × 915 de validación física Android. Ningún test unitario prueba ergonomía real o alineación espacial.

| ID | Criterio | Evidencia actual | Estado |
|---|---|---|---|
| UX-01 | Login → paso 1 en ≤3 interacciones después de introducir credenciales | Flujo: enviar login, pulsar “Iniciar guía”; cuenta 2 acciones. No se midió sobre Android físico. | Pendiente Android |
| UX-02 | Imagen OEM visible sin scroll excesivo | En Chrome de escritorio a 412 × 915, la imagen del paso 1 y del paso 7 carga y termina en y≈557 de un viewport de 915 px. | Pasa en viewport; pendiente Android |
| UX-03 | Abrir cámara desde paso actual con un toque | Botón “Abrir cámara” del paso activa vista y solicita cámara en el mismo gesto. Permisos/cámara Android no disponibles en esta sesión. | Pendiente Android |
| UX-04 | Volver a guía sin perder estado | Vistas comparten `progress` del servidor; salir de cámara libera video, no modifica progreso. | Verificado en código; pendiente Android |
| UX-05 | RAG responde primero en español | Cada resultado comienza con `technicalSummary` en español, luego documento/página/enlace; extracto OEM cerrado. No genera diagnóstico. | Pasa estructura; revisión humana pendiente |
| UX-06 | Digital Twin no interfiere | `labView` oculto al iniciar y el modelo WebGL se carga al entrar al laboratorio. | Pasa viewport |
| AR-SIM-01 | Overlay ligado a la misma zona al mover Android frente a referencia visual | Seguimiento de cuatro fiduciales de color, suavizado y caducidad de 800 ms. Sin video móvil real ni prueba de desplazamiento físico. | **PENDIENTE** |

## Protocolo de prueba física

Usar un Android con Chrome y CA local confiada, conectado por `adb reverse tcp:8522 tcp:8522`. Abrir la referencia visual de la cubierta derecha en otra pantalla a brillo alto. Avanzar por el flujo secuencial hasta el paso 7. La cámara debe detectar los cuatro cuadrados, mostrar solo el contorno/screw/flecha sobre la **fotografía** y ocultarlos cuando cualquiera de las referencias se sale del encuadre o el seguimiento caduca. Mover el teléfono lateralmente, acercarlo, alejarlo e inclinarlo. Registrar un video y anotar pérdida de tracking, deriva y latencia. El resultado no valida ubicación sobre la Canon física. Si hay deriva relevante, mantener solo fallback OEM y no aprobar AR-SIM-01.

## Límites de la simulación

No hay seguimiento natural fiable implementado. El navegador detecta cuatro esquinas de color añadidas alrededor de la fotografía OEM. La estabilidad depende de iluminación, brillo, escala, reflejos y encuadre; una imagen de la Canon sin ese marco no se detecta. El overlay representa zonas aproximadas **dentro de la imagen OEM**, no coordenadas 3D ni posiciones medidas sobre una impresora. Solo el paso de la cubierta derecha lo permite. En otros pasos el sistema no dibuja marcas AR.
