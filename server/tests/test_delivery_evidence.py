from test_workspace_content import content, seed


def setup_issue(content):
    app, client, headers, workspace = content
    seed(app, workspace, 'issues', [{'id':'ticket', 'title':'Recovery', 'status':'done'}])
    return client, headers


def document(**changes):
    return dict(kind='design', title='Recovery design', content='Full interaction specification with states and retry boundaries.', **changes)


def test_versions_and_authenticated_review(content):
    client, headers = setup_issue(content)
    path = '/api/issues/ticket/evidence'
    first = client.post(path, headers=headers, json=document())
    assert first.status_code == 200, first.text
    first = first.json()
    second = client.post(path, headers=headers, json=document(previous_id=first['id'])).json()
    assert second['version'] == 2
    assert second['content'] == first['content']
    review = client.post(path, headers=headers, json={'review_of':first['id'], 'decision':'accepted', 'scope':'Interaction specification', 'remaining':'Implementation and tests remain', 'reviewer_id':'forged'})
    assert review.status_code == 200, review.text
    assert review.json()['reviewer_id'] != 'forged'
    data = client.get(path, headers=headers).json()
    assert len(data['revisions']) == 2
    assert data['reviews'][0]['review_of'] == first['id']
    timeline = client.get('/api/issues/ticket/timeline', headers=headers).json()
    assert any(row['id'] == first['activity_id'] for row in timeline)
    assert client.get('/api/attachments/'+first['attachment_id']+'/content', headers=headers).text == first['content']


def test_missing_evidence_and_invalid_links(content):
    client, headers = setup_issue(content)
    path='/api/issues/ticket/evidence'
    assert client.get(path, headers=headers).json()['status'] == 'evidence_pending'
    assert client.post(path, headers=headers, json={'kind':'test', 'title':'Tests', 'content':'Passed'}).status_code == 400
    assert client.post(path, headers=headers, json=document(run_id='missing')).status_code == 400
    app, _, _, workspace=content
    seed(app, workspace, 'task_runs', [{'id':'fake','issue_id':'ticket','_fixture':{'execution':'synthetic'}}])
    assert client.post(path, headers=headers, json=document(run_id='fake')).status_code == 400
    assert client.post(path, headers=headers, json=document(previous_id='missing')).status_code == 400
    assert client.post(path, headers=headers, json={'review_of':'missing','decision':'accepted','scope':'All','remaining':'None'}).status_code == 400


def test_revision_conflict_cross_ticket_and_preserved_history(content):
    client, headers = setup_issue(content)
    app, _, _, workspace = content
    seed(app, workspace, 'issues', [{'id':'other', 'title':'Other'}])
    seed(app, workspace, 'comments', [{'id':'old', 'issue_id':'ticket', 'content':'Tests passed', '_fixture':{'execution':'synthetic'}}])
    path='/api/issues/ticket/evidence'
    first=client.post(path, headers=headers, json=document()).json()
    assert client.post('/api/issues/other/evidence', headers=headers, json=document(previous_id=first['id'])).status_code == 400
    assert client.post(path, headers=headers, json=document(previous_id=first['id'])).status_code == 200
    assert client.post(path, headers=headers, json=document(previous_id=first['id'])).status_code == 409
    assert client.patch(path, headers=headers, json={'content':'overwrite'}).status_code == 501
    rows=client.get('/api/issues/ticket/timeline', headers=headers).json()
    assert not any(r['id'] == 'old' for r in rows)
    from workpal_backend.workspace_content.repository import get_record
    with app.state.database.transaction() as session:
        assert get_record(session, workspace['id'], 'comments', 'old')['content']=='Tests passed'
    foreign=headers | {'X-Workspace-Slug':'not-a-member'}
    assert client.get(path, headers=foreign).status_code == 404
    assert client.post(path, headers=foreign, json=document()).status_code == 404


