from config.settings import *
INSTALLED_APPS = list(INSTALLED_APPS)
for app in ['workpal.investigation.apps.InvestigationConfig']:
    if app not in INSTALLED_APPS:
        INSTALLED_APPS.append(app)
