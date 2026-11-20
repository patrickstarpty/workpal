import os
from django.core.exceptions import ImproperlyConfigured
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
WORKPAL_ENV = os.environ.get("WORKPAL_ENV", "development")
if WORKPAL_ENV not in ("development", "production"):
    raise ImproperlyConfigured("Invalid WORKPAL_ENV")
DEVELOPMENT_SECRET = "local-development-only-change-for-deployment"
SECRET_KEY = os.environ.get("WORKPAL_SECRET_KEY", DEVELOPMENT_SECRET)
if WORKPAL_ENV == "production" and (len(SECRET_KEY) < 50 or SECRET_KEY == DEVELOPMENT_SECRET or not os.environ.get("WORKPAL_ALLOWED_HOSTS", "").strip()):
    raise ImproperlyConfigured("Production requires a strong secret and explicit hosts")
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"] if WORKPAL_ENV == "development" else [h.strip() for h in os.environ["WORKPAL_ALLOWED_HOSTS"].split(",") if h.strip()]
if WORKPAL_ENV == "production" and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Production requires explicit hosts")
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "workpal.identity.apps.IdentityConfig", "workpal.access.apps.AccessConfig", "workpal.actions.apps.ActionsConfig", "workpal.audit.apps.AuditConfig"]
MIDDLEWARE = ["workpal.http.private_api_responses", "django.middleware.security.SecurityMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ.get("WORKPAL_DB_PATH", BASE_DIR / "data/workpal.sqlite3"), "OPTIONS": {"timeout": 5, "transaction_mode": "IMMEDIATE"}, "TEST": {"NAME": None}}}
ROOT_URLCONF = "config.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = WORKPAL_ENV == "production"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_FAILURE_VIEW = "workpal.identity.actions.csrf_failure"
USE_TZ = True

TEST_RUNNER = "tests.runner.FileDatabaseRunner"
SECURE_SSL_REDIRECT = WORKPAL_ENV == "production"
SECURE_HSTS_SECONDS = 31536000 if WORKPAL_ENV == "production" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = WORKPAL_ENV == "production"
SECURE_CONTENT_TYPE_NOSNIFF = True
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation." + name} for name in ("UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator")]

INSTALLED_APPS += ['workpal.work.apps.WorkConfig']

INSTALLED_APPS += ['workpal.workflows.apps.WorkflowsConfig']

INSTALLED_APPS += ['workpal.collaboration.apps.CollaborationConfig']

INSTALLED_APPS += ["workpal.delivery.apps.DeliveryConfig"]

INSTALLED_APPS += ["workpal.agents.apps.AgentsConfig", "workpal.execution.apps.ExecutionConfig", "workpal.investigation.apps.InvestigationConfig"]
