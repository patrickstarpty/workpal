"""Go Auth middleware uses http.Error, unlike handler JSON errors."""
import json
from fastapi import HTTPException
from starlette.responses import Response


class AuthenticationError(HTTPException):
    pass


async def authentication_error(request, exc):
    return Response(json.dumps({'error':exc.detail},separators=(',',':'))+'\n',
        status_code=exc.status_code,media_type='text/plain',
        headers={'X-Content-Type-Options':'nosniff'})
