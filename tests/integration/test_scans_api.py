"""
Integration tests for Scans API endpoints.
Tests creation, status tracking, and results retrieval.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestScansAPI:
    """Test suite for /api/scans endpoints."""

    async def test_create_scan(self, async_client: AsyncClient):
        """Test successful scan creation."""
        payload = {
            "name": "Test Scan",
            "target": "127.0.0.1",
            "scan_type": "ping",
            "options": {}
        }
        response = await async_client.post("/api/scans", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["target"] == "127.0.0.1"
        assert data["status"] in ["pending", "running"]
        assert "id" in data

    async def test_get_scans_list(self, async_client: AsyncClient, test_scan):
        """Test retrieving list of scans."""
        response = await async_client.get("/api/scans")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_scan_by_id(self, async_client: AsyncClient, test_scan):
        """Test retrieving a specific scan by ID."""
        scan_id = test_scan.id
        response = await async_client.get(f"/api/scans/{scan_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == scan_id

    async def test_get_scan_results(self, async_client: AsyncClient, test_scan):
        """Test retrieving scan results."""
        scan_id = test_scan.id
        # Assuming results endpoint exists
        response = await async_client.get(f"/api/scans/{scan_id}/results")
        
        # Might be 200 with empty list or 404 if not finished
        assert response.status_code in [200, 404]

    async def test_delete_scan(self, async_client: AsyncClient, test_scan):
        """Test deleting a scan."""
        scan_id = test_scan.id
        response = await async_client.delete(f"/api/scans/{scan_id}")
        
        assert response.status_code == 204
        
        # Verify deletion
        get_resp = await async_client.get(f"/api/scans/{scan_id}")
        assert get_resp.status_code == 404

    async def test_create_scan_validation_error(self, async_client: AsyncClient):
        """Test validation error on invalid scan target."""
        payload = {
            "target": "",  # Invalid empty target
            "scan_type": "ping"
        }
        response = await async_client.post("/api/scans", json=payload)
        assert response.status_code == 422

    async def test_create_scan_invalid_type(self, async_client: AsyncClient):
        """Test validation error on invalid scan type."""
        payload = {
            "target": "127.0.0.1",
            "scan_type": "invalid_type"
        }
        response = await async_client.post("/api/scans", json=payload)
        assert response.status_code == 422

    async def test_filter_scans_by_status(self, async_client: AsyncClient, test_scan):
        """Test filtering scans by status."""
        # Assuming test_scan is 'pending' or 'running'
        status = test_scan.status
        response = await async_client.get(f"/api/scans?status={status}")
        
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == status for item in data)
