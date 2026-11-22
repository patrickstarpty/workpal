import json
import pytest
from workpal_backend.auth.waitlist_decode import decode_waitlist


@pytest.mark.parametrize('email', ['ü@example.com', 'Team: a@example.com;', 'Team: "A,B" <a@example.com>;', '"a,b"@example.com', 'a@example.com (a,b)'])
def test_single_mailbox(email):
    assert decode_waitlist(json.dumps({'email': email}).encode()) == (email.lower(), None)


@pytest.mark.parametrize('email', ['a@example.com,', 'a@example.com, (comment)', 'Team:;', 'Team: a@example.com,b@example.com;', 'a@example.com,b@example.com'])
def test_reject_non_single_mailbox(email):
    with pytest.raises(ValueError, match='email is invalid'):
        decode_waitlist(json.dumps({'email': email}).encode())


def test_simple_fold_ordered_null():
    assert decode_waitlist(b'{"EMAIL":"a@example.com","rea\\u017fon":"first","REASON":null}') == ('a@example.com', 'first')
