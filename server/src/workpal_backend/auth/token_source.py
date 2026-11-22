"""Token-source precedence from middleware/auth.go extractToken."""
from workpal_backend.realtime.request_values import first_cookie


def extract_token(request):
    authorization = request.headers.get('authorization', '')
    if authorization.startswith('Bearer '):
        return authorization[7:], False
    cookie = first_cookie(request.headers.getlist('cookie'), 'workpal_auth')
    if cookie:
        return cookie, True
    return '', False
