"""
Tests for the budget-based restocking API endpoint and planner logic.
"""
import pytest

from restocking import build_restock_plan

PLAN_URL = "/api/restocking/plan"
VALID_STATUSES = {"funded", "partial", "unfunded"}
VALID_REASONS = {"below_reorder_point", "low_cover", "demand_increasing"}


class TestRestockingEndpoints:
    """Test suite for GET /api/restocking/plan."""

    def test_get_restocking_plan(self, client):
        """Test getting a plan returns the full structure."""
        response = client.get(f"{PLAN_URL}?budget=250000")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        for field in ["budget", "horizon_days", "total_allocated", "remaining_budget",
                      "total_needed", "funded_count", "partial_count", "unfunded_count", "items"]:
            assert field in data
        assert data["budget"] == 250000
        assert data["horizon_days"] == 30
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

    def test_restocking_item_structure(self, client):
        """Test that each recommendation has valid fields and types."""
        data = client.get(f"{PLAN_URL}?budget=250000").json()

        for item in data["items"]:
            assert item["status"] in VALID_STATUSES
            assert set(item["reasons"]) <= VALID_REASONS
            assert isinstance(item["recommended_qty"], int)
            assert isinstance(item["funded_qty"], int)
            assert item["recommended_qty"] > 0
            assert 0 <= item["funded_qty"] <= item["recommended_qty"]
            assert abs(item["cost"] - item["funded_qty"] * item["unit_cost"]) < 0.01
            assert abs(item["full_cost"] - item["recommended_qty"] * item["unit_cost"]) < 0.01

    def test_restocking_allocation_within_budget(self, client):
        """Test that allocated spend never exceeds the budget."""
        for budget in [1000, 50000, 250000, 1000000]:
            data = client.get(f"{PLAN_URL}?budget={budget}").json()

            assert data["total_allocated"] <= budget + 0.01
            assert abs(data["remaining_budget"] - (budget - data["total_allocated"])) < 0.01
            allocated = sum(item["cost"] for item in data["items"])
            assert abs(allocated - data["total_allocated"]) < 0.01

    def test_restocking_counts_match_items(self, client):
        """Test that status counts match the item list."""
        data = client.get(f"{PLAN_URL}?budget=1000000").json()

        statuses = [item["status"] for item in data["items"]]
        assert data["funded_count"] == statuses.count("funded")
        assert data["partial_count"] == statuses.count("partial")
        assert data["unfunded_count"] == statuses.count("unfunded")

    def test_restocking_priority_order(self, client):
        """Test that below-reorder items come first, then ascending days of cover."""
        items = client.get(f"{PLAN_URL}?budget=250000").json()["items"]

        assert [item["priority_rank"] for item in items] == list(range(1, len(items) + 1))

        below = [item["quantity_on_hand"] <= item["reorder_point"] for item in items]
        # Once an item is not below its reorder point, none after it may be
        assert below == sorted(below, reverse=True)

        for group in (True, False):
            covers = [item["days_of_cover"] for item, b in zip(items, below)
                      if b == group and item["days_of_cover"] is not None]
            assert covers == sorted(covers)

    def test_restocking_status_sequence(self, client):
        """Test that funded items precede at most one partial, then unfunded items."""
        for budget in [1000, 250000, 1000000]:
            items = client.get(f"{PLAN_URL}?budget={budget}").json()["items"]
            order = {"funded": 0, "partial": 1, "unfunded": 2}
            sequence = [order[item["status"]] for item in items]

            assert sequence == sorted(sequence)
            assert sequence.count(1) <= 1

    def test_restocking_huge_budget_funds_everything(self, client):
        """Test that a budget above total need funds every item fully."""
        data = client.get(f"{PLAN_URL}?budget=100000000").json()

        assert data["unfunded_count"] == 0
        assert data["partial_count"] == 0
        assert abs(data["total_allocated"] - data["total_needed"]) < 0.01
        for item in data["items"]:
            assert item["funded_qty"] == item["recommended_qty"]

    def test_restocking_tiny_budget_funds_nothing(self, client):
        """Test that a budget below every unit cost funds nothing."""
        data = client.get(f"{PLAN_URL}?budget=1").json()

        assert data["total_allocated"] == 0
        assert data["funded_count"] == 0
        assert data["partial_count"] == 0
        assert data["unfunded_count"] == len(data["items"])

    def test_restocking_longer_horizon_needs_more(self, client):
        """Test that a longer coverage horizon never reduces total need."""
        short = client.get(f"{PLAN_URL}?budget=1000&horizon_days=30").json()
        long = client.get(f"{PLAN_URL}?budget=1000&horizon_days=90").json()

        assert long["horizon_days"] == 90
        assert long["total_needed"] >= short["total_needed"]
        assert len(long["items"]) >= len(short["items"])

    def test_get_restocking_plan_by_warehouse(self, client):
        """Test filtering the plan by warehouse."""
        data = client.get(f"{PLAN_URL}?budget=250000&warehouse=Tokyo").json()

        assert len(data["items"]) > 0
        for item in data["items"]:
            assert item["warehouse"] == "Tokyo"

    def test_get_restocking_plan_by_category(self, client):
        """Test filtering the plan by category (case-insensitive)."""
        data = client.get(f"{PLAN_URL}?budget=250000&category=sensors").json()

        assert len(data["items"]) > 0
        for item in data["items"]:
            assert item["category"].lower() == "sensors"

    def test_get_restocking_plan_filter_all(self, client):
        """Test that 'all' filter values behave like no filter."""
        unfiltered = client.get(f"{PLAN_URL}?budget=250000").json()
        all_filters = client.get(f"{PLAN_URL}?budget=250000&warehouse=all&category=all").json()

        assert unfiltered == all_filters

    @pytest.mark.parametrize("query", [
        "",
        "?budget=0",
        "?budget=-100",
        "?budget=abc",
        "?budget=200000000",
        "?budget=1000&horizon_days=6",
        "?budget=1000&horizon_days=181",
    ])
    def test_restocking_invalid_params(self, client, query):
        """Test that missing or out-of-range parameters return 422."""
        response = client.get(f"{PLAN_URL}{query}")
        assert response.status_code == 422
        assert "detail" in response.json()


