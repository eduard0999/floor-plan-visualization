
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional
import uuid
import json

class RoomType(Enum):
    KITCHEN = "Kitchen"
    BATHROOM = "Bathroom"
    BEDROOM = "Bedroom"
    LIVING = "Living Room"
    OFFICE = "Office"
    HALLWAY = "Hallway"
    UTILITY = "Utility"

ROOM_COLORS = {
    RoomType.KITCHEN: (250, 180, 60),
    RoomType.BATHROOM: (120, 200, 255),
    RoomType.BEDROOM: (180, 160, 255),
    RoomType.LIVING: (140, 220, 140),
    RoomType.OFFICE: (255, 130, 130),
    RoomType.HALLWAY: (210, 210, 210),
    RoomType.UTILITY: (200, 160, 120),
}

@dataclass
class Appliance:
    name: str
    watts: float
    hours_per_day: float

    def to_dict(self) -> Dict:
        return {"name": self.name, "watts": self.watts, "hours_per_day": self.hours_per_day}

    @staticmethod
    def from_dict(d: Dict) -> "Appliance":
        return Appliance(d["name"], float(d["watts"]), float(d["hours_per_day"]))

@dataclass
class Room:
    id: str
    room_type: RoomType
    gx: int  # grid x (left)
    gy: int  # grid y (top)
    gw: int  # grid width
    gh: int  # grid height
    usage_scale: float = 1.0
    custom_appliances: List[Appliance] = field(default_factory=list)
    # Optional per-room override for final kWh/day
    custom_kwh_per_day: Optional[float] = None

    @property
    def area_cells(self) -> int:
        return max(1, self.gw * self.gh)

    def contains_cell(self, cx: int, cy: int) -> bool:
        return (self.gx <= cx < self.gx + self.gw) and (self.gy <= cy < self.gy + self.gh)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "room_type": self.room_type.value,
            "gx": self.gx,
            "gy": self.gy,
            "gw": self.gw,
            "gh": self.gh,
            "usage_scale": self.usage_scale,
            "custom_appliances": [a.to_dict() for a in self.custom_appliances],
            "custom_kwh_per_day": self.custom_kwh_per_day,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Room":
        return Room(
            id=d.get("id", str(uuid.uuid4())),
            room_type=RoomType(d["room_type"]),
            gx=int(d["gx"]),
            gy=int(d["gy"]),
            gw=int(d["gw"]),
            gh=int(d["gh"]),
            usage_scale=float(d.get("usage_scale", 1.0)),
            custom_appliances=[Appliance.from_dict(a) for a in d.get("custom_appliances", [])],
            custom_kwh_per_day=(float(d["custom_kwh_per_day"]) if d.get("custom_kwh_per_day") is not None else None),
        )

class FloorPlan:
    def __init__(self, grid_w: int, grid_h: int):
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.rooms: List[Room] = []

    def add_room(self, room: Room):
        # Clamp to grid bounds
        room.gx = max(0, min(room.gx, self.grid_w - 1))
        room.gy = max(0, min(room.gy, self.grid_h - 1))
        room.gw = max(1, min(room.gw, self.grid_w - room.gx))
        room.gh = max(1, min(room.gh, self.grid_h - room.gy))
        self.rooms.append(room)

    def room_at(self, cx: int, cy: int) -> Optional[Room]:
        # Return the topmost room that contains the cell
        for room in reversed(self.rooms):
            if room.contains_cell(cx, cy):
                return room
        return None

    def remove_room(self, room_id: str) -> bool:
        before = len(self.rooms)
        self.rooms = [r for r in self.rooms if r.id != room_id]
        return len(self.rooms) != before

    def to_dict(self) -> Dict:
        return {
            "grid_w": self.grid_w,
            "grid_h": self.grid_h,
            "rooms": [r.to_dict() for r in self.rooms],
        }

    @staticmethod
    def from_dict(d: Dict) -> "FloorPlan":
        fp = FloorPlan(int(d["grid_w"]), int(d["grid_h"]))
        for rd in d.get("rooms", []):
            fp.rooms.append(Room.from_dict(rd))
        return fp

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path: str) -> "FloorPlan":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return FloorPlan.from_dict(d)
