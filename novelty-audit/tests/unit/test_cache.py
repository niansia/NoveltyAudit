import os
import time

from cache import JsonCache


def test_cache_round_trip_and_schema_rotation(tmp_path):
    cache = JsonCache(tmp_path, schema_version="1")
    cache.set("search", {"q": "memory"}, [1, 2])
    assert cache.get("search", {"q": "memory"}) == [1, 2]
    assert JsonCache(tmp_path, schema_version="2").get("search", {"q": "memory"}) is None


def test_stale_cache_misses(tmp_path):
    cache = JsonCache(tmp_path, ttl_seconds=0)
    cache.set("x", "y", 1)
    time.sleep(0.01)
    assert cache.get("x", "y") is None

