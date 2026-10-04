from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.analysis import router
from backend.api.sources import router as sources_router

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
# The UI loads only its own files and calls only this API; inline scripts/styles are not allowed.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)

app = FastAPI(title="Otter Data", version="1.0.0")
app.include_router(router)
app.include_router(sources_router)


UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # The API only serves its own page: refuse state-changing calls made by other websites.
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin")
        same_origin = f"{request.url.scheme}://{request.url.netloc}"
        if (origin and origin != same_origin) or request.headers.get(
            "sec-fetch-site"
        ) == "cross-site":
            return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        # Local app: always revalidate (ETag/Last-Modified) so UI updates show up immediately.
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only: this does not assert database connectivity or an AI pipeline."""
    return {"status": "ok", "stage": "foundation"}


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
