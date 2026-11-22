"""SQLite value checks for canonical PostgreSQL JSONB and array columns."""
from decimal import Decimal
import json
from .go_uuid import parse_uuid


def _valid_text(value):
    if '\0' in value:
        return False
    try:
        value.encode('utf-8')
        return True
    except UnicodeError:
        return False


def jsonb_valid(raw):
    try:
        obj=json.loads(raw, parse_float=Decimal, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        def valid(value):
            if isinstance(value,str):return _valid_text(value)
            if isinstance(value,list):return all(valid(v) for v in value)
            if isinstance(value,dict):return all(_valid_text(k) and valid(v) for k,v in value.items())
            return True
        return int(valid(obj))
    except (ValueError,TypeError,RecursionError):
        return 0


def array_valid(raw,kind):
    try:
        obj=json.loads(raw)
        def shape(value):
            if not isinstance(value,list):
                if value is not None:
                    if not isinstance(value,str) or not _valid_text(value):raise ValueError()
                    if kind=='uuid':parse_uuid(value)
                return ()
            shapes=[shape(v) for v in value]
            if shapes and any(s!=shapes[0] for s in shapes):raise ValueError()
            return (len(value),)+(shapes[0] if shapes else ())
        if not isinstance(obj,list):return 0
        shape(obj)
        return 1
    except (ValueError,TypeError,RecursionError):
        return 0


def utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')


def uuid_text(value):
    try:return parse_uuid(value)
    except (ValueError,UnicodeError):return None


def timestamp_instant(value):
    from datetime import datetime,timezone
    instant=datetime.fromisoformat(value.replace('Z','+00:00'))
    if instant.tzinfo is None:instant=instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def timestamp_order(value):
    from datetime import datetime,timezone
    if value is None:return None
    instant=timestamp_instant(value)
    delta=instant-datetime(1970,1,1,tzinfo=timezone.utc)
    return ((delta.days*86400+delta.seconds)*1000000)+delta.microseconds


def register_functions(dbapi, info):
    from uuid import uuid4
    from .snapshots import register
    register(dbapi,info)
    dbapi.create_function('workpal_uuid',0,lambda:str(uuid4()))
    dbapi.create_function('workpal_uuid_text',1,uuid_text,deterministic=True)
    dbapi.create_function('workpal_timestamp_order',1,timestamp_order,deterministic=True)
    dbapi.create_function('workpal_now',0,lambda:info.get('transaction_time') or utc_now())
    dbapi.create_function('workpal_jsonb_valid',1,jsonb_valid,deterministic=True)
    dbapi.create_function('workpal_array_valid',2,array_valid,deterministic=True)


def on_connect(dbapi, record):
    register_functions(dbapi,record.info)


def on_begin(connection):
    connection.info['transaction_time']=utc_now()
    connection.info.pop('transaction_xid',None)
    connection.info['transaction_settings']={}


def on_savepoint(connection,name):
    # sqlite3 does not BEGIN for SAVEPOINT; a first savepoint would otherwise
    # become the physical outer transaction and commit when released. Keep
    # ordinary read behavior intact, but establish an outer tx before nesting.
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN')


def install(engine, connection=None):
    """Both application engines and independently invoked Alembic need codecs."""
    from sqlalchemy import event
    if not event.contains(engine,'connect',on_connect):
        event.listen(engine,'connect',on_connect)
        event.listen(engine,'begin',on_begin)
        event.listen(engine,'savepoint',on_savepoint)
    if connection is not None:
        register_functions(connection.connection.driver_connection,connection.info)
