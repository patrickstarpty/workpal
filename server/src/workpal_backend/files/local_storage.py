"""Canonical Go local storage layout, separate from the legacy opaque blob store.

Callers supply an explicit root. This adapter is not wired to the live app until
canonical attachment authorization and data migration gates are satisfied.
"""
import errno
import io
import json
import logging
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit
from .avatar_urls import LocalObjectURLs
logger=logging.getLogger(__name__)


def remove(path):
    try:os.remove(path)
    except FileNotFoundError:pass
    except OSError as exc:
        if exc.errno in (errno.EISDIR,errno.EPERM):os.rmdir(path)
        else:raise


class LocalStorage(LocalObjectURLs):
    def __init__(self,root,base_url=''):
        super().__init__(base_url)
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o755)

    def file_path(self,key):
        # filepath.Join on the frozen POSIX Go build joins a slash-prefixed
        # later component under the existing prefix, then cleans the result.
        return Path(os.path.normpath(str(self.root)+'/'+key))

    @staticmethod
    def temp_path(destination):return destination.with_name('.'+destination.name+'.tmp')

    def cdn_domain(self):
        try:
            parsed=urlsplit(self.base_url)
            parsed.port  # Validate malformed ports like net/url.Parse.
            host=parsed.netloc.rsplit('@',1)[-1]
            if '%' in host:return ''
            return host[1:host.index(']')] if host.startswith('[') else host.split(':',1)[0]
        except ValueError:return ''

    def get_reader(self,key):
        if not key:raise OSError('local GetReader: empty key')
        base=Path(os.path.normpath(key)).name
        if key.endswith('.meta.json') or (base.startswith('.') and base.endswith('.tmp')):
            raise OSError('local GetReader: refusing to serve internal key')
        target=self.file_path(key)
        relative=os.path.relpath(target,os.path.normpath(self.root))
        if relative=='..' or relative.startswith('../'):raise OSError('local GetReader: key escapes upload dir')
        return target.open('rb')

    def upload(self,key,data,content_type='',filename=''):
        return self.upload_stream(key,io.BytesIO(data),len(data),content_type,filename)

    def upload_stream(self,key,reader,size,content_type='',filename=''):
        destination=self.file_path(key)
        destination.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        temporary=self.temp_path(destination)
        stream=os.fdopen(os.open(temporary,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o644),'wb')
        try:
            shutil.copyfileobj(reader,stream)
            stream.close()
            stream=None
            os.replace(temporary,destination)
        except BaseException:
            if stream is not None:
                try:stream.close()
                except OSError:pass
            try:remove(temporary)
            except OSError:pass
            raise
        if filename:
            try:
                # Preserve Go's legacy JSON tags and compact HTML-escaped encoding.
                raw=json.dumps(dict(filename=filename,content_type=content_type),ensure_ascii=False,separators=(',',':'))
                raw=raw.replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
                with os.fdopen(os.open(str(destination)+'.meta.json',os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o644),'w') as sidecar:sidecar.write(raw)
            except OSError:logger.error('Local storage sidecar write failed')
        return self.object_url(key)

    def upload_from_reader(self,key,reader,content_type='',filename=''):
        chunks=[]
        while True:
            part=reader.read(65536)
            if not part:break
            chunks.append(part)
        return self.upload(key,b''.join(chunks),content_type,filename)

    def delete_object(self,key):
        if not key:return
        destination=self.file_path(key)
        for path in (destination,Path(str(destination)+'.meta.json'),self.temp_path(destination)):remove(path)

    def delete(self,key):
        try:self.delete_object(key)
        except OSError:logger.error('Local storage delete failed')

    def delete_keys(self,keys):
        for key in keys:self.delete(key)
