import pytest
from urllib.parse import urlsplit, parse_qs


def test_capabilities_bind_attachment_expiry_and_download_intent():
    from workpal_backend.files.capabilities import AttachmentCapabilities
    signer=AttachmentCapabilities('fixture-secret')
    now=1_000_000_000_999_999_999
    load=signer.path('attachment',now_ns=now)
    download=signer.path('attachment',now_ns=now,download=True)
    load_values=parse_qs(urlsplit(load).query);download_values=parse_qs(urlsplit(download).query)
    assert load.startswith('/api/attachments/attachment/signed-download?exp=1000000060&sig=')
    assert download.endswith('&dl=1')
    signature=load_values['sig'][0]
    assert signature!=download_values['sig'][0]
    assert signer.verify('attachment','1000000060',signature,now_ns=now)
    assert not signer.verify('other','1000000060',signature,now_ns=now)
    assert not signer.verify('attachment','1000000061',signature,now_ns=now)
    assert not signer.verify('attachment','1000000060',signature,intent='attachment',now_ns=now)
    assert signer.verify('attachment','+01000000060',signature.upper(),now_ns=now)
    assert signer.verify('attachment','1000000060',signature,now_ns=1_000_000_060_999_999_999)
    assert not signer.verify('attachment','1000000060',signature,now_ns=1_000_000_061_000_000_000)
    assert not signer.verify('attachment','1000000060',signature[:2]+' '+signature[2:],now_ns=now)


@pytest.mark.parametrize('raw',['',' 60','60 ','６０','9223372036854775808','1_000'])
def test_capability_expiry_uses_go_int64_parser(raw):
    from workpal_backend.files.capabilities import AttachmentCapabilities
    signer=AttachmentCapabilities('fixture-secret')
    assert not signer.verify('attachment',raw,signer.sign('attachment',60),now_ns=0)
