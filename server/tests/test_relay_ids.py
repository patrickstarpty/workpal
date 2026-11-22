from concurrent.futures import ThreadPoolExecutor
import pytest


def test_ulid_encoding_time_and_entropy_bounds():
    from workpal_backend.realtime.relay_ids import encode_ulid
    assert encode_ulid(0, 0) == '0' * 26
    assert encode_ulid((1 << 48) - 1, (1 << 80) - 1) == '7' + 'Z' * 25
    assert encode_ulid(1469918176385, int('D3BFD8D38D18854D03D3', 16)) == '01ARYZ6S41TEZXHMWD322MT0YK'
    for timestamp in [-1, 1 << 48]:
        with pytest.raises(ValueError):
            encode_ulid(timestamp, 0)


def test_monotonic_entropy_same_millisecond_clock_rollback_and_overflow():
    from workpal_backend.realtime.relay_ids import ULIDGenerator, encode_ulid
    now = [10]
    source = iter([1, 100, (1 << 80) - 1])
    generator = ULIDGenerator(clock_ms=lambda: now[0], entropy=lambda: next(source), increment=lambda: 3)
    assert generator.make() == encode_ulid(10, 1)
    assert generator.make() == encode_ulid(10, 4)
    now[0] = 9
    assert generator.make() == encode_ulid(9, 100)
    now[0] = 11
    assert generator.make() == encode_ulid(11, (1 << 80) - 1)
    with pytest.raises(OverflowError):
        generator.make()


def test_generator_serializes_shared_entropy_across_threads():
    from workpal_backend.realtime.relay_ids import ULIDGenerator
    generator = ULIDGenerator(clock_ms=lambda: 100, entropy=lambda: 1, increment=lambda: 1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: generator.make(), range(200)))
    assert len(set(values)) == 200
    assert len({value[:10] for value in values}) == 1
