# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration tests for waketrd service."""
import pytest
import httpx

from clawos_core.constants import PORT_WAKETRD

WAKETRD_URL = f"http://127.0.0.1:{PORT_WAKETRD}"


@pytest.mark.asyncio
class TestWakeTrdAPI:
    """Integration tests for waketrd HTTP API."""

    async def test_health_endpoint(self):
        """Test health check endpoint."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{WAKETRD_URL}/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"
                assert data["service"] == "waketrd"
        except httpx.ConnectError:
            pytest.skip("waketrd not running")

    async def test_trigger_endpoint(self):
        """Test wake trigger endpoint."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{WAKETRD_URL}/trigger")
                assert response.status_code == 200
                data = response.json()
                assert data["triggered"] is True
                assert "action" in data
        except httpx.ConnectError:
            pytest.skip("waketrd not running")
        except httpx.ReadTimeout:
            pytest.skip("waketrd timeout (LLM may be slow)")

    async def test_cooldown(self):
        """Test that rapid triggers are rate-limited."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # First trigger should succeed
                response = await client.post(f"{WAKETRD_URL}/trigger")
                assert response.status_code == 200
                data = response.json()

                if data.get("triggered"):
                    # Immediate second trigger should be on cooldown
                    response2 = await client.post(f"{WAKETRD_URL}/trigger")
                    data2 = response2.json()
                    assert data2.get("reason") == "cooldown"

        except httpx.ConnectError:
            pytest.skip("waketrd not running")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
