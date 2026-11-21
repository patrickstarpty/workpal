from pathlib import Path
import os
from pydantic import Field, model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(populate_by_name=True, extra='ignore')
    frontend_dir: Path | None = Field(default=None, validation_alias='WORKPAL_FRONTEND_DIR')
    database_url: str = Field(default='sqlite:///server/data/python/workpal.sqlite', validation_alias='WORKPAL_DATABASE_URL')
    redis_url: str = Field(default='redis://127.0.0.1:6379', validation_alias='REDIS_URL', repr=False)
    redis_key_prefix: str = Field(default='workpal:', validation_alias='REDIS_KEY_PREFIX')
    host: str = Field(default='127.0.0.1', validation_alias='WORKPAL_HOST')
    port: int = Field(default=4175, ge=1, le=65535, validation_alias='WORKPAL_PORT')
    environment: str = Field(default='development', validation_alias='WORKPAL_ENV')
    dev_auth: bool = Field(default=False, validation_alias='WORKPAL_DEV_AUTH')
    auth_secret: str | None = Field(default=None, validation_alias='AUTH_SECRET', repr=False)
    frontend_origin: str = Field(default='http://localhost:4173', validation_alias='FRONTEND_ORIGIN')
    auth_token_ttl: int = Field(default=2592000, ge=60, validation_alias='AUTH_TOKEN_TTL')
    cookie_domain: str = Field(default='', validation_alias='COOKIE_DOMAIN')

    @field_validator('cookie_domain', mode='before')
    @classmethod
    def domain(cls, value):
        import ipaddress
        value = str(value).strip()
        try:
            ipaddress.ip_address(value.lstrip('.'))
            return ''
        except ValueError:
            return value

    @field_validator('auth_token_ttl', mode='before')
    @classmethod
    def ttl(cls, value):
        import re
        raw = str(value).strip()
        units = {'ns':1e-9,'us':1e-6,'µs':1e-6,'μs':1e-6,'ms':.001,'s':1,'m':60,'h':3600}
        parts = re.findall(r'(\d+(?:\.\d*)?|\.\d+)(ns|us|µs|μs|ms|s|m|h)', raw.lstrip('+'))
        try:
            seconds = int(raw) if re.fullmatch(r'[+-]?\d+', raw) else sum(float(n)*units[u] for n,u in parts) if ''.join(n+u for n,u in parts) == raw.lstrip('+') and parts else 0
            if seconds <= 0 or seconds > 9223372036:
                return 2592000
            return max(60, int(seconds))
        except (ValueError, OverflowError):
            return 2592000

    disable_workspace_creation: bool = Field(default=False, validation_alias='DISABLE_WORKSPACE_CREATION')
    workspace_creation_allowed_emails: str = Field(default='', validation_alias='WORKSPACE_CREATION_ALLOWED_EMAILS')

    upload_dir: Path = Field(default=ROOT/'server/data/python/uploads', validation_alias='WORKPAL_UPLOAD_DIR')
    worker_poll_interval: float = Field(default=1, ge=.05, le=30, validation_alias='WORKPAL_WORKER_POLL_INTERVAL')
    reconcile_interval: float = Field(default=60, ge=.05, le=86400, validation_alias='WORKPAL_RECONCILE_INTERVAL')

    @field_validator('upload_dir')
    @classmethod
    def upload_path(cls, value):
        # Resolve system aliases such as macOS /var -> /private/var in parents
        # only; the final root must never itself be a symlink.
        path = Path(os.path.abspath(value))
        if path.is_symlink(): raise ValueError('Upload root cannot be a symlink')
        path = path.parent.resolve()/path.name
        repo = ROOT.resolve()
        intended = repo/'server/data/python/uploads'
        protected = Path(os.environ.get('WORKPAL_DB') or repo/'server/data/workpal.sqlite').resolve().parent
        # The default data directory has one explicit Python upload exception.
        # A separately configured mock directory has no such exception.
        configured_mock = protected != repo/'server/data'
        if (path == Path('/') or path == repo or path in repo.parents
                or (path.is_relative_to(repo) and not path.is_relative_to(intended))
                or (configured_mock and (path == protected or path.is_relative_to(protected) or protected.is_relative_to(path)))):
            raise ValueError('Dedicated upload directory required')
        return path

    busy_timeout_ms: int = Field(default=250, ge=1, le=5000)

    @model_validator(mode='after')
    def validate_local(self):
        if self.dev_auth and (self.environment != 'development' or self.host not in ('127.0.0.1','::1','localhost')):
            raise ValueError('Development authentication requires development mode and loopback binding')
        if self.dev_auth and (not self.auth_secret or len(self.auth_secret.encode()) < 32):
            raise ValueError('AUTH_SECRET must contain at least 32 bytes')
        url = make_url(self.database_url)
        if url.drivername != 'sqlite' or not url.database or url.database == ':memory:' or url.query:
            raise ValueError('A dedicated SQLite file is required')
        path = Path(url.database)
        path = (ROOT/path).resolve() if not path.is_absolute() else path.resolve()
        protected_paths = [ROOT/'server/data/workpal.sqlite', Path(os.environ.get('WORKPAL_DB') or ROOT/'server/data/workpal.sqlite')]
        for protected in protected_paths:
            protected = protected.resolve()
            if path == protected or (path.exists() and protected.exists() and os.path.samefile(path, protected)):
                raise ValueError('Mock database is protected')
        self.database_url = 'sqlite:///' + str(path)
        if not self.redis_key_prefix.strip(): raise ValueError('Redis namespace is required')
        return self
