import base64
from test_workspace_content import content, seed


def test_binary_document_download_is_database_backed_and_scoped(content):
    app, client, headers, workspace = content
    data = b'PK\x03\x04document-bytes'
    seed(app, workspace, 'issues', [{'id':'ticket'}])
    seed(app, workspace, 'attachments', [{'id':'doc', 'issue_id':'ticket', 'filename':'TDS.docx',
        'content_type':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}])
    seed(app, workspace, 'attachment_contents', [{'id':'doc', 'encoding':'base64', 'data':base64.b64encode(data).decode()}])
    for suffix in ('content', 'download'):
        response=client.get('/api/attachments/doc/'+suffix, headers=headers)
        assert response.status_code == 200
        assert response.content == data
        assert response.headers['content-disposition'].startswith('attachment;')
        assert response.headers['x-content-type-options'] == 'nosniff'
    assert client.get('/api/attachments/doc/content',headers=headers | {'X-Workspace-Slug':'foreign'}).status_code == 404


def test_import_restores_documents_without_restoring_execution_claims(content, tmp_path):
    from workpal_backend.workspace_content.document_import import import_documents
    from workpal_backend.workspace_content import repository as repo
    app, client, headers, workspace = content
    seed(app, workspace, 'issues', [{'id':'ticket','status':'done'}])
    seed(app, workspace, 'comments', [{'id':'old','issue_id':'ticket','content':'Agent executed and approved', '_fixture':{'execution':'synthetic'}}])
    seed(app, workspace, 'attachments', [{'id':'doc','issue_id':'ticket','comment_id':'old','source_task_id':'fake-run',
        'filename':'TDS.docx','url':'/delivery/TDS.docx','_fixture':{'execution':'none'}}])
    (tmp_path/'delivery').mkdir()
    data=b'PK\x03\x04test-document'
    (tmp_path/'delivery/TDS.docx').write_bytes(data)
    with app.state.database.transaction() as session:
        assert import_documents(session,workspace['id'],'importer',tmp_path)==1
        assert import_documents(session,workspace['id'],'importer',tmp_path)==0
        assert repo.get_record(session,workspace['id'],'archived_attachments','doc')['_fixture']
    (tmp_path/'delivery/TDS.docx').unlink()
    timeline=client.get('/api/issues/ticket/timeline',headers=headers).json()
    assert len(timeline)==1
    assert timeline[0]['content']=='Document imported · TDS.docx'
    assert timeline[0]['author_type']=='member'
    assert not timeline[0].get('source_task_id')
    assert timeline[0]['attachments'][0]['authenticated_download'] is True
    assert client.get('/api/attachments/doc/download',headers=headers).content==data
    assert client.get('/api/issues/ticket',headers=headers).json()['status']=='done'
