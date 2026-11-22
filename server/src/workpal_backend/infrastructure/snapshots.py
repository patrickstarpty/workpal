"""Search snapshot visibility and transaction IDs for SQLite's single writer.

Identifiers belong to this database, not the reference PostgreSQL instance.
Concurrent/retention API parity is verified separately from the trigger schema.
"""
import re
MAX_XID=(1<<64)-1


def parse_snapshot(raw):
    number=r'[ \t\r\n\v\f]*[+-]?[0-9]+'
    if not isinstance(raw,str) or not re.fullmatch(number+':'+number+':(?:'+number+'(?:,'+number+')*,?)?',raw):
        raise ValueError('invalid snapshot')
    def unsigned(token):
        token=token.lstrip(' \t\r\n\v\f')
        negative=token.startswith('-')
        digits=token.lstrip('+-').lstrip('0') or '0'
        # PostgreSQL's input helper uses strtou64 without rejecting ERANGE.
        if len(digits)>20 or (len(digits)==20 and digits>str(MAX_XID)):return MAX_XID
        value=int(digits)
        return (-value)&MAX_XID if negative else value
    low,high,active=raw.split(':')
    low,high=unsigned(low),unsigned(high)
    active=active.removesuffix(',')
    active=tuple(unsigned(x) for x in active.split(',')) if active else ()
    if not 0<low<=high<=MAX_XID or any(not low<=x<high for x in active) or any(a>b for a,b in zip(active,active[1:])):
        raise ValueError('invalid snapshot')
    return low,high,frozenset(active)


def visible(xid,snapshot):
    low,high,active=parse_snapshot(snapshot)
    xid=int(xid)
    if not 0<=xid<=MAX_XID:raise ValueError('invalid transaction id')
    return int(xid<low or (xid<high and xid not in active))


def register(dbapi,info):
    def xid():
        current=info.get('transaction_xid')
        if current is None:
            current=dbapi.execute('UPDATE workpal_transaction_clock SET value=value+1 WHERE singleton=1 RETURNING value').fetchone()[0]
            info['transaction_xid']=current
        else:
            # A savepoint can roll back the counter allocation while the
            # connection-local transaction ID remains assigned. Re-reserve
            # that ID before committing any later change in the outer tx.
            dbapi.execute('UPDATE workpal_transaction_clock SET value=? WHERE singleton=1 AND value<?',(current,current))
        return current
    def snapshot():
        # A writer's own ID is not visible in pg_current_snapshot either.
        high=info.get('transaction_xid')
        if high is None:
            high=dbapi.execute('SELECT value+1 FROM workpal_transaction_clock WHERE singleton=1').fetchone()[0]
        return f'{high}:{high}:'
    dbapi.create_function('workpal_xid',0,xid)
    dbapi.create_function('workpal_current_snapshot',0,snapshot)
    dbapi.create_function('workpal_visible_in_snapshot',2,visible,deterministic=True)
    dbapi.create_function('workpal_setting',1,lambda key:info.get('transaction_settings',{}).get(key))
