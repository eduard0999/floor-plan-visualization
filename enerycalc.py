from __future__ import annotations
from typing import Dict, List, Tuple
from rooms import Room, RoomType, FloorPlan, Appliance

# --- Baseline assumptions (starter values; tweak as needed) ---
# Each entry: "Appliance": (watts, hours_per_day)
BASELINE_APPLIANCES: Dict[RoomType, Dict[str, Tuple[float, float]]] = {
    RoomType.KITCHEN: {
        "Fridge": (150, 24),
        "Oven": (1000, 1),
        "Microwave": (1200, 0.1),
        "Lights": (10, 4),
    },
    RoomType.BATHROOM: {
        "Lights": (10, 2),
        "Fan": (20, 0.5),
    },
    RoomType.BEDROOM: {
        "Lights": (8, 3),
        "Laptop": (60, 2),
    },
    RoomType.LIVING: {
        "TV": (100, 3),
        "Console/Set-top": (90, 2),
        "Lights": (10, 4),
    },
    RoomType.OFFICE: {
        "PC": (150, 8),
        "Monitor": (30, 8),
        "Lights": (10, 6),
    },
    RoomType.HALLWAY: {
        "Lights": (5, 2),
    },
    RoomType.UTILITY: {
        "Washer": (500, 0.3),
        "Dryer": (2500, 0.3),
        "Lights": (10, 1),
    },
}


def room_daily_kwh(room: Room) -> float:
    """Estimate daily kWh for a room using baseline + custom appliances, multiplied by usage_scale."""
    baseline = BASELINE_APPLIANCES.get(room.room_type, {})
    total_wh = 0.0

    # Baseline
    for watts, hours in baseline.values():
        total_wh += watts * hours

    # Custom appliances
    for a in room.custom_appliances:
        total_wh += a.watts * a.hours_per_day

    # Usage scale multiplier
    total_wh *= max(0.0, room.usage_scale)

    return total_wh / 1000.0  # Wh -> kWh


def floor_daily_kwh(fp: FloorPlan) -> float:
    return sum(room_daily_kwh(r) for r in fp.rooms)


def build_heatmap(fp: FloorPlan) -> List[List[float]]:
    """
    Returns a grid (grid_h x grid_w) with per-cell kWh/day.
    Distributes each room's daily kWh uniformly over its area.
    """
    grid = [[0.0 for _ in range(fp.grid_w)] for _ in range(fp.grid_h)]
    for r in fp.rooms:
        if r.gw <= 0 or r.gh <= 0:
            continue
        kwh = room_daily_kwh(r)
        per_cell = kwh / r.area_cells
        for y in range(r.gy, r.gy + r.gh):
            if y < 0 or y >= fp.grid_h:
                continue
            for x in range(r.gx, r.gx + r.gw):
                if x < 0 or x >= fp.grid_w:
                    continue
                grid[y][x] += per_cell
    return grid


def max_cell_value(grid: List[List[float]]) -> float:
    m = 0.0
    for row in grid:
        for v in row:
            if v > m:
                m = v
    return m