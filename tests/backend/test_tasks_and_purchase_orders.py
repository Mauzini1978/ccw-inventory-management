"""
Tests for task and purchase order API endpoints.
"""
import pytest

import main


@pytest.fixture
def clean_state():
    """Reset in-memory task and purchase order state before and after each test."""
    main.tasks_store.clear()
    po_snapshot = list(main.purchase_orders)
    yield
    main.tasks_store.clear()
    main.purchase_orders[:] = po_snapshot


@pytest.fixture
def backlog_item_without_po(client):
    """A backlog item that has no purchase order yet."""
    items = client.get("/api/backlog").json()
    for item in items:
        if not item["has_purchase_order"]:
            return item
    pytest.skip("All backlog items already have a purchase order")


def _po_payload(backlog_item_id):
    return {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Components",
        "quantity": 50,
        "unit_cost": 12.5,
        "expected_delivery_date": "2026-12-01",
        "notes": "Rush order",
    }


class TestTasksEndpoints:
    """Test suite for task endpoints."""

    def test_get_tasks_empty_initially(self, client, clean_state):
        """Test that no tasks exist before any are created."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client, clean_state):
        """Test creating a task returns it as pending with all fields."""
        response = client.post(
            "/api/tasks",
            json={"title": "  Call supplier  ", "priority": "high", "dueDate": "2026-11-20"},
        )
        assert response.status_code == 201

        task = response.json()
        assert task["id"].startswith("task-")
        assert task["title"] == "Call supplier"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2026-11-20"
        assert task["status"] == "pending"

    def test_created_task_listed_newest_first(self, client, clean_state):
        """Test that the task list returns the most recently created task first."""
        client.post("/api/tasks", json={"title": "First", "priority": "low", "dueDate": "2026-11-01"})
        client.post("/api/tasks", json={"title": "Second", "priority": "low", "dueDate": "2026-11-02"})

        titles = [t["title"] for t in client.get("/api/tasks").json()]
        assert titles == ["Second", "First"]

    def test_create_task_rejects_invalid_priority(self, client, clean_state):
        """Test that an unknown priority is rejected with 422."""
        response = client.post(
            "/api/tasks",
            json={"title": "Bad", "priority": "urgent", "dueDate": "2026-11-20"},
        )
        assert response.status_code == 422

    def test_create_task_rejects_empty_title(self, client, clean_state):
        """Test that an empty title is rejected with 422."""
        response = client.post(
            "/api/tasks",
            json={"title": "", "priority": "low", "dueDate": "2026-11-20"},
        )
        assert response.status_code == 422

    def test_create_task_rejects_invalid_date(self, client, clean_state):
        """Test that a malformed due date is rejected with 422."""
        response = client.post(
            "/api/tasks",
            json={"title": "Bad date", "priority": "low", "dueDate": "not-a-date"},
        )
        assert response.status_code == 422

    def test_toggle_task_flips_status(self, client, clean_state):
        """Test that PATCH toggles pending to completed and back."""
        task_id = client.post(
            "/api/tasks", json={"title": "Toggle me", "priority": "medium", "dueDate": "2026-11-20"}
        ).json()["id"]

        first = client.patch(f"/api/tasks/{task_id}").json()
        assert first["status"] == "completed"

        second = client.patch(f"/api/tasks/{task_id}").json()
        assert second["status"] == "pending"

    def test_toggle_nonexistent_task(self, client, clean_state):
        """Test that toggling an unknown task returns 404."""
        response = client.patch("/api/tasks/task-missing")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_task(self, client, clean_state):
        """Test that a deleted task is no longer listed."""
        task_id = client.post(
            "/api/tasks", json={"title": "Delete me", "priority": "low", "dueDate": "2026-11-20"}
        ).json()["id"]

        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_delete_nonexistent_task(self, client, clean_state):
        """Test that deleting an unknown task returns 404."""
        response = client.delete("/api/tasks/task-missing")
        assert response.status_code == 404


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    def test_create_purchase_order(self, client, clean_state, backlog_item_without_po):
        """Test creating a purchase order for a backlog item."""
        response = client.post("/api/purchase-orders", json=_po_payload(backlog_item_without_po["id"]))
        assert response.status_code == 201

        po = response.json()
        assert po["id"].startswith("PO-")
        assert po["backlog_item_id"] == backlog_item_without_po["id"]
        assert po["supplier_name"] == "Acme Components"
        assert po["quantity"] == 50
        assert po["unit_cost"] == 12.5
        assert po["expected_delivery_date"] == "2026-12-01"
        assert po["status"] == "ordered"
        assert po["created_date"]
        assert po["notes"] == "Rush order"

    def test_created_po_marks_backlog_item(self, client, clean_state, backlog_item_without_po):
        """Test that the backlog endpoint reflects the new purchase order."""
        client.post("/api/purchase-orders", json=_po_payload(backlog_item_without_po["id"]))

        items = {item["id"]: item for item in client.get("/api/backlog").json()}
        assert items[backlog_item_without_po["id"]]["has_purchase_order"] is True

    def test_get_purchase_order_by_backlog_item(self, client, clean_state, backlog_item_without_po):
        """Test fetching the purchase order for a backlog item."""
        created = client.post(
            "/api/purchase-orders", json=_po_payload(backlog_item_without_po["id"])
        ).json()

        response = client.get(f"/api/purchase-orders/{backlog_item_without_po['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_purchase_order_when_none_exists(self, client, clean_state, backlog_item_without_po):
        """Test that a backlog item without a PO returns 404."""
        response = client.get(f"/api/purchase-orders/{backlog_item_without_po['id']}")
        assert response.status_code == 404
        assert "no purchase order" in response.json()["detail"].lower()

    def test_create_purchase_order_unknown_backlog_item(self, client, clean_state):
        """Test that a PO for an unknown backlog item returns 404."""
        response = client.post("/api/purchase-orders", json=_po_payload("backlog-missing"))
        assert response.status_code == 404

    def test_create_duplicate_purchase_order(self, client, clean_state, backlog_item_without_po):
        """Test that a second PO for the same backlog item returns 409."""
        payload = _po_payload(backlog_item_without_po["id"])
        assert client.post("/api/purchase-orders", json=payload).status_code == 201
        assert client.post("/api/purchase-orders", json=payload).status_code == 409

    @pytest.mark.parametrize(
        "field,value",
        [
            ("quantity", 0),
            ("quantity", -5),
            ("unit_cost", -1.0),
            ("supplier_name", ""),
            ("expected_delivery_date", "next week"),
        ],
    )
    def test_create_purchase_order_validation(
        self, client, clean_state, backlog_item_without_po, field, value
    ):
        """Test that invalid PO fields are rejected with 422."""
        payload = _po_payload(backlog_item_without_po["id"])
        payload[field] = value
        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 422
