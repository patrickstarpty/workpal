from workpal_backend.auth.profile_decode import go_trim_space


def test_origin_policy_same_host_and_proxy_trust_follow_go():
    from workpal_backend.realtime.origins import OriginPolicy
    policy=OriginPolicy(['https://allowed.example'],['127.0.0.0/8','::1/128'])
    for origin in ['', 'https://HOST/path?x=1', '//host', 'wss://host', 'http://user@host']:
        assert policy.allowed(origin,'host','192.0.2.1:1234','')
    assert policy.allowed('https://public.example/path','internal','127.0.0.1:12',' public.example, inner')
    assert not policy.allowed('https://public.example','internal','192.0.2.1:12','public.example')
    assert policy.allowed('https://allowed.example','internal','192.0.2.1:12','')
    assert not policy.allowed('https://host/%bad%','host','127.0.0.1:12','')
    assert not policy.allowed('http://host:bad','host:bad','127.0.0.1:12','')


def test_router_origin_environment_defaults_and_precedence():
    from workpal_backend.realtime.origins import router_origins
    assert router_origins({})==['http://localhost:3000','http://localhost:5173','http://localhost:5174']
    assert router_origins({'ALLOWED_ORIGINS':'https://ignored','FRONTEND_ORIGIN':' https://front '})==['https://front']
    assert router_origins({'CORS_ALLOWED_ORIGINS':' https://one, ,https://two ','FRONTEND_ORIGIN':'https://front'})==['https://one','https://two']
    assert router_origins({'CORS_ALLOWED_ORIGINS':', ,'})==router_origins({})


def test_trusted_proxy_rejects_noncanonical_prefix_lengths():
    from workpal_backend.realtime.origins import OriginPolicy
    for prefix in ['0.0.0.0/00','0.0.0.0/+0','0.0.0.0/255.255.255.0','::/0128']:
        assert not OriginPolicy([], [prefix]).trusted('127.0.0.1:80')
