import pytest


@pytest.mark.parametrize(('mime','filename','force','expected'), [
    ('image/png','nice"file;.png',False,'inline; filename="nice_file_.png"'),
    ('image/svg+xml; charset=utf-8','logo.svg',False,'attachment; filename="logo.svg"'),
    (' IMAGE/PNG ; charset=utf-8','a.png',False,'inline; filename="a.png"'),
    ('application/pdf','a.pdf',True,'attachment; filename="a.pdf"'),
    ('text/plain','a\r\nb\\c\x00.txt',False,'attachment; filename="a__b_c_.txt"'),
    ('image/png','中"文.png',False,'inline; filename="___.png"; filename*=UTF-8\'\'%E4%B8%AD%22%E6%96%87.png'),
    ('text/plain','a\udcff.txt',False,'attachment; filename="a_.txt"; filename*=UTF-8\'\'a%EF%BF%BD.txt'),
])
def test_media_disposition_and_filename_encoding(mime,filename,force,expected):
    from workpal_backend.files.content_disposition import content_disposition
    assert content_disposition(mime,filename,force_attachment=force)==expected
