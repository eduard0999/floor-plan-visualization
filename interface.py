
from __future__ import annotations
import pygame
from pygame import Surface, SRCALPHA
from typing import Optional, Tuple
import uuid

from rooms import Room, RoomType, FloorPlan, ROOM_COLORS
from enerycalc import build_heatmap, max_cell_value, floor_daily_kwh, room_daily_kwh

class EnergyVisualizerApp:
    def __init__(self, screen: Surface, grid_w: int = 40, grid_h: int = 25, cell_px: int = 24):
        self.screen = screen
        self.W, self.H = screen.get_size()
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.cell_px = cell_px
        self.margin_left = 16
        self.margin_top = 16

        self.fp = FloorPlan(grid_w, grid_h)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16)

        # UI state
        self.current_room_type = RoomType.KITCHEN
        self.show_grid = True
        self.show_heatmap = True
        self.dragging = False
        self.drag_start_cell: Optional[Tuple[int, int]] = None
        self.selected_room: Optional[Room] = None
        self.heatmap_cache = None  # (grid, max) cached per frame if needed

        # Numeric input for per-room kWh/day override
        self.kwh_input_active = False
        self.kwh_input_buffer = ""

    # ---------- Utility ----------
    def cell_to_px(self, cx: int, cy: int) -> Tuple[int, int]:
        x = self.margin_left + cx * self.cell_px
        y = self.margin_top + cy * self.cell_px
        return x, y

    def px_to_cell(self, px: int, py: int) -> Tuple[int, int]:
        cx = (px - self.margin_left) // self.cell_px
        cy = (py - self.margin_top) // self.cell_px
        return int(cx), int(cy)

    def grid_rect_px(self) -> pygame.Rect:
        return pygame.Rect(
            self.margin_left,
            self.margin_top,
            self.grid_w * self.cell_px,
            self.grid_h * self.cell_px
        )

    # ---------- Drawing ----------
    def draw_grid(self):
        if not self.show_grid:
            return
        rect = self.grid_rect_px()
        color = (70, 70, 70)
        # Outer border
        pygame.draw.rect(self.screen, (110, 110, 110), rect, 1)
        # Grid lines
        for x in range(self.grid_w + 1):
            px = self.margin_left + x * self.cell_px
            pygame.draw.line(self.screen, color, (px, rect.top), (px, rect.bottom), 1)
        for y in range(self.grid_h + 1):
            py = self.margin_top + y * self.cell_px
            pygame.draw.line(self.screen, color, (rect.left, py), (rect.right, py), 1)

    def draw_rooms(self):
        for r in self.fp.rooms:
            x, y = self.cell_to_px(r.gx, r.gy)
            w = r.gw * self.cell_px
            h = r.gh * self.cell_px
            base = ROOM_COLORS.get(r.room_type, (180, 180, 180))
            pygame.draw.rect(self.screen, base, (x, y, w, h))
            pygame.draw.rect(self.screen, (40, 40, 40), (x, y, w, h), 2)

            # Room label
            label = f"{r.room_type.value}"
            kwh = room_daily_kwh(r)
            if r.custom_kwh_per_day is not None:
                label2 = f"{kwh:.2f} kWh/d (custom)"
            else:
                label2 = f"{kwh:.2f} kWh/d x{r.usage_scale:.2f}"
            txt = self.font.render(label, True, (15, 15, 15))
            txt2 = self.font.render(label2, True, (15, 15, 15))
            self.screen.blit(txt, (x + 6, y + 4))
            self.screen.blit(txt2, (x + 6, y + 22))

            # Selection outline
            if self.selected_room and self.selected_room.id == r.id:
                pygame.draw.rect(self.screen, (255, 255, 0), (x - 2, y - 2, w + 4, h + 4), 2)

    def draw_drag_preview(self):
        if not self.dragging or self.drag_start_cell is None:
            return
        mx, my = pygame.mouse.get_pos()
        cx, cy = self.px_to_cell(mx, my)
        sx, sy = self.drag_start_cell
        gx = min(sx, cx)
        gy = min(sy, cy)
        gw = abs(cx - sx) + 1
        gh = abs(cy - sy) + 1
        x, y = self.cell_to_px(gx, gy)
        w = gw * self.cell_px
        h = gh * self.cell_px
        color = ROOM_COLORS.get(self.current_room_type, (200, 200, 200))
        pygame.draw.rect(self.screen, color, (x, y, w, h), 0)
        pygame.draw.rect(self.screen, (255, 255, 255), (x, y, w, h), 2)

    def draw_heatmap(self):
        if not self.show_heatmap:
            return
        rect = self.grid_rect_px()
        overlay = pygame.Surface((rect.width, rect.height), SRCALPHA)
        grid = build_heatmap(self.fp)
        m = max_cell_value(grid)
        if m <= 1e-9:
            return
        for y in range(self.grid_h):
            for x in range(self.grid_w):
                v = grid[y][x] / m  # normalize 0..1
                color = self.value_to_color(v, alpha=140)
                rx = x * self.cell_px
                ry = y * self.cell_px
                pygame.draw.rect(overlay, color, (rx, ry, self.cell_px, self.cell_px))
        self.screen.blit(overlay, (self.margin_left, self.margin_top))

    def draw_hud(self):
        total = floor_daily_kwh(self.fp)
        lines = [
            f"[1-7] Type: {self.current_room_type.value}",
            "[LClick-Drag] Add room, [RClick] Delete room under cursor",
            "[H] Heatmap  [G] Grid  [S] Save  [L] Load",
            "[Click room to select]  [ [ / ] ] Usage scale",
            "[E] Edit kWh/day (custom override)   [C] Clear override",
            f"Rooms: {len(self.fp.rooms)}   Total: {total:.2f} kWh/day",
        ]
        y = 8
        for line in lines:
            txt = self.font.render(line, True, (235, 235, 235))
            self.screen.blit(txt, (8, y))
            y += 18

    # ---------- Color mapping ----------
    def value_to_color(self, t: float, alpha: int = 180) -> Tuple[int, int, int, int]:
        """Blue (cool) -> Yellow -> Red (hot) gradient for heatmap."""
        t = max(0.0, min(1.0, t))
        # Blue (0,0,255) -> Yellow (255,255,0) -> Red (255,0,0)
        if t < 0.5:
            k = t / 0.5  # 0..1
            r = int(255 * k)
            g = int(255 * k)
            b = int(255 - 255 * k)
        else:
            k = (t - 0.5) / 0.5
            r = 255
            g = int(255 - 255 * k)
            b = 0
        return (r, g, b, alpha)

    # ---------- Numeric input helpers ----------
    def start_kwh_input(self):
        if self.selected_room:
            self.kwh_input_active = True
            self.kwh_input_buffer = ""

    def commit_kwh_input(self):
        if self.selected_room and self.kwh_input_active:
            txt = self.kwh_input_buffer.strip()
            try:
                val = float(txt)
                self.selected_room.custom_kwh_per_day = max(0.0, val)
            except ValueError:
                pass
        self.kwh_input_active = False
        self.kwh_input_buffer = ""

    # ---------- Events ----------
    def handle_mouse_down(self, event: pygame.event.Event):
        if event.button == 1:  # left: start drag or select
            cx, cy = self.px_to_cell(*event.pos)
            if 0 <= cx < self.grid_w and 0 <= cy < self.grid_h:
                self.dragging = True
                self.drag_start_cell = (cx, cy)
                # Also select the topmost room under cursor (if any)
                self.selected_room = self.fp.room_at(cx, cy)
        elif event.button == 3:  # right: delete room under cursor
            cx, cy = self.px_to_cell(*event.pos)
            r = self.fp.room_at(cx, cy)
            if r:
                self.fp.remove_room(r.id)
            if self.selected_room and r and self.selected_room.id == r.id:
                self.selected_room = None

    def handle_mouse_up(self, event: pygame.event.Event):
        if event.button != 1:
            return
        if not self.dragging or self.drag_start_cell is None:
            return
        mx, my = event.pos
        cx, cy = self.px_to_cell(mx, my)
        sx, sy = self.drag_start_cell
        gx = min(sx, cx)
        gy = min(sy, cy)
        gw = abs(cx - sx) + 1
        gh = abs(cy - sy) + 1
        # Only add if inside grid
        if gx < self.grid_w and gy < self.grid_h and gx >= 0 and gy >= 0:
            new_room = Room(
                id=str(uuid.uuid4()),
                room_type=self.current_room_type,
                gx=gx,
                gy=gy,
                gw=gw,
                gh=gh,
            )
            self.fp.add_room(new_room)
            self.selected_room = new_room
        self.dragging = False
        self.drag_start_cell = None

    def handle_keydown(self, event: pygame.event.Event):
        # If editing kWh/day, capture numeric input first
        if self.kwh_input_active:
            if event.key == pygame.K_RETURN:
                self.commit_kwh_input()
                return
            elif event.key == pygame.K_ESCAPE:
                self.kwh_input_active = False
                self.kwh_input_buffer = ""
                return
            elif event.key == pygame.K_BACKSPACE:
                self.kwh_input_buffer = self.kwh_input_buffer[:-1]
                return
            else:
                ch = event.unicode
                if ch and (ch.isdigit() or ch in "."):
                    self.kwh_input_buffer += ch
                return

        # Normal shortcuts
        if event.key == pygame.K_h:
            self.show_heatmap = not self.show_heatmap

        elif event.key == pygame.K_g:
            self.show_grid = not self.show_grid

        elif event.key == pygame.K_s:
            self.fp.save("floorplan.json")
            print("Saved to floorplan.json")

        elif event.key == pygame.K_l:
            try:
                self.fp = FloorPlan.load("floorplan.json")
                print("Loaded floorplan.json")
                self.selected_room = None
            except Exception as e:
                print("Failed to load floorplan.json:", e)

        # Room type shortcuts 1..7
        elif event.key == pygame.K_1:
            self.current_room_type = RoomType.KITCHEN
        elif event.key == pygame.K_2:
            self.current_room_type = RoomType.BATHROOM
        elif event.key == pygame.K_3:
            self.current_room_type = RoomType.BEDROOM
        elif event.key == pygame.K_4:
            self.current_room_type = RoomType.LIVING
        elif event.key == pygame.K_5:
            self.current_room_type = RoomType.OFFICE
        elif event.key == pygame.K_6:
            self.current_room_type = RoomType.HALLWAY
        elif event.key == pygame.K_7:
            self.current_room_type = RoomType.UTILITY

        # Usage scale adjust on selected room
        elif event.key == pygame.K_LEFTBRACKET:  # '['
            if self.selected_room:
                self.selected_room.usage_scale = max(
                    0.25, round(self.selected_room.usage_scale - 0.25, 2)
                )

        elif event.key == pygame.K_RIGHTBRACKET:  # ']'
            if self.selected_room:
                self.selected_room.usage_scale = min(
                    4.0, round(self.selected_room.usage_scale + 0.25, 2)
                )

        # Edit / Clear per-room kWh/day override
        elif event.key == pygame.K_e:
            self.start_kwh_input()

        elif event.key == pygame.K_c:
            if self.selected_room:
                self.selected_room.custom_kwh_per_day = None

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_down(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self.handle_mouse_up(event)
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event)
        return True

    def update(self, dt: float):
        pass  # Placeholder for future real-time updates

    def render(self):
        self.screen.fill((28, 28, 35))
        self.draw_heatmap()
        self.draw_rooms()
        self.draw_drag_preview()
        self.draw_grid()
        self.draw_hud()

        # Input prompt while editing kWh/day
        if self.kwh_input_active and self.selected_room:
            prompt = f"Set kWh/day for {self.selected_room.room_type.value}: {self.kwh_input_buffer}"
            overlay = self.font.render(prompt, True, (255, 220, 150))
            self.screen.blit(overlay, (8, self.H - 28))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            running = self.handle_events()
            self.update(dt)
            self.render()
