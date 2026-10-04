import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models.draft import Draft  # noqa: F401  (registers the table)
from app.routers import github_webhook
from app.routers.review import get_db, router as review_router
from app.security import require_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready")
    yield


app = FastAPI(
    title="DSA Automation",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # CSRF protection for the review pages. Browsers label every request with
    # Sec-Fetch-Site, which says where it came from. We only allow requests
    # from this site itself (or typed/bookmarked: "none").
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/review"):
        fetch_site = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")

        if fetch_site is not None:
            blocked = fetch_site not in {"same-origin", "none"}
        elif origin is not None:
            # Older browsers: fall back to comparing the Origin header.
            blocked = (
                origin == "null"
                or urlparse(origin).netloc != request.headers.get("host", "")
            )
        else:
            blocked = False  # no browser headers: not a browser cross-site attack

        if blocked:
            return JSONResponse(
                {"detail": "Cross-site request blocked"}, status_code=403
            )

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/review"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(github_webhook.router)
app.include_router(review_router)


@app.get(
    "/api/latest-draft",
    include_in_schema=False,
    dependencies=[Depends(require_auth)],
)
def latest_draft(db: Session = Depends(get_db)):
    """Newest draft id. The laptop watcher polls this to open the review page."""
    return {"id": db.scalar(select(func.max(Draft.id)))}


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/review")