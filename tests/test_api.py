"""
CompanyAI — API Health & Root Endpoint Tests
===============================================
FastAPI uygulamasının temel endpoint testleri.
"""

import pytest
import pytest_asyncio


class TestRootEndpoint:
    """/ endpoint testleri."""

    @pytest.mark.asyncio
    async def test_root_returns_json(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"


class TestHealthEndpoint:
    """/api/health endpoint testleri."""

    @pytest.mark.asyncio
    async def test_health_returns_version(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "status" in data
