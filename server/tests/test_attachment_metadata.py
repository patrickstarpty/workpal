from datetime import datetime, timezone, timedelta
import pytest

A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
BASE=dict(id=A,workspace_id=W,uploader_id=None,uploader_type='member',filename='a.pdf',url='https://cdn.example/a.pdf',content_type='application/pdf',size_bytes=3,created_at=datetime(2026,11,22,12,30,45,999999,tzinfo=timezone(timedelta(hours=8))))
class Storage:
    is_local=False
    def cdn_domain(self):return 'cdn.example'
class Local(Storage):is_local=True
class Signer:
    def __init__(self):self.calls=[]
    def signed_url(self,*args):self.calls.append(args);return 'signed'

def serializer(storage=None,signer=None):
    from workpal_backend.files.metadata import AttachmentMetadata
    return AttachmentMetadata(storage,signer,public_url='https://api.example/',clock_ns=lambda:100*10**9)


def test_attachment_response_null_fields_and_original_timezone():
    response=serializer().response(BASE)
    assert response['created_at']=='2026-11-22T12:30:45+08:00'
    assert response['uploader_id']==''
    assert all(response[key] is None for key in ('issue_id','comment_id','chat_session_id','chat_message_id'))
    assert 'attachment_download_url' not in response and 'width' not in response
    assert response['download_url']==f'/api/attachments/{A}/download'
    assert response['markdown_url']==f'https://api.example/api/attachments/{A}/download'

@pytest.mark.parametrize('field',['issue_id','comment_id','chat_session_id','chat_message_id','task_id'])
def test_local_bound_attachments_use_durable_authenticated_url(field):
    response=serializer(Local()).response(dict(BASE,**{field:W}))
    assert response['url']==response['markdown_url']
    assert serializer(Local()).response(BASE)['url']==BASE['url']
    assert serializer(Local()).response(dict(BASE,source_context_id=W))['url']==BASE['url']


def test_remote_public_url_remains_durable():
    response=serializer(Storage()).response(BASE)
    assert response['markdown_url']==BASE['url'] and response['url']==BASE['url']


def test_stable_lists_skip_signing_but_default_signs():
    signer=Signer();service=serializer(Storage(),signer)
    assert service.response(BASE,stable=True)['download_url']==f'/api/attachments/{A}/download'
    assert signer.calls==[]
    assert service.response(BASE)['download_url']=='signed'
    assert signer.calls==[(BASE['url'],1900)]

@pytest.mark.parametrize(('width','height','included'),[(0,0,True),(10,None,False),(None,10,False),(10,20,True)])
def test_dimensions_require_both_valid_values(width,height,included):
    response=serializer().response(dict(BASE,width=width,height=height))
    assert ('width' in response)==included and ('height' in response)==included


def test_null_timestamp_formats_go_zero_time():
    assert serializer().response(dict(BASE,created_at=None))['created_at']=='0001-01-01T00:00:00Z'


def test_single_metadata_proxy_mints_separate_preview_and_download_capabilities():
    import asyncio
    from workpal_backend.files.metadata import AttachmentMetadata
    from workpal_backend.files.capabilities import AttachmentCapabilities
    caps=AttachmentCapabilities('public-test-fixture')
    service=AttachmentMetadata(Local(),capabilities=caps,clock_ns=lambda:100*10**9)
    response=asyncio.run(service.signed_response(BASE))
    assert response['download_url']==caps.path(A,now_ns=100*10**9)
    assert response['attachment_download_url']==caps.path(A,now_ns=100*10**9,download=True)
    assert 'signed-download' not in service.response(BASE)['download_url']


@pytest.mark.parametrize('failed',[0,1,None])
def test_single_metadata_presign_attempts_are_independent(failed):
    import asyncio
    class Presigner(Storage):
        def __init__(self):self.calls=[]
        def key_from_url(self,url):return 'key'
        def presign_get_with_content_disposition(self,key,ttl,disposition):
            index=len(self.calls);self.calls.append((key,ttl,disposition))
            if index==failed:raise OSError('sign failed')
            return 'signed-'+str(index)
    storage=Presigner();service=serializer(storage)
    response=asyncio.run(service.signed_response(BASE))
    assert storage.calls==[('key',1800*10**9,''),('key',1800*10**9,'attachment; filename="a.pdf"')]
    assert response['download_url']==(f'/api/attachments/{A}/download' if failed==0 else 'signed-0')
    assert response.get('attachment_download_url')==(None if failed==1 else 'signed-1')


def test_explicit_proxy_overrides_configured_cloudfront_for_single_metadata():
    import asyncio
    from workpal_backend.files.metadata import AttachmentMetadata
    from workpal_backend.files.capabilities import AttachmentCapabilities
    caps=AttachmentCapabilities('public-test-fixture');signer=Signer()
    service=AttachmentMetadata(Storage(),signer,mode='proxy',capabilities=caps,clock_ns=lambda:100*10**9)
    response=asyncio.run(service.signed_response(BASE))
    assert len(signer.calls)==1  # Original attachmentToResponse signs before mode dispatch.
    assert response['download_url']==caps.path(A,now_ns=100*10**9)


def test_explicit_cloudfront_without_signer_leaves_stable_url():
    import asyncio
    from workpal_backend.files.metadata import AttachmentMetadata
    response=asyncio.run(AttachmentMetadata(Storage(),mode='cloudfront').signed_response(BASE))
    assert response['download_url']==f'/api/attachments/{A}/download'
    assert 'attachment_download_url' not in response


def test_subminute_negative_offset_uses_go_truncated_minute_sign():
    value=datetime(2026,1,1,tzinfo=timezone(timedelta(seconds=-29)))
    assert serializer().response(dict(BASE,created_at=value))['created_at']=='2026-01-01T00:00:00+00:00'


def test_signed_metadata_keeps_original_struct_field_order():
    import asyncio
    from workpal_backend.files.capabilities import AttachmentCapabilities
    from workpal_backend.files.metadata import AttachmentMetadata
    response=asyncio.run(AttachmentMetadata(mode='proxy',capabilities=AttachmentCapabilities('fixture'),clock_ns=lambda:0).signed_response(BASE))
    keys=list(response)
    assert keys[keys.index('download_url')+1:keys.index('download_url')+3]==['attachment_download_url','markdown_url']
