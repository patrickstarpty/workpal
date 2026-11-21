"""Explicit, confined frontend hosting after all API routes."""
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse


def mount_frontend(app, directory):
    root = Path(directory).resolve()
    index = root / 'index.html'
    if not index.is_file() or not index.resolve().is_relative_to(root):
        raise ValueError('Frontend build missing; run npm run build first')

    @app.api_route('/{frontend_path:path}', methods=['GET', 'HEAD'], include_in_schema=False)
    def frontend(frontend_path: str):
        parts = frontend_path.split('/')
        if parts[0] in {'api', 'auth', 'ws', 'v1', 'plugin-surfaces', 'health', 'healthz', 'readyz'} or '..' in parts or '\\' in frontend_path:
            raise HTTPException(404)
        candidate = (root / frontend_path).resolve()
        if not candidate.is_relative_to(root):
            raise HTTPException(404)
        if candidate.is_file():
            return FileResponse(candidate, headers={'Cache-Control': 'no-cache'} if candidate == index else {})
        if Path(frontend_path).suffix or parts[0] == 'assets':
            raise HTTPException(404)
        return FileResponse(index, headers={'Cache-Control': 'no-cache'})
