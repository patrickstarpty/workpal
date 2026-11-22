import pytest

@pytest.mark.parametrize(('target','location'),[
    ('https://cdn.example/x?a=1&b=2','https://cdn.example/x?a=1&b=2'),
    ('../files/a','/api/files/a'),
    ('/a//b/../c/','/a/c/'),
    ('//cdn.example/a','//cdn.example/a'),
    ('///a//b','/a/b'),
    ('?q=1','/api/attachments/?q=1'),
    ('/工作区/文件','/%e5%b7%a5%e4%bd%9c%e5%8c%ba/%e6%96%87%e4%bb%b6'),
    ('/bad%escape/../x','/bad%escape/../x'),
])
def test_download_redirect_go_location(target,location):
    from workpal_backend.files.redirect import download_redirect
    response=download_redirect(target,request_path='/api/attachments/id')
    assert response.status_code==302
    assert response.headers['location']==location
    assert response.headers['content-type']=='text/html; charset=utf-8'


def test_redirect_html_escaping_and_double_newline():
    from workpal_backend.files.redirect import download_redirect
    response=download_redirect('https://cdn.example/a?x="<&\'')
    assert response.body==b'<a href="https://cdn.example/a?x=&#34;&lt;&amp;&#39;">Found</a>.\n\n'

@pytest.mark.parametrize('method',['HEAD','POST','PUT'])
def test_non_get_has_no_redirect_body(method):
    from workpal_backend.files.redirect import download_redirect
    response=download_redirect('/x',method=method)
    assert response.body==b''
    assert ('content-type' in response.headers)==(method=='HEAD')


def test_existing_content_type_prevents_generated_html():
    from workpal_backend.files.redirect import download_redirect
    response=download_redirect('/x',headers={'Content-Type':'custom','X-Content-Type-Options':'nosniff'})
    assert response.body==b''
    assert response.headers['content-type']=='custom'
    assert response.headers['x-content-type-options']=='nosniff'
