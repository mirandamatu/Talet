# Reporte de Auditoría — Atipia OS

## Bugs Críticos Corregidos

- [CRÍTICO] CORS abierto en backend -> Se agregó `ALLOWED_ORIGINS` configurable y `CORSMiddleware` ahora usa una lista explícita desde settings. Archivos: `backend/app/core/config.py`, `backend/app/main.py`.
- [CRÍTICO] `JWT_SECRET` inseguro por defecto -> El default ahora es vacío y el startup falla si no está configurado. También se mantiene warning si aparece el valor inseguro `change-me`. Archivos: `backend/app/core/config.py`, `backend/app/main.py`.
- [CRÍTICO] Startup con API deprecada -> Se reemplazaron los handlers `@app.on_event('startup')` por `lifespan`. Archivo: `backend/app/main.py`.
- [IMPORTANTE] Headers HTTP de seguridad faltantes -> Se agregaron `X-Content-Type-Options`, `X-Frame-Options` y `Referrer-Policy`. Archivo: `backend/app/main.py`.
- [IMPORTANTE] `GET /api/candidates` sin paginación -> Se agregaron `limit` y `offset` con máximo `500`. Archivo: `backend/app/routes/client.py`.
- [IMPORTANTE] Candidatos creados desde búsqueda sin `client_id` -> Se completa `client_id` al crear candidatos para mantener filtros multi-cliente consistentes. Archivo: `backend/app/routes/talent.py`.
- [CRÍTICO UX] `window.prompt()` y `alert()` en análisis de entrevistas -> Se reemplazaron por `InterviewAnalysisModal` con textarea, loading y resultado dentro de la UI. Archivo: `frontend/src/App.jsx`.
- [IMPORTANTE XSS] Job descriptions renderizadas sin sanitizar -> Los `dangerouslySetInnerHTML` de descripciones ahora pasan por `DOMPurify.sanitize`. Archivo: `frontend/src/App.jsx`.

## Mejoras UX Aplicadas

- [UX] Subida de reunión con input nativo -> Reemplazada por `<FileInput>` con validación de tipo y tamaño. Archivo: `frontend/src/App.jsx`.
- [UX] Edición de búsqueda sin validación inline -> Se agregaron `<Field>` y validación para título obligatorio y email de contacto. Archivo: `frontend/src/App.jsx`.
- [UX] Alerts de estado/presentación de candidato -> Reemplazadas por `useToast()`. Archivo: `frontend/src/App.jsx`.
- [UX] Listas y KPIs sin feedback de carga -> Se agregaron skeletons para búsquedas, candidatos y grilla KPI. Archivo: `frontend/src/App.jsx`.
- [UX] Botones de menú solo-icono sin etiqueta -> Se agregaron `aria-label` en acciones de candidato y banco de talento. Archivo: `frontend/src/App.jsx`.
- [UX] Carga global de candidatos sin límite -> El frontend pide `GET /candidates?limit=200` como límite provisorio hasta implementar paginación visual. Archivo: `frontend/src/App.jsx`.

## Mejoras de Código

- [REFACTOR] `Login` extraído desde el monolito -> Nuevo componente en `frontend/src/features/auth/Login.jsx`.
- [REFACTOR] `Notifications` extraído desde el monolito -> Nuevo componente en `frontend/src/features/notifications/Notifications.jsx`.
- [REFACTOR] Error boundary agregado -> La app principal ahora se exporta envuelta en `ErrorBoundary` para evitar pantalla en blanco ante errores de render. Archivo: `frontend/src/App.jsx`.
- [DB] Índices faltantes agregados en modelos y migración -> `candidates.search_id`, `candidates.archived_at`, `candidate_search_assignments.archived_at`, `status_history.candidate_id`. Archivos: modelos correspondientes y `backend/alembic/versions/0016_missing_candidate_indexes.py`.
- [TEST INFRA] Dependencias y configuración de tests agregadas -> `pytest`, `httpx`, Vitest, Testing Library, setup de jsdom y scripts. Archivos: `backend/requirements.txt`, `frontend/package.json`, `frontend/vite.config.js`.

## Tests Agregados

- [TEST] Backend auth -> login válido, password incorrecto, cuenta inactiva, token requerido y rol bloqueado. Resultado: PASS.
- [TEST] Backend búsquedas -> creación, listado, visibilidad cliente, soft delete y cambio de estado. Resultado: PASS.
- [TEST] Backend candidatos -> carga, soft delete, envío a banco, asignación y fallback IA sin API key. Resultado: PASS.
- [TEST] Backend IA -> reanálisis de candidato/búsqueda con mocks y candidato sin CV. Resultado: PASS.
- [TEST] Backend careers -> career page pública, postulación pública y slug inexistente. Resultado: PASS.
- [TEST] Frontend Login -> validación de email, loading y login exitoso con `fetch` mockeado. Resultado: PASS.
- [TEST] Frontend UI compartida -> `Field`, toast, confirm, skeleton, password toggle y file input. Resultado: PASS.

## Resultados De Verificación

- `python -m pytest` en `backend`: 21 passed, 29 warnings.
- `npm test` en `frontend`: 10 passed.
- `npm run build` en `frontend`: exitoso. Queda warning no bloqueante por chunks mayores a 500 kB, especialmente `react-pdf`/worker y bundle principal.
- `ReadLints`: sin errores en archivos editados.

## Items Pendientes (requieren acción externa o decisión del equipo)

- Configurar `JWT_SECRET` real en producción con un valor aleatorio de mínimo 32 caracteres.
- Configurar `ALLOWED_ORIGINS` en producción con el dominio final del frontend, por ejemplo `https://app.atipia.com`.
- Revisar `backend/Dockerfile`: hoy ejecuta `python -m app.seed` en cada arranque. Para producción conviene quitarlo o hacerlo condicional para evitar usuarios demo.
- Proteger `/uploads` con acceso autenticado o URLs firmadas. Cambiarlo puede impactar CVs ya vinculados.
- Proteger webhooks de Zoom/Meet con firma, token compartido o allowlist. Requiere conocer el contrato de integración.
- Migrar auth de JWT en `localStorage` a cookies `httpOnly` si se busca una mitigación fuerte contra XSS. En esta pasada se mitigó sanitizando HTML.
- Validar SMTP, S3 y Google OAuth con credenciales reales de producción.
- Agregar CI para ejecutar `pytest`, `npm test` y `npm run build` en cada PR.
- Reducir bundle frontend con code splitting, especialmente vistas pesadas y `react-pdf`.

## Variables de entorno requeridas para producción

- `DATABASE_URL`: conexión PostgreSQL. Sin esto el backend no arranca contra la DB real.
- `JWT_SECRET`: secreto de firma JWT. Sin esto el backend falla al iniciar.
- `ALLOWED_ORIGINS`: orígenes permitidos para CORS. Si falta, queda solo `http://localhost:5173`.
- `AI_API_KEY`: habilita OpenAI. Si falta, se usan heurísticas/fallbacks donde estén disponibles.
- `AI_API_BASE_URL`, `AI_MODEL`, `AI_TIMEOUT_SECONDS`: configuración del proveedor IA.
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`: habilitan Calendar/Gmail.
- `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_PUBLIC_URL_BASE`: storage de CVs/documentos. Si falta, puede caer a storage local según flujo.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`: envío de emails. Si falta, notificaciones por correo pueden no salir.
