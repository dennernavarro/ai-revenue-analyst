# Stage 7 — Docker

**Built:** a two-stage Dockerfile (uv builder → slim Python runtime, non-root
user, bytecode-compiled, `uv.lock`-frozen deps) and a one-service
docker-compose with a healthcheck and a named volume for the SQLite
checkpoints.

**What I learned**

- *uv makes container builds clean:* copy `pyproject.toml` + `uv.lock` first
  and `uv sync --frozen --no-install-project` so the dependency layer caches
  independently of source changes; the runtime stage needs no uv at all,
  just the `.venv` on PATH.
- *Non-root users meet volumes the hard way.* The named volume mounted
  `/app/.state` owned by root, the `analyst` user couldn't create the SQLite
  file, and the container died on boot. Second lesson in the same minute:
  `WORKDIR` creates `/app` as root, so even `mkdir` inside it failed until
  the directory was created and chowned before `USER`. Permission bugs only
  show up when you actually run the container.
- The healthcheck hits `GET /properties` with a stdlib `urllib` one-liner —
  slim images have no curl.
- Verified end to end: REST and `/chat` answered from inside the container,
  and a conversation survived `docker compose restart` thanks to the volume
  (same `conversation_id`, zero tool calls to recall context).
