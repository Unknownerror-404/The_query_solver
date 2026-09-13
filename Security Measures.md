# Civic App TODO List
## Security
- [ ] **Rate‑limit authentication** – limit login attempts per IP to prevent brute‑force attacks. Implemented via a FastAPI middleware that tracks attempts in an in‑memory store. 
- [ ] Pin‑code guardrails for file uploads – MIME type and size checks.
- [ ] Rotating usage keys for third‑party services.
- [ ] Database connection pool tuning.

## Performance
- [ ] Offload video frame extraction & inference to a background worker (Celery/RQ).
- [ ] Cache frequent database queries (Redis/LRU cache).
- [ ] Enable gzip / brotli compression in ASGI server.

## Reliability & Observability
- [ ] Rate‑limit authentication and API endpoints.
- [ ] Structured JSON logging for telemetry (timestamp, user, endpoint, latency, error).
- [ ] Health‑check endpoint for orchestration.

## Maintainability
- [ ] Extract inline CSS into `static/shared.css`.
- [ ] Centralise route handlers (router files).
- [ ] Type‑annotate all public functions for IDE help.
- [ ] Add unit tests for new helpers (e.g., `distance_km` overload). 

## UX / Accessibility
- [ ] Client‑side form validation using HTML5 or tiny JS bundle.
- [ ] Add ARIA roles and skip‑links for screen readers.
- [ ] Internationalization: extract strings, use Babel.

## CI / Deployment
- [ ] Add `ruff` / `black` lint/run checks to CI.
- [ ] Create Dockerfile and Compose scripts.
- [ ] Push image to GitHub Container Registry.
- [ ] Automatic release on merge to main branch.

## Documentation
- [ ] Update README with new installation steps.
- [ ] Document API usage and limits.
- [ ] Provide sample config for environment variables.