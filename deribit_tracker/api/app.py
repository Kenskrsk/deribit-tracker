from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from deribit_tracker.api.routes import create_prices_router
from deribit_tracker.config import Settings
from deribit_tracker.db.engine import build_engine, build_session_factory
from deribit_tracker.services.prices import InvalidDateRangeError, PriceNotFoundError


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Run with `uvicorn deribit_tracker.api.app:create_app --factory`."""
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(app_settings.database_url)
        app.state.session_factory = build_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(
        title="Deribit Price Tracker",
        description="BTC/ETH index prices collected from Deribit every minute.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(create_prices_router())
    _register_error_handlers(app)

    @app.get("/health", tags=["service"], summary="Liveness check")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PriceNotFoundError)
    async def handle_not_found(_: Request, error: PriceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})

    @app.exception_handler(InvalidDateRangeError)
    async def handle_invalid_range(_: Request, error: InvalidDateRangeError) -> JSONResponse:
        # Same shape as FastAPI's own validation errors, so clients parse one 422 format.
        detail = [{"type": "value_error", "loc": ["query", "date_from"], "msg": str(error)}]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail}
        )
