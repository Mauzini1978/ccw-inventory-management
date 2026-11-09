"""
Budget-constrained restocking planner.

Pure logic (no FastAPI imports) so it can be unit tested with small fixtures.

Demand signal: average daily units ordered over a trailing window that ends at the
latest order date in the data (not "today"), so results are stable for mock data.
If a demand forecast exists for a SKU, demand is scaled by its trend
(forecasted_demand / current_demand).

Allocation: items are ranked by urgency and funded greedily. The first item that
does not fully fit gets as many whole units as the remaining budget buys
("partial"); every item after that is "unfunded".
"""
import math
from datetime import datetime, timedelta
from typing import Optional

from filters import apply_filters

DEMAND_WINDOW_DAYS = 90


def _parse_date(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def compute_daily_demand(orders: list, window_days: int = DEMAND_WINDOW_DAYS) -> dict:
    """Return {sku: average units per day} over the trailing window of order history."""
    dated = [(d, o) for o in orders if (d := _parse_date(o.get('order_date'))) is not None]
    if not dated:
        return {}

    anchor = max(d for d, _ in dated)
    window_start = anchor - timedelta(days=window_days)

    units: dict = {}
    for order_date, order in dated:
        if order_date <= window_start:
            continue
        for item in order.get('items', []):
            sku = item.get('sku')
            if sku:
                units[sku] = units.get(sku, 0) + (item.get('quantity') or 0)

    return {sku: qty / window_days for sku, qty in units.items()}


def _forecast_factors(forecasts: list) -> dict:
    """Return {sku: (factor, trend)} for forecasts with a usable current_demand."""
    factors = {}
    for f in forecasts:
        current = f.get('current_demand') or 0
        if current > 0:
            factors[f['item_sku']] = (f.get('forecasted_demand', current) / current, f.get('trend'))
    return factors


def build_restock_plan(inventory: list, orders: list, forecasts: list, budget: float,
                       horizon_days: int = 30, warehouse: Optional[str] = None,
                       category: Optional[str] = None) -> dict:
    """Build a prioritised, budget-constrained restock plan."""
    items = apply_filters(inventory, warehouse, category)
    daily_demand = compute_daily_demand(orders)
    factors = _forecast_factors(forecasts)

    candidates = []
    for item in items:
        sku = item['sku']
        demand = daily_demand.get(sku, 0.0)
        factor, trend = factors.get(sku, (1.0, None))
        demand *= factor

        on_hand = item['quantity_on_hand']
        reorder_point = item['reorder_point']
        # Round before ceil so float noise (e.g. 5.0000000001) can't add a phantom unit
        needed = math.ceil(round(demand * horizon_days + reorder_point - on_hand, 6))
        if needed <= 0:
            continue

        days_of_cover = on_hand / demand if demand > 0 else None
        below_reorder = on_hand <= reorder_point

        reasons = []
        if below_reorder:
            reasons.append('below_reorder_point')
        if days_of_cover is not None and days_of_cover < horizon_days:
            reasons.append('low_cover')
        if trend == 'increasing':
            reasons.append('demand_increasing')

        candidates.append({
            'sku': sku,
            'name': item['name'],
            'category': item['category'],
            'warehouse': item['warehouse'],
            'quantity_on_hand': on_hand,
            'reorder_point': reorder_point,
            'unit_cost': item['unit_cost'],
            'daily_demand': round(demand, 2),
            'days_of_cover': round(days_of_cover, 1) if days_of_cover is not None else None,
            'recommended_qty': needed,
            'reasons': reasons,
            '_below_reorder': below_reorder,
            '_cover_sort': days_of_cover if days_of_cover is not None else math.inf,
            '_demand_sort': demand,
        })

    candidates.sort(key=lambda c: (not c['_below_reorder'], c['_cover_sort'], -c['_demand_sort'], c['sku']))

    remaining = float(budget)
    funding_stopped = False
    total_needed = 0.0
    counts = {'funded': 0, 'partial': 0, 'unfunded': 0}
    result_items = []

    for rank, c in enumerate(candidates, start=1):
        unit_cost = c['unit_cost']
        full_cost = c['recommended_qty'] * unit_cost
        total_needed += full_cost

        if not funding_stopped and full_cost <= remaining + 1e-9:
            status, funded_qty = 'funded', c['recommended_qty']
        elif not funding_stopped:
            funding_stopped = True
            # Integer cents avoid float floor errors (0.3 // 0.1 == 2.0)
            cost_cents = round(unit_cost * 100)
            remaining_cents = math.floor(remaining * 100 + 1e-6)  # round down: never spend money we don't have
            funded_qty = remaining_cents // cost_cents if cost_cents > 0 else 0
            status = 'partial' if funded_qty >= 1 else 'unfunded'
        else:
            status, funded_qty = 'unfunded', 0

        cost = round(funded_qty * unit_cost, 2)
        remaining -= cost
        counts[status] += 1

        entry = {k: v for k, v in c.items() if not k.startswith('_')}
        entry.update({
            'priority_rank': rank,
            'status': status,
            'funded_qty': funded_qty,
            'cost': cost,
            'full_cost': round(full_cost, 2),
        })
        result_items.append(entry)

    total_allocated = round(sum(i['cost'] for i in result_items), 2)

    return {
        'budget': round(float(budget), 2),
        'horizon_days': horizon_days,
        'total_allocated': total_allocated,
        'remaining_budget': round(float(budget) - total_allocated, 2),
        'total_needed': round(total_needed, 2),
        'funded_count': counts['funded'],
        'partial_count': counts['partial'],
        'unfunded_count': counts['unfunded'],
        'items': result_items,
    }
