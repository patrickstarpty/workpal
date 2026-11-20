from pathlib import Path
from django.http import HttpResponse, Http404, HttpResponseNotAllowed

ROOT = Path(__file__).resolve().parents[3]
ASSETS = {name: (ROOT / 'apps/workpal-web' / path, mime) for name, path, mime in (
    ('app.js', 'src/app.js', 'text/javascript'),
    ('client.js', 'src/client.js', 'text/javascript'),
    ('ui.js', 'src/ui.js', 'text/javascript'),
    ('features/workspace.js', 'src/features/workspace.js', 'text/javascript'),
    ('features/projects.js', 'src/features/projects.js', 'text/javascript'),
    ('features/issue-create.js', 'src/features/issue-create.js', 'text/javascript'),
    ('features/requirements-form.js', 'src/features/requirements-form.js', 'text/javascript'),
    ('features/issue-edit.js', 'src/features/issue-edit.js', 'text/javascript'),
    ('features/issue-archive.js', 'src/features/issue-archive.js', 'text/javascript'),
    ('features/people.js', 'src/features/people.js', 'text/javascript'),
    ('features/issue-parent.js', 'src/features/issue-parent.js', 'text/javascript'),
    ('features/issue-hierarchy.js', 'src/features/issue-hierarchy.js', 'text/javascript'),
    ('features/issue-dependencies.js', 'src/features/issue-dependencies.js', 'text/javascript'),
    ('features/issue-transition.js', 'src/features/issue-transition.js', 'text/javascript'),
    ('features/issue-assignee.js', 'src/features/issue-assignee.js', 'text/javascript'),
    ('features/issue-status-history.js', 'src/features/issue-status-history.js', 'text/javascript'),
    ('features/issues.js', 'src/features/issues.js', 'text/javascript'),
    ('styles.css', 'src/styles.css', 'text/css'),
)}
ASSETS.update({'inter.woff2': (ROOT / 'assets/fonts/inter-latin.woff2', 'font/woff2'),
               'mark.svg': (ROOT / 'assets/brand/workpal-mark.svg', 'image/svg+xml')})

def page(request, asset=None):
    request.get_host()
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    target = (ROOT / 'apps/workpal-web/index.html', 'text/html') if asset is None else ASSETS.get(asset)
    if not target or not target[0].is_file():
        raise Http404
    response = HttpResponse(target[0].read_bytes() if request.method == 'GET' else b'', content_type=target[1])
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'"
    return response
