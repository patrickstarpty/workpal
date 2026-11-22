"""PostgreSQL pg_snapshot input observations from isolated reference database."""
import pytest
from workpal_backend.infrastructure.snapshots import parse_snapshot,visible

@pytest.mark.parametrize('raw',['3:6:5,4','0:0:','0:1:','5:3:','3:6:2','3:6:6','3:3: '])
def test_reject_invalid_snapshot(raw):
    with pytest.raises(ValueError):parse_snapshot(raw)

@pytest.mark.parametrize('raw,expected',[
    (' 3:3:',(3,3,frozenset())),('03:06:04',(3,6,frozenset({4}))),
    ('3:6:4,4',(3,6,frozenset({4}))),
    ('3:18446744073709551616:',(3,(1<<64)-1,frozenset())),
])
def test_snapshot_canonicalization(raw,expected):assert parse_snapshot(raw)==expected


def test_visibility_boundaries():
    assert [visible(x,'3:6:4') for x in [2,3,4,5,6]]==[1,1,0,1,0]


def test_snapshot_accepts_one_trailing_active_separator():
    assert parse_snapshot('3:6:4,')==(3,6,frozenset({4}))
    with pytest.raises(ValueError):parse_snapshot('3:6:4,,')
