from types import SimpleNamespace
import pytest


@pytest.mark.parametrize(('url','expected'), [
    ('https://cdn.test/file',True),('HTTPS://cdn.test/file',True),
    ('/uploads/file',False),('https:///file',False),
    ('https://cdn.test/file?Signature=signed',False),
    ('https://cdn.test/file?Signature=&Signature=signed',True),
    ('https://cdn.test/file?signature=signed',True),
    ('https://cdn.test/file?X-Amz-Expires=1',False),
    ('https://cdn.test/file?Signature=%zz',True),
    ('https://cdn.test/%zz',False),
])
def test_durable_storage_url_rules(url,expected):
    from workpal_backend.files.attachment_urls import durable_public_url
    assert durable_public_url(url)==expected


@pytest.mark.parametrize(('storage','signer','expected'), [
    (None,None,False),
    (SimpleNamespace(is_local=True,cdn_domain=lambda:'cdn.test'),None,False),
    (SimpleNamespace(is_local=False,cdn_domain=lambda:''),None,False),
    (SimpleNamespace(is_local=False,cdn_domain=lambda:'cdn.test'),object(),False),
    (SimpleNamespace(is_local=False,cdn_domain=lambda:'cdn.test'),None,True),
])
def test_public_storage_requires_actual_public_deployment(storage,signer,expected):
    from workpal_backend.files.attachment_urls import AttachmentURLs
    urls=AttachmentURLs(storage,signer,public_url='https://app.test///')
    assert urls.publicly_readable('https://cdn.test/file')==expected
    assert urls.markdown_url('a','https://cdn.test/file')==('https://cdn.test/file' if expected else 'https://app.test/api/attachments/a/download')


def test_mode_and_client_capability_are_distinct():
    from workpal_backend.files.attachment_urls import normalize_download_mode,stable_urls_requested,download_ttl
    assert normalize_download_mode(' \u0085PRESIGN\u00a0')==('presign',True)
    assert normalize_download_mode('invalid')==('auto',False)
    assert stable_urls_requested('other, \u0085stable_attachment_urls\u00a0')
    assert not stable_urls_requested('STABLE_ATTACHMENT_URLS')
    assert download_ttl(0)==1800*10**9
    assert download_ttl(-1)==1800*10**9
    assert download_ttl(1)==1


@pytest.mark.parametrize(('url','expected'),[
    ('/uploads/a',True),('https://localhost/a',True),('https://minio/a',True),
    ('https://a.internal/a',True),('https://127.0.0.1/a',True),
    ('https://10.0.0.1/a',True),('https://169.254.2.3/a',True),
    ('https://224.0.0.9/a',True),('https://192.0.2.1/a',False),
    ('https://203.0.113.1/a',False),('https://8.8.8.8/a',False),
    ('https://[2001:4860:4860::8888]/a',True),
    ('https://public.example./a',False),
])
def test_auto_proxy_host_policy(url,expected):
    from workpal_backend.files.attachment_urls import should_proxy_url
    assert should_proxy_url(url)==expected


def test_resolved_mode_precedence():
    from workpal_backend.files.attachment_urls import resolve_download_mode
    assert resolve_download_mode('proxy','https://public.example',signer=True,presigner=True)=='proxy'
    assert resolve_download_mode('auto','http://localhost',signer=True,presigner=True)=='cloudfront'
    assert resolve_download_mode('auto','http://localhost',presigner=True)=='proxy'
    assert resolve_download_mode('auto','https://public.example',presigner=True)=='presign'
    assert resolve_download_mode('invalid','https://public.example')=='proxy'


@pytest.mark.parametrize('host',['[::ffff:0.0.0.0]','[::%25foo.bar]'])
def test_unspecified_check_preserves_netip_address_identity(host):
    from workpal_backend.files.attachment_urls import should_proxy_url
    assert not should_proxy_url('https://'+host+'/a')
