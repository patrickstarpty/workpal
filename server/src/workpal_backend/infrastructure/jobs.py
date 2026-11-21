"""Durable single-row recurring schedules; caller owns every transaction."""
import time
from uuid import uuid4
from sqlalchemy import Table, MetaData, Column, String, Float, Integer, Text, select, update, and_, or_
from sqlalchemy.dialects.sqlite import insert
jobs = Table('scheduled_jobs', MetaData(),
    Column('name', String, primary_key=True), Column('due', Float, nullable=False),
    Column('token', String), Column('lease_until', Float),
    Column('attempts', Integer, nullable=False), Column('last_error', Text))

def schedule(session, name, *, now=None):
    session.execute(insert(jobs).values(name=name, due=time.time() if now is None else now,
        attempts=0).on_conflict_do_nothing(index_elements=['name']))

def claim(session, *, now=None, lease_seconds=60):
    if not 1 <= lease_seconds <= 300: raise ValueError('Invalid lease')
    now = time.time() if now is None else now
    eligible = and_(jobs.c.due <= now, or_(jobs.c.token.is_(None), jobs.c.lease_until <= now))
    name = select(jobs.c.name).where(eligible).order_by(jobs.c.due, jobs.c.name).limit(1).scalar_subquery()
    row = session.execute(update(jobs).where(jobs.c.name == name, eligible).values(
        token=str(uuid4()), lease_until=now+lease_seconds, attempts=jobs.c.attempts+1
    ).returning(jobs)).mappings().first()
    return dict(row) if row else None

def finish(session, job, *, interval, now=None, error=None):
    if not .05 <= interval <= 86400: raise ValueError('Invalid interval')
    now = time.time() if now is None else now
    delay = interval if error is None else min(300, 2 ** min(job['attempts'], 8))
    return session.execute(update(jobs).where(jobs.c.name==job['name'], jobs.c.token==job['token'],
        jobs.c.lease_until>now).values(token=None, lease_until=None, due=now+delay,
        attempts=0 if error is None else job['attempts'],
        last_error=None if error is None else str(error)[:2048])).rowcount == 1