def test_complete_test_report_and_handoff(content):
    client, headers=setup_issue(content)
    path='/api/issues/ticket/evidence'
    report={'kind':'test','title':'Recovery regression','content':'Case R1: interrupted request',
            'method':'Manual interruption of a local request','results':'Not run','failures':'Unknown until executed','uncovered':'All runtime behavior'}
    created=client.post(path, headers=headers, json=report)
    assert created.status_code == 200, created.text
    assert client.get(path, headers=headers).json()['status']=='review_required'
    handoff={'kind':'handoff','title':'Recovery handoff','content':'Review request','scope':'Local behavior','remaining':'Execute tests'}
    assert client.post(path, headers=headers, json=handoff).status_code == 400
    handoff['input_ids']=[created.json()['id']]
    assert client.post(path, headers=headers, json=handoff).status_code == 200


def test_malformed_kind_is_rejected(content):
    client, headers=setup_issue(content)
    for kind in ([], {}, None, 12):
        assert client.post('/api/issues/ticket/evidence', headers=headers, json={'kind':kind}).status_code==400


def test_code_evidence_is_linked_to_real_run_and_activity(content):
    client, headers=setup_issue(content)
    app, _, _, workspace=content
    seed(app, workspace, 'task_runs', [{'id':'real-run','issue_id':'ticket','status':'completed'}])
    payload={'kind':'code','title':'Retry change','content':'Actual patch review', 'run_id':'real-run',
             'diff':'--- old\n+++ new\n-retry()\n+retryOnce()', 'findings':'Duplicate retries',
             'fixes':'Bound retries to one','recheck':'Not executed; review remains open'}
    response=client.post('/api/issues/ticket/evidence', headers=headers, json=payload)
    assert response.status_code==200, response.text
    data=response.json()
    timeline=client.get('/api/issues/ticket/timeline', headers=headers).json()
    comment=next(r for r in timeline if r['id']==data['activity_id'])
    assert comment['source_task_id']=='real-run'
    assert comment['attachments'][0]['authenticated_download'] is True
    assert client.get('/api/issues/ticket/evidence', headers=headers).json()['runs']['real-run']['id']=='real-run'
    assert client.get('/api/attachments/'+data['id']+'/download',headers=headers).text==data['content']


def test_later_evidence_does_not_restore_fabricated_history(content):
    client, headers=setup_issue(content)
    app, _, _, workspace=content
    seed(app, workspace, 'comments', [{'id':'claim','issue_id':'ticket','content':'Design accepted', 'source_task_id':'old-run','_fixture':{'execution':'synthetic'}}])
    seed(app, workspace, 'evidence_imports', [{'id':'later','issue_id':'ticket','activity_id':'new-audit'}])
    assert client.get('/api/issues/ticket/timeline',headers=headers).json() == []


def test_fixture_execution_is_unavailable_but_real_actions_persist(content):
    client, headers = setup_issue(content)
    app, _, _, workspace = content
    for kind in ('task_runs', 'activities', 'attachments'):
        seed(app, workspace, kind, [{'id':'fake', 'issue_id':'ticket', '_fixture':{'execution':'synthetic'}}])
    for suffix in ('task-runs', 'runs', 'tasks', 'activity', 'attachments'):
        assert client.get('/api/issues/ticket/' + suffix, headers=headers).json() == []
    assert client.get('/api/tasks/fake/messages', headers=headers).status_code == 404
    assert client.get('/api/attachments/fake/content', headers=headers).status_code == 404
    comment = client.post('/api/issues/ticket/comments', headers=headers, json={'content':'Actual note'}).json()
    assert client.patch('/api/issues/ticket', headers=headers, json={'status':'todo'}).status_code == 200
    timeline = client.get('/api/issues/ticket/timeline', headers=headers).json()
    assert any(r['id'] == comment['id'] and r['content'] == 'Actual note' for r in timeline)
    event = next(r for r in timeline if r.get('action') == 'status_changed')
    assert event['details'] == {'from':'done', 'to':'todo'}
    assert event['actor_id'] == comment['author_id']
    assert client.patch('/api/issues/ticket', headers=headers, json={'status':'todo'}).status_code == 200
    assert client.get('/api/issues/ticket/timeline', headers=headers).json() == timeline
