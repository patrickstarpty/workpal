from uuid import UUID
import pytest


def test_uuid7_uses_submillisecond_sequence_and_retains_random_tail():
    from workpal_backend.infrastructure.uuid7 import UUID7Generator
    value=UUID(UUID7Generator(clock_ns=lambda:1_234_567_890,random_bytes=lambda n:bytes(range(n)))())
    assert value.version==7 and value.variant=='specified in RFC 4122'
    assert int.from_bytes(value.bytes[:6],'big')==1234
    assert (int.from_bytes(value.bytes[6:8],'big')&4095)==567890>>8
    assert value.bytes[8:]==bytes([0x88,9,10,11,12,13,14,15])


def test_repeated_and_backwards_clock_advances_monotonically():
    from workpal_backend.infrastructure.uuid7 import UUID7Generator
    times=iter([1_000_000_000,1_000_000_000,999_000_000])
    generator=UUID7Generator(clock_ns=lambda:next(times),random_bytes=lambda n:b'\0'*n)
    values=[UUID(generator()).int for _ in range(3)]
    assert values[0]<values[1]<values[2]
    assert values[1]-values[0]==1<<64 and values[2]-values[1]==1<<64


def test_sequence_overflow_carries_into_milliseconds():
    from workpal_backend.infrastructure.uuid7 import UUID7Generator
    generator=UUID7Generator(clock_ns=lambda:0,random_bytes=lambda n:b'\0'*n)
    values=[UUID(generator()) for _ in range(4096)]
    assert int.from_bytes(values[-1].bytes[:6],'big')==1
    assert int.from_bytes(values[-1].bytes[6:8],'big')&4095==0


def test_random_failure_does_not_consume_clock_or_sequence():
    from workpal_backend.infrastructure.uuid7 import UUID7Generator
    calls=[]
    def failed(n):raise OSError('entropy unavailable')
    generator=UUID7Generator(clock_ns=lambda:calls.append('clock'),random_bytes=failed)
    with pytest.raises(OSError):generator()
    assert not calls
