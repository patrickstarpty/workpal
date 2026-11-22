from pathlib import Path
import pytest

KEY=(Path(__file__).parent/'fixtures/cloudfront-test-key.pem').read_bytes()


@pytest.mark.parametrize('variant',['normal','label','header','preamble','duplicate_begin','invalid_before_valid'])
def test_rsa_parser_uses_first_valid_pem_block_bytes_independent_of_label(variant):
    from workpal_backend.auth.rsa_keys import parse_rsa_private_key
    raw=KEY
    if variant=='label':raw=raw.replace(b'PRIVATE KEY',b'UNRELATED LABEL')
    if variant=='header':raw=raw.replace(b'-----BEGIN PRIVATE KEY-----\n',b'-----BEGIN PRIVATE KEY-----\nNote: test fixture\n\n')
    if variant=='preamble':raw=b'ignore prefix\n'+raw+b'ignored suffix'
    if variant=='duplicate_begin':raw=b'-----BEGIN PRIVATE KEY-----\n'+raw
    if variant=='invalid_before_valid':raw=b'-----BEGIN BAD-----\ninvalid!!\n-----END BAD-----\n'+raw
    assert parse_rsa_private_key(raw).private_numbers()==parse_rsa_private_key(KEY).private_numbers()


@pytest.mark.parametrize('raw',[b'',b'garbage',b'-----BEGIN KEY-----\nAAAA\n-----END KEY-----',KEY.replace(b'-----END PRIVATE KEY-----',b'-----END MISMATCH-----')])
def test_invalid_key_is_rejected(raw):
    from workpal_backend.auth.rsa_keys import parse_rsa_private_key
    with pytest.raises(ValueError):parse_rsa_private_key(raw)
