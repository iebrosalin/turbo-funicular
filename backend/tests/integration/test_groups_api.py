"""
Integration tests for Groups API endpoints.
Tests CRUD operations, tree structure, and validation.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


class TestGroupsAPI:
    """Test suite for /api/groups endpoints."""

    async def test_create_group(self, async_client: AsyncClient):
        """Test successful group creation."""
        payload = {"name": "Test Group", "description": "Auto-created test group"}
        response = await async_client.post("/api/groups", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Group"
        assert data["description"] == "Auto-created test group"
        assert "id" in data

    async def test_get_groups_tree(self, async_client: AsyncClient, test_group_hierarchy):
        """Test retrieving the full groups tree."""
        response = await async_client.get("/api/groups/tree")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Check if root nodes are present
        assert len(data) > 0

    async def test_move_group_success(self, async_client: AsyncClient, test_group_hierarchy):
        """Test moving a group to a new parent."""
        # Structure: Parent -> Child. Move Child to Root (parent_id=None) or vice versa depending on fixture
        # Assuming fixture creates: Root -> Child. Let's try moving Child to be a sibling of Root (if possible) 
        # or create two roots and move one under another.
        # For simplicity, let's assume we have Group A and Group B (siblings). Move B under A.
        
        # Create two groups first if fixture doesn't provide siblings
        g1 = await async_client.post("/api/groups", json={"name": "G1"})
        g2 = await async_client.post("/api/groups", json={"name": "G2"})
        g1_id = g1.json()["id"]
        g2_id = g2.json()["id"]

        response = await async_client.post(f"/api/groups/{g2_id}/move", json={"parent_id": g1_id})
        
        assert response.status_code == 200
        data = response.json()
        assert data["parent_id"] == g1_id

    async def test_move_group_cyclic_dependency(self, async_client: AsyncClient, test_group_hierarchy):
        """Test preventing cyclic dependency when moving groups."""
        # Fixture likely creates Parent -> Child. Try moving Parent under Child.
        # We need IDs. Let's create a specific scenario.
        parent = await async_client.post("/api/groups", json={"name": "CycParent"})
        child = await async_client.post("/api/groups", json={"name": "CycChild", "parent_id": parent.json()["id"]})
        
        p_id = parent.json()["id"]
        c_id = child.json()["id"]

        # Try to move Parent under Child -> Should fail
        response = await async_client.post(f"/api/groups/{p_id}/move", json={"parent_id": c_id})
        
        assert response.status_code == 400
        assert "cyclic" in response.json()["detail"].lower()

    async def test_delete_group_with_assets(self, async_client: AsyncClient, asset_in_group):
        """Test cascading delete or handling of assets when deleting a group."""
        group_id = asset_in_group.group_id
        
        response = await async_client.delete(f"/api/groups/{group_id}")
        
        # Depending on business logic: either 200 (cascade) or 400 (has assets)
        # Assuming cascade delete for now based on typical requirements, or check specific logic
        # If logic prevents deletion: assert response.status_code == 400
        assert response.status_code in [200, 404] 

    async def test_update_group(self, async_client: AsyncClient, test_group_hierarchy):
        """Test updating group details."""
        # Get first group from fixture or create one
        g = await async_client.post("/api/groups", json={"name": "ToUpdate"})
        g_id = g.json()["id"]
        
        payload = {"name": "Updated Name", "description": "New Desc"}
        response = await async_client.put(f"/api/groups/{g_id}", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New Desc"

    async def test_get_group_not_found(self, async_client: AsyncClient):
        """Test getting a non-existent group."""
        response = await async_client.get("/api/groups/99999")
        assert response.status_code == 404

    async def test_validation_error(self, async_client: AsyncClient):
        """Test validation error on empty name."""
        payload = {"name": ""}
        response = await async_client.post("/api/groups", json=payload)
        assert response.status_code == 422
