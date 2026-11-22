import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from workpal_backend.infrastructure.database import Database, migrate

@pytest.fixture
def conn(settings):
    migrate(settings)
    db = Database(settings)
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO workspaces(id,name,slug,issue_prefix,created_at,updated_at) VALUES ('w','W','w','W','t','t')"))
        yield c
    db.close()

def insert(c, **changes):
    row = dict(id='s', workspace_id='w', key='custom', name='Custom', category='started', color='#abcdef', created_at='t', updated_at='t')
    row.update(changes)
    c.execute(text(f"INSERT INTO issue_status ({','.join(row)}) VALUES ({','.join(':'+k for k in row)})"), row)

INVALID = [('key',v) for v in ['', '_a','A','a!','a'*33,'a\0!']] + [('name',v) for v in ['', 'a'*65,'A\0B']] + [('description',v) for v in ['a'*257,'a\0b']] + [('color',v) for v in ['#ABCDEF','#12345g','#1234567','#abcdef\0!']] + [('category','todo'),('is_system',2),('icon','a\0b'),('created_at','t\0x'),('updated_at','t\0x'),('archived_at','t\0x'),('id','s\0x')]

@pytest.mark.parametrize('field,value', INVALID)
@pytest.mark.parametrize('operation',['insert','update'])
def test_invalid_text_and_contract(conn,field,value,operation):
    if operation == 'update':
        insert(conn)
    with pytest.raises(IntegrityError):
        if operation == 'insert':
            insert(conn, **{field:value})
        else:
            conn.execute(text(f'UPDATE issue_status SET {field}=:value WHERE id=\'s\''),dict(value=value))

PAIRS = [('backlog','unstarted'),('todo','unstarted'),('in_progress','started'),('in_review','started'),('blocked','started'),('done','done'),('cancelled','closed')]

@pytest.mark.parametrize('key,category', PAIRS)
@pytest.mark.parametrize('operation',['insert','update'])
def test_system_pairs(conn,key,category,operation):
    insert(conn,key=key,category=category,is_system=1)
    if operation == 'update':
        with pytest.raises(IntegrityError):
            conn.execute(text("UPDATE issue_status SET category=:c"), {'c':'closed' if category != 'closed' else 'done'})
        with pytest.raises(IntegrityError):
            conn.execute(text("UPDATE issue_status SET archived_at='t'"))
    else:
        with pytest.raises(IntegrityError):
            insert(conn,id='bad',key=key+'x',name='Other',category=category,is_system=1)
        with pytest.raises(IntegrityError):
            insert(conn,id='bad',key=key,name='Other',category=category,is_system=1,archived_at='t')

@pytest.mark.parametrize('operation',['insert','update'])
@pytest.mark.parametrize('field,value',[('key','custom'),('name','CUSTOM')])
def test_uniqueness(conn,operation,field,value):
    insert(conn)
    if operation == 'update':
        insert(conn,id='other',key='other',name='Other')
    with pytest.raises(IntegrityError):
        if operation == 'insert':
            insert(conn,**dict(dict(id='other',key='other',name='Other'),**{field:value}))
        else:
            conn.execute(text(f"UPDATE issue_status SET {field}=:v WHERE id='other'"),{'v':value})

def test_archive_reuse_and_defaults(conn):
    insert(conn,archived_at='t',position=1.25)
    insert(conn,id='other',key='other',name='CUSTOM')
    with pytest.raises(IntegrityError):
        conn.execute(text("UPDATE issue_status SET archived_at=NULL WHERE id='s'"))
    with pytest.raises(IntegrityError):
        insert(conn,id='third',name='Third')
    rows=conn.execute(text('SELECT description,icon,is_system,position FROM issue_status ORDER BY id')).all()
    assert rows == [('', '', 0, 0.0), ('', '', 0, 1.25)]

def test_boundaries_and_workspace_isolation(conn):
    insert(conn,key='a'*32,name='A'*64,description='文'*256)
    conn.execute(text("INSERT INTO workspaces(id,name,slug,issue_prefix,created_at,updated_at) VALUES ('w2','W2','w2','W','t','t')"))
    insert(conn,id='other',workspace_id='w2',key='a'*32,name='a'*64)
    conn.execute(text("UPDATE issue_status SET key='0',name='文',description='',position=-0.125 WHERE id='s'"))
    assert conn.execute(text("SELECT position FROM issue_status WHERE id='s'")).scalar_one() == -0.125

def test_production_service_seeds_seven(conn):
    from sqlalchemy.orm import Session
    from workpal_backend.workspaces.service import create_workspace
    conn.execute(text("INSERT INTO users(id,email,name,created_at,updated_at) VALUES ('u','u@example.com','U','t','t')"))
    with Session(bind=conn) as session:
        workspace=create_workspace(session,'u','Service','service')
        rows=session.execute(text('SELECT key,category,is_system,icon FROM issue_status WHERE workspace_id=:w'),{'w':workspace['id']}).all()
        assert sorted(rows) == sorted((k,c,1,'') for k,c in PAIRS)
