# Checklist Chrome Android — DS TechVision 0.2

Fecha de automatización: 2026-09-29.

## Evidencia automatizada

- [PASS] FastAPI inicia y `/health` devuelve versión 0.2.0.
- [PASS] Búsqueda bilingüe recupera evidencia con documento y página PDF.
- [PASS] Interfaz, estado, búsqueda y manuales rechazan acceso sin sesión.
- [PASS] Cookie autenticada incluye HttpOnly, Secure y SameSite=strict.
- [PASS] Manifest, service worker e iconos 192/512 están disponibles.
- [PASS] El service worker excluye navegación autenticada, `/api/`, manuales y respuestas privadas.
- [PASS] Certificado generado contiene SAN de IP privada y Authority Key Identifier.
- [PASS] Uvicorn respondió por HTTPS y el cliente validó la cadena usando la CA generada; no se desactivó TLS.
- [PASS] Contrato JavaScript: cámara trasera inicial, `audio: false`, errores tipados y liberación de tracks.
- [PASS] Regresión Windows: `pytest` — 4 pruebas aprobadas.

## Prueba física requerida

- [PENDIENTE] Instalar la CA en un Android administrado y confirmar que Chrome no muestra advertencias.
- [PENDIENTE] Iniciar sesión desde la Wi‑Fi local y confirmar que un acceso sin sesión no abre un PDF.
- [PENDIENTE] Instalar la PWA y abrirla desde la pantalla de inicio en modo standalone.
- [PENDIENTE] Autorizar cámara y comprobar que comienza con la trasera en orientación vertical.
- [PENDIENTE] Alternar trasera/frontal y verificar video en vivo.
- [PENDIENTE] Denegar permiso y comprobar el mensaje específico; rehabilitarlo desde Ajustes del sitio.
- [PENDIENTE] Abrir otra aplicación, volver y verificar que la cámara quedó liberada y puede reiniciarse.
- [PENDIENTE] Colocar/mover/limpiar una marca 2D y confirmar que no se presenta como reconocimiento automático.
- [PENDIENTE] Buscar “rodillo de recogida”, abrir la referencia y confirmar documento/página en el PDF original.
- [PENDIENTE] Detener la cámara y verificar que desaparece el indicador de uso de cámara de Android.

No se marca PASS ningún comportamiento dependiente de hardware Android sin evidencia en un dispositivo real.
