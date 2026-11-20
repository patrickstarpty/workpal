"""Restricted policy management and immutable, normalized evidence snapshots."""
from copy import deepcopy
from workpal.contracts import DomainError
from workpal.access.service import authorize
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from . import environments as env, sources
from .models import Source, EvidencePolicyVersion
from .normalization import _policy
import json, hashlib


def selected(actor, source_id):
    env.integer(source_id)
    env.projects.manage(actor)
    if actor.executor_id is not None:
        raise DomainError('permission_denied', 'Human policy management required.', status=403)
    source=Source.objects.filter(pk=source_id,environment__workspace_id=actor.workspace_id).first()
    if source is None:
        raise DomainError('not_found','Source unavailable.',status=404)
    env.selected(actor,source.environment_id,'write')
    authorize(actor,'read',[sources.source_ref(source.pk)])
    authorize(actor,'publish',[sources.source_ref(source.pk)])
    if source.adapter_type!='http_query':
        raise DomainError('invalid_input','Query source required.')
    return source


def configure_policy(actor, source_id, policy, expected_revision):
    env.integer(source_id)
    env.integer(expected_revision,maximum=MAX_SQLITE_INTEGER-1)
    def write():
        source=selected(actor,source_id)
        copied=deepcopy(policy)
        digest=_digest(_policy(copied))
        if not Source.objects.filter(pk=source.pk,policy_revision=expected_revision).update(policy_revision=expected_revision+1):
            raise DomainError('revision_conflict','Policy changed.',status=409)
        version=EvidencePolicyVersion.objects.create(source=source,revision=expected_revision+1,policy=copied,policy_sha256=digest,creator_id=actor.user_id)
        Source.objects.filter(pk=source.pk).update(current_policy=version)
        return dict(source_id=source.pk,revision=version.revision,policy_sha256=digest)
    return atomic_write(write)


def read_policy(actor, source_id):
    source=selected(actor,source_id)
    result=dict(source_id=source.pk,revision=source.policy_revision,configured=source.current_policy_id is not None,policy_sha256='')
    if source.current_policy_id is not None:
        result.update(policy=deepcopy(source.current_policy.policy),policy_sha256=source.current_policy.policy_sha256)
    return result

def _digest(value):
    try: return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
    except (ValueError,TypeError,UnicodeError): raise DomainError('invalid_input','Invalid JSON.')

def validate(config):
    from urllib.parse import urlsplit
    import re, ipaddress
    def text(v,n):
        return type(v) is str and 1<=len(v)<=n and not any(ord(c)<32 or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in v)
    def require(condition):
        if not condition:
            raise ValueError('Invalid configuration')
    fields={'version','endpoint','method','network_zone','secret_ref','capabilities','parameter_schema','response_mapping','readonly_proof'}
    if type(config) is not dict or set(config)!=fields: raise DomainError('invalid_input','Invalid config.')
    try:
        require(type(config['version']) is int and config['version']==1)
        require(config['method']=='GET' and config['network_zone'] in ('public','private'))
        require(config['capabilities']==['search_logs'] and config['parameter_schema']=='search_logs_v1' and config['response_mapping']=='jsonl_logs_v1')
        require(text(config['secret_ref'],200) and not any(c.isspace() for c in config['secret_ref']))
        url=config['endpoint']; require(text(url,2048) and url.isascii() and not any(c.isspace() for c in url) and not any(c in url for c in '\\%?#'))
        u=urlsplit(url); require(u.scheme=='https' and u.netloc and not u.username and not u.password and u.port in (None,443))
        host=u.hostname; require(host==host.lower() and u.netloc in (host,host+':443'))
        require(len(host)<=253 and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part) for part in host.split('.')))
        try: ipaddress.ip_address(host)
        except ValueError: pass
        else: raise ValueError('IP literal is not allowed')
        require(u.path.startswith('/') and not any(part in ('.','..') for part in u.path.split('/')))
        proof=config['readonly_proof']; require(type(proof) is dict and set(proof)=={'reference','sha256','attestation'})
        require(text(proof['reference'],1000) and text(proof['attestation'],2000) and type(proof['sha256']) is str and re.fullmatch('[0-9a-f]{64}',proof['sha256']))
        _digest(config)
    except (ValueError,TypeError,AttributeError): raise DomainError('invalid_input','Invalid config.') from None

def configure(actor,source_id,config,expected_revision):
    env.integer(expected_revision,maximum=MAX_SQLITE_INTEGER-1)
    def write():
        from .models import SourceQueryVersion
        source=selected(actor,source_id); copied=deepcopy(config); validate(copied)
        if source.current_policy_id is None: raise DomainError('policy_required','Policy required.',status=403)
        digest=_digest(copied)
        if not Source.objects.filter(pk=source.pk,query_revision=expected_revision).update(query_revision=expected_revision+1): raise DomainError('revision_conflict','Configuration changed.',status=409)
        version=SourceQueryVersion.objects.create(source=source,revision=expected_revision+1,config=copied,config_sha256=digest,policy_version_id=source.current_policy_id,creator_id=actor.user_id)
        Source.objects.filter(pk=source.pk).update(current_query_config=version)
        return dict(source_id=source.pk,revision=version.revision,config_sha256=digest)
    return atomic_write(write)

def read_config(actor,source_id):
    source=selected(actor,source_id)
    return dict(source_id=source.pk,revision=source.query_revision,config_sha256=source.current_query_config.config_sha256 if source.current_query_config_id else '',configured=source.current_query_config_id is not None,connected=False)
