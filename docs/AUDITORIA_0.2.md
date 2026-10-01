# Auditoría DS TechVision 0.2

## Estado encontrado

- Backend FastAPI 0.1 con rutas de estado, equipos, búsqueda y PDFs.
- Frontend HTML/CSS/JavaScript responsive con cámara básica y marca manual 2D.
- Recuperador local TF‑IDF bilingüe e índice JSONL; sin LLM ni llamadas de red.
- Dos documentos originales presentes e indexados: Service Manual Rev. 6 (437 páginas) y Parts Catalog Rev. 9.
- Script PowerShell limitado a localhost y sin autenticación/HTTPS.
- Dos pruebas basales para ingestión, búsqueda y contrato API.

## Decisiones 0.2

- Se conservó el índice, la ingestión y `LocalRetriever`; no se reconstruyó el RAG funcional.
- Se añadió autenticación con hash scrypt, cookie firmada HttpOnly/Secure/SameSite y límite básico de intentos.
- Manuales, búsqueda, estado e interfaz requieren sesión. Solo login, salud y recursos PWA públicos quedan accesibles.
- Se añadió PWA de alcance limitado. El service worker excluye contenido privado y no promete offline completo.
- Se añadió CA local y certificado de servidor con SAN de IPv4 privada; claves y credenciales se guardan fuera del repositorio.
- La cámara libera el `MediaStream` al detener, navegar u ocultar la app. El cambio de aplicación requiere reanudación explícita.
- Las superposiciones se etiquetan como manuales, sin afirmar reconocimiento o AR espacial.

## Fuera de alcance preservado

PortalBrain y SGS no se inspeccionaron ni modificaron. Los PDF originales no fueron escritos ni reemplazados. No se entrenaron modelos ni se inventaron procedimientos técnicos.