@pytest.fixture
def planner_inventory():
    """Small hand-built inventory for exact planner calculations."""
    return [
        {"sku": "A", "name": "Item A", "category": "Sensors", "warehouse": "Tokyo",
         "quantity_on_hand": 10, "reorder_point": 20, "unit_cost": 10.0},
        {"sku": "B", "name": "Item B", "category": "Sensors", "warehouse": "London",
         "quantity_on_hand": 100, "reorder_point": 20, "unit_cost": 5.0},
        {"sku": "C", "name": "Item C", "category": "Actuators", "warehouse": "Tokyo",
         "quantity_on_hand": 1000, "reorder_point": 20, "unit_cost": 1.0},
    ]


@pytest.fixture
def planner_orders():
    """Orders giving A 1 unit/day and B 2 units/day over a 90-day window."""
    return [
        {"order_date": "2025-12-31T00:00:00", "items": [{"sku": "A", "quantity": 90}, {"sku": "B", "quantity": 180}]},
        # Outside the 90-day window: must be ignored
        {"order_date": "2025-01-01T00:00:00", "items": [{"sku": "A", "quantity": 9999}]},
    ]


class TestRestockPlanner:
    """Unit tests for build_restock_plan with exact expected values."""

    def test_planner_quantities_and_ranking(self, planner_inventory, planner_orders):
        """Test demand, quantities, ranking and skip of well-stocked items."""
        plan = build_restock_plan(planner_inventory, planner_orders, [], budget=10000, horizon_days=30)
        items = {i["sku"]: i for i in plan["items"]}

        # A: 1/day * 30 + 20 - 10 = 40 units; B: 2/day * 30 + 20 - 100 = -20 -> skipped
        # C: no demand, 1000 on hand > reorder point -> skipped
        assert list(items) == ["A"]
        assert items["A"]["daily_demand"] == 1.0
        assert items["A"]["days_of_cover"] == 10.0
        assert items["A"]["recommended_qty"] == 40
        assert items["A"]["reasons"] == ["below_reorder_point", "low_cover"]
        assert plan["total_needed"] == 400.0

    def test_planner_partial_funding(self, planner_inventory, planner_orders):
        """Test that the first unaffordable item receives whole units only."""
        plan = build_restock_plan(planner_inventory, planner_orders, [], budget=255, horizon_days=30)
        item = plan["items"][0]

        assert item["status"] == "partial"
        assert item["funded_qty"] == 25
        assert item["cost"] == 250.0
        assert plan["remaining_budget"] == 5.0

    def test_planner_forecast_trend_adjustment(self, planner_inventory, planner_orders):
        """Test that a matching forecast scales demand and adds a reason."""
        forecasts = [{"item_sku": "A", "current_demand": 100, "forecasted_demand": 150, "trend": "increasing"}]
        plan = build_restock_plan(planner_inventory, planner_orders, forecasts, budget=10000, horizon_days=30)
        item = plan["items"][0]

        # 1.5/day * 30 + 20 - 10 = 55
        assert item["daily_demand"] == 1.5
        assert item["recommended_qty"] == 55
        assert "demand_increasing" in item["reasons"]

    def test_planner_no_demand_below_reorder(self, planner_inventory):
        """Test that an item with no orders is restocked up to its reorder point."""
        plan = build_restock_plan(planner_inventory, [], [], budget=10000, horizon_days=30)
        items = {i["sku"]: i for i in plan["items"]}

        assert list(items) == ["A"]
        assert items["A"]["days_of_cover"] is None
        assert items["A"]["recommended_qty"] == 10
        assert items["A"]["reasons"] == ["below_reorder_point"]

    def test_planner_partial_funding_exact_cents(self, planner_orders):
        """Test that partial quantities use exact cents (0.30 / 0.10 buys 3, not 2)."""
        inventory = [{"sku": "A", "name": "Item A", "category": "Sensors", "warehouse": "Tokyo",
                      "quantity_on_hand": 10, "reorder_point": 20, "unit_cost": 0.1}]
        plan = build_restock_plan(inventory, planner_orders, [], budget=0.3, horizon_days=30)
        item = plan["items"][0]

        assert item["status"] == "partial"
        assert item["funded_qty"] == 3
        assert plan["total_allocated"] <= 0.3

    def test_planner_does_not_mutate_inputs(self, planner_inventory, planner_orders):
        """Test that the planner leaves the source data untouched."""
        before = [dict(i) for i in planner_inventory]
        build_restock_plan(planner_inventory, planner_orders, [], budget=255)
        assert planner_inventory == before
