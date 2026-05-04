"""Tests for app.rate_limiter — IP-based rate limiting (AUTH-06 to AUTH-08)."""

import pytest
import time
from unittest.mock import MagicMock
from fastapi import HTTPException


class TestCheckRateLimit:
    """AUTH-06: check_rate_limit allows up to 5 requests per 60 seconds per IP."""

    @pytest.fixture
    def fresh_ip(self):
        """Return a unique IP for each test to avoid state bleed."""
        return f"192.168.1.{id(time.time()) % 256}"

    @pytest.fixture
    def mock_request(self, fresh_ip):
        req = MagicMock()
        req.client.host = fresh_ip
        req.headers = {}
        return req

    def test_first_request_succeeds(self, mock_request):
        import app.rate_limiter as rl
        # Clear any leftover state for this IP
        rl._rate_limit_store.pop(mock_request.client.host, None)
        result = rl.check_rate_limit(mock_request)
        assert result == mock_request.client.host

    def test_fifth_request_succeeds(self, mock_request):
        import app.rate_limiter as rl
        ip = mock_request.client.host
        rl._rate_limit_store.clear()
        for i in range(4):
            rl.check_rate_limit(mock_request)
        # 5th request should still succeed (limit is 5, so 1-5 succeed)
        result = rl.check_rate_limit(mock_request)
        assert result == ip

    def test_different_ips_are_independent(self):
        import app.rate_limiter as rl
        rl._rate_limit_store.clear()
        req1 = MagicMock()
        req1.client.host = "10.0.0.1"
        req1.headers = {}
        req2 = MagicMock()
        req2.client.host = "10.0.0.2"
        req2.headers = {}
        for _ in range(5):
            rl.check_rate_limit(req1)
        # IP2 should still be able to make requests
        result = rl.check_rate_limit(req2)
        assert result == "10.0.0.2"


class TestCheckRateLimitExceeded:
    """AUTH-07: check_rate_limit raises HTTPException 429 after limit exceeded."""

    def test_sixth_request_raises_429(self):
        import app.rate_limiter as rl
        rl._rate_limit_store.clear()
        ip = f"203.0.113.{id(time.time()) % 255}"
        req = MagicMock()
        req.client.host = ip
        req.headers = {}
        for i in range(5):
            rl.check_rate_limit(req)
        with pytest.raises(HTTPException) as exc_info:
            rl.check_rate_limit(req)
        assert exc_info.value.status_code == 429

    def test_429_detail_contains_limit(self):
        import app.rate_limiter as rl
        rl._rate_limit_store.clear()
        ip = f"203.0.113.{id(time.time()) % 254}"
        req = MagicMock()
        req.client.host = ip
        req.headers = {}
        for _ in range(5):
            rl.check_rate_limit(req)
        with pytest.raises(HTTPException) as exc_info:
            rl.check_rate_limit(req)
        assert str(rl.MAX_ATTEMPTS) in exc_info.value.detail

    def test_429_detail_contains_window_seconds(self):
        import app.rate_limiter as rl
        rl._rate_limit_store.clear()
        ip = f"203.0.113.{id(time.time()) % 253}"
        req = MagicMock()
        req.client.host = ip
        req.headers = {}
        for _ in range(5):
            rl.check_rate_limit(req)
        with pytest.raises(HTTPException) as exc_info:
            rl.check_rate_limit(req)
        assert "60" in exc_info.value.detail


class TestCleanOldTimestamps:
    """AUTH-08: _clean_old_timestamps removes timestamps outside the sliding window."""

    def test_recent_timestamp_retained(self):
        import app.rate_limiter as rl
        now = time.time()
        timestamps = [now - 30]  # 30 seconds ago — inside 60s window
        result = rl._clean_old_timestamps(timestamps, now)
        assert len(result) == 1

    def test_old_timestamp_removed(self):
        import app.rate_limiter as rl
        now = time.time()
        timestamps = [now - 61]  # 61 seconds ago — outside 60s window
        result = rl._clean_old_timestamps(timestamps, now)
        assert len(result) == 0

    def test_empty_list_returns_empty(self):
        import app.rate_limiter as rl
        result = rl._clean_old_timestamps([], time.time())
        assert result == []

    def test_mixed_timestamps_keeps_only_recent(self):
        import app.rate_limiter as rl
        now = time.time()
        timestamps = [now - 10, now - 30, now - 61, now - 120]
        result = rl._clean_old_timestamps(timestamps, now)
        assert len(result) == 2
        assert all(now - ts < 60 for ts in result)