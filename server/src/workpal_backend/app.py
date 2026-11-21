from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from workpal_backend.infrastructure.database import Database, DatabaseBusy
from workpal_backend.infrastructure.redis import RedisResources

def create_app(settings):
    settings = type(settings).model_validate(settings.model_dump())
    started = datetime.now(timezone.utc).isoformat()
    @asynccontextmanager
    async def lifespan(app):
        app.state.database = Database(settings)
        try:
            app.state.redis = RedisResources(settings)
            from .realtime.hub import Hub
            app.state.realtime = Hub()
            from .realtime.consumer import RealtimeConsumer
            consumer = RealtimeConsumer(app.state.database, app.state.redis, app.state.realtime)
            app.state.realtime_consumer = consumer
            task = None
            # An unmigrated API can still report liveness/readiness; migrate then restart.
            try:
                schema_ready = app.state.database.readiness() == 'ok'
            except Exception:
                schema_ready = False
            if schema_ready:
                task = asyncio.create_task(consumer.run(), name='realtime-consumer')
            app.state.realtime_consumer_task = task
            try: yield
            finally:
                try:
                    consumer.stop()
                    if task is not None:
                        await asyncio.wait_for(task, 3)
                finally:
                    try:
                        await app.state.realtime.close()
                    finally:
                        await app.state.redis.close()
        finally: app.state.database.close()
    app = FastAPI(lifespan=lifespan)
    @app.middleware('http')
    async def session_boundary(request, call_next):
        request.scope['headers'] = [(k,v) for k,v in request.scope['headers'] if k.lower() not in (b'x-actor-source', b'x-agent-id', b'x-task-id')]
        response = await call_next(request)
        if response.status_code < 400 and request.method in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('authorization') is None and hasattr(request.state, 'session_claims'):
            from .auth.routes import refresh
            try:
                refresh(request, response)
            except DatabaseBusy as exc:
                return await database_busy(request, exc)
            except HTTPException as exc:
                return await http_error(request, exc)
        return response

    @app.get('/health')
    def live(): return dict(status='ok',pid=os.getpid(),started_at=started)
    @app.get('/readyz')
    @app.get('/healthz')
    async def ready():
        checks = dict(db='ok', migrations='unknown', redis='error')
        try: checks['migrations'] = app.state.database.readiness()
        except Exception: checks['db'] = 'error'
        checks['redis'] = 'ok' if await app.state.redis.ready() else 'error'
        ok = all(v == 'ok' for v in checks.values())
        return JSONResponse(dict(status='ok' if ok else 'not_ready',checks=checks),status_code=200 if ok else 503)
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    from .auth.routes import router
    app.state.settings = settings
    app.include_router(router)
    from .auth.profile_routes import router as profile_router
    app.include_router(profile_router)
    from .auth.completion_routes import router as completion_router
    app.include_router(completion_router)
    from .auth.waitlist_routes import router as waitlist_router
    app.include_router(waitlist_router)
    from .auth.onboarding_routes import router as onboarding_router
    app.include_router(onboarding_router)
    from .workspaces.routes import router as workspace_router
    app.include_router(workspace_router)
    from .workspaces.membership_mutation_routes import router as membership_mutation_router
    app.include_router(membership_mutation_router)
    from .workspaces.invitation_routes import router as invitation_router
    app.include_router(invitation_router)
    from .workspaces.invitation_mutation_routes import router as invitation_mutation_router
    app.include_router(invitation_mutation_router)
    from .workspaces.invitation_decline import router as invitation_decline_router
    app.include_router(invitation_decline_router)
    from .realtime.routes import router as realtime_router
    app.include_router(realtime_router)
    from .workspace_content.analytics_routes import router as analytics_router
    app.include_router(analytics_router)
    from .workspace_content.routes import router as content_router
    app.include_router(content_router)
    @app.exception_handler(DatabaseBusy)
    async def database_busy(request, exc):
        return JSONResponse({'error': 'Database is busy; retry later', 'retryable': True}, status_code=503, headers={'Retry-After': '1'})
    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({'error': exc.detail}, status_code=exc.status_code, headers=exc.headers)
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({'error': 'invalid request'}, status_code=400)
    return app
