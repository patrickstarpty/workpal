"""Bounded binary evidence transport; authorization precedes stream access."""
import re
from datetime import datetime
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from django.http import JsonResponse
from workpal.actions.http import error, invalid
from workpal.contracts import Actor, DomainError
from workpal.storage import MAX_SQLITE_INTEGER
from . import evidence, environments


def integer(value, minimum=1, maximum=MAX_SQLITE_INTEGER):
    if not isinstance(value,str) or len(value)>19 or not re.fullmatch(r'0|[1-9][0-9]*',value): invalid()
    number=int(value)
    if not minimum<=number<=maximum: invalid()
    return number


def endpoint(request, investigation_id=None, evidence_id=None):
    try:
        request.get_host()
        upload=request.path.endswith('/evidence-uploads')
        if request.method != ('POST' if upload else 'GET'):
            raise DomainError('method_not_allowed','Method not allowed.',status=405)
        if not request.user.is_authenticated or not request.user.is_active:
            raise DomainError('authentication_required','Login required.',status=403)
        allowed={'workspace_id','source_id','format','timezone','range_start','range_end'} if upload else {'workspace_id'} if evidence_id is not None else {'workspace_id','cursor','limit'}
        if set(request.GET)-allowed or any(len(request.GET.getlist(k))!=1 for k in request.GET): invalid()
        workspace=integer(request.GET.get('workspace_id'))
        for pk in (investigation_id,evidence_id):
            if pk is not None and not 1<=pk<=MAX_SQLITE_INTEGER: invalid()
        actor=Actor(request.user.pk,workspace,executor_id=None,session_id=request.session.session_key)
        if upload:
            if request.content_type!='application/octet-stream': invalid()
            source=integer(request.GET.get('source_id'))
            format=request.GET.get('format')
            if format not in ('text','jsonl'): invalid()
            key=request.headers.get('Idempotency-Key')
            if not key or not key.strip() or len(key)>200: invalid()
            options={k:request.GET.get(k) for k in ('timezone','range_start','range_end')}
            if options['timezone'] is not None: environments.valid_timezone(options['timezone'])
            start,end=options['range_start'],options['range_end']
            if (start is None)!=(end is None): invalid()
            if start is not None:
                try:
                    if len(start)>64 or len(end)>64: invalid()
                    a,b=map(datetime.fromisoformat,(start,end))
                    if a.utcoffset() is None or b.utcoffset() is None or a>=b: invalid()
                except ValueError: invalid()
            length=request.META.get('CONTENT_LENGTH','')
            if length:
                if len(length)>19 or not re.fullmatch(r'0|[1-9][0-9]*',length): invalid()
                if int(length)>2097152: raise RequestDataTooBig()
            evidence.authorize_upload(actor,investigation_id,source)
            content=bytearray()
            while True:
                chunk=request.read(min(65536,2097153-len(content)))
                if not chunk: break
                content.extend(chunk)
                if len(content)>2097152: raise RequestDataTooBig()
            if length and len(content)!=int(length): invalid()
            data=evidence.submit_upload(actor,investigation_id,source,bytes(content),format=format,key=key,**options)
        elif evidence_id is not None:
            data=evidence.read_evidence(actor,evidence_id)
        else:
            data=evidence.list_evidence(actor,investigation_id,integer(request.GET.get('cursor','0'),0),integer(request.GET.get('limit','50'),1,200))
        response=JsonResponse(data)
    except DomainError as exc:
        response=error(DomainError(exc.code,'Unable to complete evidence request.',request_id=exc.request_id,retryable=exc.retryable,status=exc.status))
    except DisallowedHost: response=error(DomainError('invalid_host','Invalid host.'))
    except RequestDataTooBig: response=error(DomainError('input_too_large','Request is too large.',status=413))
    except Exception: response=error(DomainError('internal_error','Unable to complete action.',status=500))
    response['Cache-Control']='no-store'
    response['X-Content-Type-Options']='nosniff'
    return response
