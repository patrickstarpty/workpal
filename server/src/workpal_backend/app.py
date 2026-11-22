from contextlib import asynccontextmanager
from .health import ServerHealth
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from workpal_backend.infrastructure.database import Database, DatabaseBusy
from workpal_backend.infrastructure.redis import RedisResources

def create_app(settings):
    configured_frontend = settings.frontend_origin if 'frontend_origin' in settings.model_fields_set else ''
    settings = type(settings).model_validate(settings.model_dump())
    health = ServerHealth()
    from .realtime.daemon_metrics import DaemonMetrics
    daemon_metrics = DaemonMetrics()
    @asynccontextmanager
    async def lifespan(app):
        app.state.database = Database(settings)
        try:
            app.state.redis = RedisResources(settings)
            from .realtime.hub import Hub
            from .realtime.membership_queries import MembershipQueries
            import anyio
            async def membership_lookup(identities):
                def read():
                    with app.state.database.transaction() as session:
                        return MembershipQueries(session).members(identities)
                return await anyio.to_thread.run_sync(read, abandon_on_cancel=True)
            async def membership_check(workspace, user):
                return (await membership_lookup([(workspace, user)])).get((workspace, user), False)
            app.state.realtime = Hub(membership_lookup=membership_lookup, membership_check=membership_check)
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
    from .auth.errors import AuthenticationError, authentication_error
    app.add_exception_handler(AuthenticationError, authentication_error)
    @app.middleware('http')
    async def session_boundary(request, call_next):
        request.scope['headers'] = [(k,v) for k,v in request.scope['headers'] if k.lower() not in (b'x-actor-source', b'x-agent-id', b'x-task-id')]
        response = await call_next(request)
        response.raw_headers.extend(getattr(request.state, 'renewal_cookie_headers', []))
        return response

    @app.get('/health')
    def live():
        return health.live()

    @app.get('/health/realtime')
    async def realtime_health(request: Request):
        from .realtime.health import metrics_response
        return metrics_response(request, settings.realtime_metrics_token, app.state.realtime.metrics, daemon_metrics)

    @app.get('/readyz')
    @app.get('/healthz')
    def ready():
        return health.ready(app.state.database)
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    from .auth.routes import router
    app.state.settings = settings
    from .realtime.origins import OriginPolicy, router_origins
    from .auth.profile_decode import go_trim_space
    app.state.ws_origin_policy = OriginPolicy(
        router_origins({'CORS_ALLOWED_ORIGINS': settings.cors_allowed_origins, 'FRONTEND_ORIGIN': configured_frontend}),
        [go_trim_space(value) for value in settings.trusted_proxies.split(',')])
    app.state.daemon_metrics = daemon_metrics
    from .infrastructure.events import EventBus
    from .infrastructure.outbox import append_event
    app.state.events=EventBus()
    def persist_domain_event(event):
        with app.state.database.transaction() as session:append_event(session,event)
    app.state.events.subscribe_all(persist_domain_event)
    app.include_router(router)
    from .auth.personal_tokens import router as token_router
    app.include_router(token_router)
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
    from .files.routes import router as file_router
    app.include_router(file_router)
    from .agents.env import router as agent_env_router
    app.include_router(agent_env_router)
    from .agents.skills import router as agent_skill_router
    app.include_router(agent_skill_router)
    from .runtimes.routes import router as runtime_router
    app.include_router(runtime_router)
    from .workspace_content.routes import router as content_router
    app.include_router(content_router)
    @app.exception_handler(DatabaseBusy)
    async def database_busy(request, exc):
        return JSONResponse({'error': 'Database is busy; retry later', 'retryable': True}, status_code=503, headers={'Retry-After': '1'})
    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if request.url.path == '/api/tokens' or request.url.path.startswith('/api/tokens/'):
            from .infrastructure.go_response import GoJSONResponse
            return GoJSONResponse({'error': exc.detail}, status_code=exc.status_code, headers=exc.headers)
        return JSONResponse({'error': exc.detail}, status_code=exc.status_code, headers=exc.headers)
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({'error': 'invalid request'}, status_code=400)
    if settings.frontend_dir is not None:
        from .frontend import mount_frontend
        mount_frontend(app, settings.frontend_dir)
    return app
