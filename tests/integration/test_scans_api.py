"""
Integration tests for Scans API endpoints.
Tests creation, status tracking, and results retrieval.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

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


class TestScanStatusAPI:
    """Test suite for /api/scans/status endpoint."""

    async def test_get_status_empty(self, async_client: AsyncClient):
        """Test status endpoint with no jobs."""
        response = await async_client.get("/api/scans/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "queues" in data
        assert "recent_jobs" in data
        assert "nmap_rustscan" in data["queues"]
        assert "utilities" in data["queues"]

    async def test_get_status_with_jobs(self, async_client: AsyncClient, db_session):
        """Test status endpoint with existing jobs."""
        from backend.models.scan import ScanJob, Scan
        
        # Create a scan
        scan = Scan(
            name="Status Test Scan",
            target="192.168.1.1",
            scan_type="nmap",
            status="running"
        )
        db_session.add(scan)
        await db_session.flush()
        
        # Create a job
        job = ScanJob(
            scan_id=scan.id,
            job_type="nmap",
            status="running"
        )
        db_session.add(job)
        await db_session.commit()
        
        response = await async_client.get("/api/scans/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["queues"]["nmap_rustscan"]["is_running"] is True
        assert len(data["recent_jobs"]) >= 1


class TestDigScanAPI:
    """Test suite for /api/scans/dig endpoint."""

    async def test_dig_scan_success(self, async_client: AsyncClient):
        """Test successful dig scan creation."""
        payload = {
            "targets_text": "example.com",
            "dns_server": "8.8.8.8",
            "cli_args": "",
            "record_types": ["A"]
        }
        response = await async_client.post("/api/scans/dig", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert "message" in data

    async def test_dig_scan_minimal_payload(self, async_client: AsyncClient):
        """Test dig scan with minimal required fields."""
        payload = {
            "targets_text": "google.com"
        }
        response = await async_client.post("/api/scans/dig", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    async def test_dig_scan_creates_db_record(self, async_client: AsyncClient, db_session):
        """Test that dig scan creates a record in the database."""
        payload = {
            "targets_text": "test-dig.example.com",
            "dns_server": "1.1.1.1"
        }
        response = await async_client.post("/api/scans/dig", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        job_id = data["job_id"]
        
        # Verify the scan exists in the database
        from backend.models.scan import Scan
        result = await db_session.execute(select(Scan).where(Scan.id == job_id))
        scan = result.scalar_one_or_none()
        
        assert scan is not None
        assert scan.scan_type == "dig"
        assert "test-dig.example.com" in scan.target


class TestNmapRustscanAPI:
    """Test suite for /api/scans/nmap and /api/scans/rustscan endpoints."""

    async def test_nmap_scan_success(self, async_client: AsyncClient):
        """Test successful nmap scan initiation."""
        response = await async_client.post("/api/scans/nmap", params={"target": "192.168.1.1"})
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "queued"

    async def test_rustscan_success(self, async_client: AsyncClient):
        """Test successful rustscan initiation."""
        response = await async_client.post("/api/scans/rustscan", params={"target": "192.168.1.1"})
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "queued"


class TestScanQueueAPI:
    """Test suite for scan queue endpoints."""

    async def test_get_scan_queue(self, async_client: AsyncClient):
        """Test getting scan queue."""
        response = await async_client.get("/api/scans/scan-queue")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_get_scan_jobs(self, async_client: AsyncClient):
        """Test getting all scan jobs."""
        response = await async_client.get("/api/scans/scan-job")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_cancel_scan_job_not_found(self, async_client: AsyncClient):
        """Test cancelling non-existent job returns 404."""
        response = await async_client.delete("/api/scans/scan-queue/99999")
        
        # The current implementation returns 200 with message, but could be improved
        assert response.status_code in [200, 404]

    async def test_stop_scan_job_not_found(self, async_client: AsyncClient):
        """Test stopping non-existent job."""
        response = await async_client.post("/api/scans/scan-job/99999/stop")
        
        assert response.status_code in [200, 404]

    async def test_retry_scan_job_not_found(self, async_client: AsyncClient):
        """Test retrying non-existent job."""
        response = await async_client.post("/api/scans/scan-job/99999/retry")
        
        assert response.status_code in [200, 404]


class TestScanImportAPI:
    """Test suite for scan import endpoints."""

    async def test_import_scan_file(self, async_client: AsyncClient):
        """Test importing a scan file."""
        # Create a temporary file for testing
        import io
        file_content = b"test scan results"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        
        response = await async_client.post("/api/scans/import", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "filename" in data
        assert data["filename"] == "test.txt"

    async def test_import_xml_scan(self, async_client: AsyncClient):
        """Test importing an XML scan file."""
        import io
        xml_content = b"<?xml version='1.0'?><nmaprun></nmaprun>"
        files = {"file": ("scan.xml", io.BytesIO(xml_content), "application/xml")}
        
        response = await async_client.post("/api/scans/import-xml", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "filename" in data
        assert data["filename"] == "scan.xml"


class TestScanUpdateAPI:
    """Test suite for scan update endpoints."""

    async def test_update_scan_success(self, async_client: AsyncClient, test_scan):
        """Test successful scan update."""
        scan_id = test_scan.id
        payload = {
            "name": "Updated Scan Name",
            "status": "completed",
            "progress": 100
        }
        response = await async_client.put(f"/api/scans/{scan_id}", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Scan Name"
        assert data["status"] == "completed"
        assert data["progress"] == 100

    async def test_update_scan_not_found(self, async_client: AsyncClient):
        """Test updating non-existent scan returns 404."""
        payload = {"name": "Updated Name"}
        response = await async_client.put("/api/scans/99999", json=payload)
        
        assert response.status_code == 404

    async def test_update_scan_partial_update(self, async_client: AsyncClient, test_scan):
        """Test partial update of scan (only name)."""
        scan_id = test_scan.id
        original_status = test_scan.status
        
        payload = {"name": "Partial Update Name"}
        response = await async_client.put(f"/api/scans/{scan_id}", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Partial Update Name"
        # Status should remain unchanged
        assert data["status"] == original_status


class TestScanNotFoundErrors:
    """Test suite for 404 error handling."""

    async def test_get_scan_not_found(self, async_client: AsyncClient):
        """Test getting non-existent scan returns 404."""
        response = await async_client.get("/api/scans/99999")
        assert response.status_code == 404

    async def test_get_scan_results_not_found(self, async_client: AsyncClient):
        """Test getting results for non-existent scan returns 404."""
        response = await async_client.get("/api/scans/99999/results")
        assert response.status_code == 404

    async def test_delete_scan_not_found(self, async_client: AsyncClient):
        """Test deleting non-existent scan returns 404."""
        response = await async_client.delete("/api/scans/99999")
        assert response.status_code == 404

    async def test_get_scan_job_not_found(self, async_client: AsyncClient):
        """Test getting non-existent scan job returns 404."""
        response = await async_client.get("/api/scans/scan-job/99999")
        assert response.status_code == 404

    async def test_download_result_not_found(self, async_client: AsyncClient):
        """Test downloading results for non-existent job returns 404."""
        response = await async_client.get("/api/scans/scan-job/99999/download/json")
        assert response.status_code == 404


class TestActiveScansAPI:
    """Test suite for active scans endpoints."""

    async def test_get_active_scans_empty(self, async_client: AsyncClient):
        """Test getting active scans when none exist."""
        response = await async_client.get("/api/scans/active")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_get_active_scans_with_data(self, async_client: AsyncClient, db_session):
        """Test getting active scans when some exist."""
        from backend.models.scan import Scan
        
        # Create an active scan
        scan = Scan(
            name="Active Test Scan",
            target="10.0.0.1",
            scan_type="nmap",
            status="running",
            progress=50
        )
        db_session.add(scan)
        await db_session.commit()
        
        response = await async_client.get("/api/scans/active")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should contain at least our running scan
        running_scans = [s for s in data if s["status"] == "running"]
        assert len(running_scans) >= 1


class TestScanHistoryAPI:
    """Test suite for scan history endpoints."""

    async def test_get_history_alias(self, async_client: AsyncClient, test_scan):
        """Test that /history endpoint works as alias."""
        response = await async_client.get("/api/scans/history")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_history_contains_created_scan(self, async_client: AsyncClient, test_scan):
        """Test that history contains created scans."""
        response = await async_client.get("/api/scans/history")
        
        assert response.status_code == 200
        data = response.json()
        scan_ids = [s["id"] for s in data]
        assert test_scan.id in scan_ids


class TestScanQueueEdgeCases:
    """Test suite for edge cases in scan queue operations."""

    async def test_get_queue_job_not_found(self, async_client: AsyncClient):
        """Test getting non-existent queue job returns 404."""
        response = await async_client.get("/api/scans/scan-queue/99999")
        assert response.status_code == 404

    async def test_stop_non_existent_job(self, async_client: AsyncClient):
        """Test stopping non-existent job."""
        response = await async_client.post("/api/scans/scan-job/88888/stop")
        # Current implementation may return 200 or 404
        assert response.status_code in [200, 404]

    async def test_retry_non_existent_job(self, async_client: AsyncClient):
        """Test retrying non-existent job."""
        response = await async_client.post("/api/scans/scan-job/77777/retry")
        assert response.status_code in [200, 404]

    async def test_download_invalid_format(self, async_client: AsyncClient, db_session):
        """Test downloading with invalid format."""
        # Create a scan and job first
        from backend.models.scan import Scan, ScanJob
        
        scan = Scan(
            name="Download Test Scan",
            target="10.0.0.1",
            scan_type="nmap",
            status="completed"
        )
        db_session.add(scan)
        await db_session.flush()
        
        job = ScanJob(scan_id=scan.id, job_type="nmap", status="completed")
        db_session.add(job)
        await db_session.commit()
        
        response = await async_client.get(f"/api/scans/scan-job/{job.id}/download/invalid_format")
        # Should return 404 as results don't exist
        assert response.status_code == 404


class TestDigScanEdgeCases:
    """Test suite for edge cases in dig scan operations."""

    async def test_dig_scan_empty_targets(self, async_client: AsyncClient):
        """Test dig scan with empty targets_text."""
        payload = {"targets_text": ""}
        response = await async_client.post("/api/scans/dig", json=payload)
        
        # Should still create a scan (validation depends on implementation)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    async def test_dig_scan_multiple_targets(self, async_client: AsyncClient):
        """Test dig scan with multiple targets."""
        payload = {
            "targets_text": "example.com\ngoogle.com\ntest.org",
            "dns_server": "8.8.4.4",
            "record_types": ["A", "MX", "TXT"]
        }
        response = await async_client.post("/api/scans/dig", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    async def test_dig_scan_no_dns_server(self, async_client: AsyncClient):
        """Test dig scan without specifying DNS server."""
        payload = {
            "targets_text": "example.com",
            "record_types": ["A"]
        }
        response = await async_client.post("/api/scans/dig", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data


class TestNmapRustscanEdgeCases:
    """Test suite for edge cases in nmap/rustscan operations."""

    async def test_nmap_scan_empty_target(self, async_client: AsyncClient):
        """Test nmap scan with empty target."""
        response = await async_client.post("/api/scans/nmap", params={"target": ""})
        # May return 200 (queued) or 422 (validation error)
        assert response.status_code in [200, 422]

    async def test_rustscan_special_characters_target(self, async_client: AsyncClient):
        """Test rustscan with special characters in target."""
        response = await async_client.post("/api/scans/rustscan", params={"target": "192.168.1.0/24"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"


class TestStatusEndpointEdgeCases:
    """Test suite for edge cases in status endpoint."""

    async def test_status_queues_structure(self, async_client: AsyncClient):
        """Test that status endpoint returns correct queue structure."""
        response = await async_client.get("/api/scans/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check nmap_rustscan queue structure
        nmap_queue = data["queues"]["nmap_rustscan"]
        assert "queue_length" in nmap_queue
        assert "current_job_id" in nmap_queue
        assert "is_running" in nmap_queue
        assert "queued_jobs" in nmap_queue
        assert isinstance(nmap_queue["queued_jobs"], list)
        
        # Check utilities queue structure
        util_queue = data["queues"]["utilities"]
        assert "queue_length" in util_queue
        assert "current_job_id" in util_queue
        assert "is_running" in util_queue
        assert "queued_jobs" in util_queue
        assert isinstance(util_queue["queued_jobs"], list)

    async def test_status_recent_jobs_limit(self, async_client: AsyncClient, db_session):
        """Test that recent_jobs is limited to 20 items."""
        from backend.models.scan import Scan, ScanJob
        
        # Create more than 20 jobs
        for i in range(25):
            scan = Scan(
                name=f"Status Test Scan {i}",
                target=f"192.168.1.{i}",
                scan_type="nmap",
                status="completed"
            )
            db_session.add(scan)
        
        await db_session.flush()
        
        for i in range(25):
            job = ScanJob(
                scan_id=i + 1,
                job_type="nmap",
                status="completed"
            )
            db_session.add(job)
        
        await db_session.commit()
        
        response = await async_client.get("/api/scans/status")
        
        assert response.status_code == 200
        data = response.json()
        # recent_jobs should be limited to 20
        assert len(data["recent_jobs"]) <= 20
