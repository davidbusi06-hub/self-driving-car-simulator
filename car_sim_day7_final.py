import pygame
import sys
import math
import random

import os
os.environ['SDL_VIDEO_ALLOW_SCREENSAVER'] = '1'

pygame.init()
pygame.display.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Self-Driving Car Simulator - Day 7 Final")
# Keyboard-only exit (Q key)
clock = pygame.time.Clock()
font       = pygame.font.SysFont(None, 28)
font_large = pygame.font.SysFont(None, 52)
font_small = pygame.font.SysFont(None, 22)

BLACK  = (0,   0,   0)
GREEN  = (0, 200,  80)
RED    = (220,  50,  50)
BLUE   = (50, 120, 220)
GRAY   = (80,  80,  80)
DARK   = (20,  20,  20)
WHITE  = (255,255,255)
YELLOW = (255,220,  0)
ORANGE = (255,140,  0)
CYAN   = (0,  200, 200)
PURPLE = (160, 60, 220)
LIME   = (120, 255,  0)

CP_COLORS = [CYAN, YELLOW, ORANGE, PURPLE]

WIDTH  = 800
HEIGHT = 600
MARGIN = 35  # safe zone — car center stays at least 35px from screen edge
GRID   = 40  # visited-cell grid size (matches background grid)


def gen_obstacles():
    obs = []
    PAD = MARGIN + 10  # keep obstacles fully inside safe zone
    for _ in range(6):
        for _ in range(200):
            w = random.randint(50, 110)
            h = random.randint(35,  90)
            # clamp so entire rect stays on screen
            x = random.randint(PAD, max(PAD + 1, WIDTH  - w - PAD))
            y = random.randint(PAD, max(PAD + 1, HEIGHT - h - PAD))
            r = pygame.Rect(x, y, w, h)
            # must be fully inside screen
            if r.left < PAD or r.right > WIDTH-PAD or r.top < PAD or r.bottom > HEIGHT-PAD:
                continue
            # keep clear of car start zone
            if r.inflate(30, 30).colliderect(pygame.Rect(55, 55, 130, 130)):
                continue
            # no overlap with other obstacles
            if any(r.inflate(20, 20).colliderect(o) for o in obs):
                continue
            obs.append(r)
            break
    return obs


def gen_checkpoints(obs):
    """
    Spawn exactly 4 checkpoints, one per quadrant.
    Each quadrant has a tightly inset safe zone — checkpoints are
    always well within visible screen bounds.
    """
    cps = []
    CP_W, CP_H = 58, 22        # fixed size — no randomness that breaks bounds
    PAD = 80                    # large inset: 80px from every screen edge

    MX, MY = WIDTH // 2, HEIGHT // 2
    # Each quadrant is inset PAD from screen edges AND 30px from centre lines
    safe_zones = [
        (PAD,      MX - 30,   PAD,      MY - 30),   # top-left
        (MX + 30,  WIDTH-PAD, PAD,      MY - 30),   # top-right
        (PAD,      MX - 30,   MY + 30,  HEIGHT-PAD),# bottom-left
        (MX + 30,  WIDTH-PAD, MY + 30,  HEIGHT-PAD),# bottom-right
    ]

    for (x1, x2, y1, y2) in safe_zones:
        # These bounds already guarantee on-screen placement.
        # x range for left edge: x1 .. x2-CP_W  (so right edge = x1+CP_W .. x2)
        # y range for top  edge: y1 .. y2-CP_H
        rx1 = x1
        rx2 = x2 - CP_W
        ry1 = y1
        ry2 = y2 - CP_H

        # Safety: if zone is too small just use centre
        if rx2 < rx1: rx2 = rx1
        if ry2 < ry1: ry2 = ry1

        placed = False
        for _ in range(600):
            x = random.randint(rx1, rx2)
            y = random.randint(ry1, ry2)
            r = pygame.Rect(x, y, CP_W, CP_H)
            # paranoid explicit bounds check
            if r.left < PAD or r.right > WIDTH-PAD or r.top < PAD or r.bottom > HEIGHT-PAD:
                continue
            if r.inflate(8, 8).colliderect(pygame.Rect(50, 50, 140, 140)):
                continue
            if any(r.inflate(6, 6).colliderect(o) for o in obs):
                continue
            cps.append(r)
            placed = True
            break

        if not placed:
            # Grid walk — 10px steps inside safe zone
            for gx in range(rx1, rx2+1, 10):
                for gy in range(ry1, ry2+1, 10):
                    r = pygame.Rect(gx, gy, CP_W, CP_H)
                    if r.left < PAD or r.right > WIDTH-PAD or r.top < PAD or r.bottom > HEIGHT-PAD:
                        continue
                    if not any(r.inflate(4,4).colliderect(o) for o in obs):
                        cps.append(r)
                        placed = True
                        break
                if placed:
                    break

        if not placed:
            # Nuclear: centre of safe zone, clamp, shrink any blocking obstacle
            cx = (rx1 + rx2) // 2
            cy = (ry1 + ry2) // 2
            cx = max(PAD, min(WIDTH-PAD-CP_W, cx))
            cy = max(PAD, min(HEIGHT-PAD-CP_H, cy))
            r  = pygame.Rect(cx, cy, CP_W, CP_H)
            for o in obs:
                if r.inflate(4,4).colliderect(o):
                    o.width  = max(6, o.width  - 50)
                    o.height = max(6, o.height - 50)
            cps.append(r)

    return cps


class Car:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = 100.0
        self.y = 100.0
        self.angle = 0.0
        self.speed = 0.0
        self.max_speed = 5.0
        self.status = "Manual"
        self.mode = "manual"
        self.current_steer   = 0.0
        self.next_cp         = 0
        self.total_distance  = 0.0
        self.destination_reached = False
        # steering state
        self.steer_hold_timer  = 0
        self.held_steer        = 0.0
        # stuck detection
        self.stuck_counter     = 0
        self.last_x            = self.x
        self.last_y            = self.y
        # loop escape
        self.path_history      = []
        self.loop_escape_timer = 0
        self.loop_escape_angle = 0.0
        # reverse: ONLY used as absolute last resort, capped short
        self.reverse_timer     = 0
        self.reverse_dir       = 1
        # visited grid memory
        self.visited_cells     = set()
        self.visit_timer       = 0  # record a cell every N frames
        # ordered path log for replaying known routes
        self.path_log          = []   # list of (x, y) every 25 frames
        self.path_log_timer    = 0
        self.replaying_path    = False
        self.replay_waypoint   = 0    # index into path_log we're heading toward

    def get_rect(self):
        d = math.hypot(20,15)
        return pygame.Rect(self.x-d, self.y-d, d*2, d*2)

    def collides_anything(self, obs):
        r = self.get_rect()
        if self.x < MARGIN or self.x > WIDTH-MARGIN or self.y < MARGIN or self.y > HEIGHT-MARGIN:
            return True
        return any(r.colliderect(o) for o in obs)

    def clamp_to_screen(self):
        """Hard clamp — car center can never leave the safe zone regardless of speed."""
        self.x = max(MARGIN, min(WIDTH-MARGIN,  self.x))
        self.y = max(MARGIN, min(HEIGHT-MARGIN, self.y))

    def check_checkpoints(self, cps):
        if self.destination_reached or not cps:
            return
        if self.get_rect().colliderect(cps[self.next_cp]):
            self.next_cp += 1
            if self.next_cp >= len(cps):
                self.destination_reached = True

    def cast_ray(self, ray_angle, obs):
        ca = math.cos(math.radians(ray_angle))
        sa = math.sin(math.radians(ray_angle))
        for d in range(1, 201):
            rx = self.x + d*ca
            ry = self.y - d*sa
            if rx < 0 or rx > WIDTH or ry < 0 or ry > HEIGHT:
                return (rx,ry), d
            if any(o.collidepoint(rx,ry) for o in obs):
                return (rx,ry), d
        return (self.x+200*ca, self.y-200*sa), 200

    def get_sensor_data(self, obs):
        # 9 rays: front-facing fan + sides
        angles = [-90, -60, -35, -15, 0, 15, 35, 60, 90]
        rays, dists = [], []
        for off in angles:
            ep, d = self.cast_ray(self.angle+off, obs)
            rays.append(ep)
            dists.append(d)
        return rays, dists

    def angle_to_checkpoint(self, cps):
        if not cps:
            return 0.0
        cp = cps[self.next_cp]
        cx = cp.x + cp.width/2
        cy = cp.y + cp.height/2
        dx = cx - self.x
        dy = -(cy - self.y)
        target = math.degrees(math.atan2(dy, dx))
        diff = (target - self.angle + 360) % 360
        if diff > 180:
            diff -= 360
        return diff

    def dist_to_checkpoint(self, cps):
        if not cps:
            return 9999
        cp = cps[self.next_cp]
        cx = cp.x + cp.width/2
        cy = cp.y + cp.height/2
        return math.hypot(cx - self.x, cy - self.y)

    def best_turn_direction(self, dists, cps):
        cp_diff = self.angle_to_checkpoint(cps)
        left_clear  = dists[0] + dists[1] + dists[2]
        right_clear = dists[6] + dists[7] + dists[8]
        if cp_diff > 0:
            return 1 if left_clear > right_clear * 0.55 else -1
        else:
            return -1 if right_clear > left_clear * 0.55 else 1

    def gap_clearance(self, obs):
        """Cast 90-deg side rays. Returns (left_d, right_d, gap, passable)."""
        MIN_PASS = 44
        _, left_d  = self.cast_ray(self.angle + 90, obs)
        _, right_d = self.cast_ray(self.angle - 90, obs)
        gap = left_d + right_d
        return left_d, right_d, gap, gap >= MIN_PASS

    def score_heading(self, heading_offset, obs, cps):
        """Score a candidate heading: prioritise open space, unvisited cells, then CP alignment."""
        test_angle = self.angle + heading_offset
        # cast 5 rays in a fan around this heading for a wide openness reading
        _, f0 = self.cast_ray(test_angle - 30, obs)
        _, f1 = self.cast_ray(test_angle - 15, obs)
        _, f2 = self.cast_ray(test_angle,      obs)
        _, f3 = self.cast_ray(test_angle + 15, obs)
        _, f4 = self.cast_ray(test_angle + 30, obs)
        openness  = f0*0.5 + f1*0.75 + f2*1.0 + f3*0.75 + f4*0.5  # weighted fan
        # CP alignment
        cp_diff   = self.angle_to_checkpoint(cps)
        alignment = max(0, 1 - abs(heading_offset - cp_diff) / 180)
        # visited penalty
        penalty   = self.visited_penalty(heading_offset, cps)
        # openness is the primary driver, CP alignment secondary
        return openness * 1.0 + alignment * 60 + penalty



    def move(self):
        self.x += self.speed * math.cos(math.radians(self.angle))
        self.y -= self.speed * math.sin(math.radians(self.angle))
        self.total_distance += abs(self.speed)

    def apply_steering(self, target, smoothing=0.18):
        self.current_steer = (1 - smoothing) * self.current_steer + smoothing * target
        self.angle += self.current_steer


    def cell_at(self, x, y):
        return (int(x) // GRID, int(y) // GRID)

    def mark_visited(self):
        """Record current grid cell as visited."""
        self.visited_cells.add(self.cell_at(self.x, self.y))

    def visited_penalty(self, heading_offset, cps):
        """
        Look ahead ~60px in the given heading and check if that cell was visited.
        Returns a penalty score (negative = bad, 0 = fine).
        Skip penalty if that cell contains the next checkpoint.
        """
        test_angle = self.angle + heading_offset
        lx = self.x + 60 * math.cos(math.radians(test_angle))
        ly = self.y - 60 * math.sin(math.radians(test_angle))
        cell = self.cell_at(lx, ly)
        if cell not in self.visited_cells:
            return 0
        # don't penalise if this is the checkpoint cell
        if cps and self.next_cp < len(cps):
            cp = cps[self.next_cp]
            cp_cell = self.cell_at(cp.x + cp.width/2, cp.y + cp.height/2)
            if cell == cp_cell:
                return 0
        return -60  # strong penalty for revisiting


    def simulate_path(self, start_angle, obs, steps=5, step_dist=20):
        """
        Simulate driving forward from current position at a given heading.
        Returns (total_clearance, survived_steps, final_x, final_y).
        Does NOT modify car state.
        """
        sx, sy = self.x, self.y
        angle  = start_angle
        total_clear = 0
        survived    = 0
        for _ in range(steps):
            nx = sx + step_dist * math.cos(math.radians(angle))
            ny = sy - step_dist * math.sin(math.radians(angle))
            # check bounds
            if nx < MARGIN or nx > WIDTH-MARGIN or ny < MARGIN or ny > HEIGHT-MARGIN:
                break
            # check obstacle collision at new point
            test_r = pygame.Rect(nx-18, ny-18, 36, 36)
            if any(test_r.colliderect(o) for o in obs):
                break
            # measure lateral clearance at this step
            _, lc = self.cast_ray_from(nx, ny, angle + 90,  obs, max_d=60)
            _, rc = self.cast_ray_from(nx, ny, angle - 90,  obs, max_d=60)
            _, fc = self.cast_ray_from(nx, ny, angle,       obs, max_d=80)
            total_clear += lc + rc + fc * 1.5
            sx, sy = nx, ny
            survived += 1
        return total_clear, survived, sx, sy

    def cast_ray_from(self, fx, fy, ray_angle, obs, max_d=150):
        """Cast a ray from an arbitrary point (used by lookahead)."""
        ca = math.cos(math.radians(ray_angle))
        sa = math.sin(math.radians(ray_angle))
        for d in range(1, max_d+1):
            rx = fx + d * ca
            ry = fy - d * sa
            if rx < 0 or rx > WIDTH or ry < 0 or ry > HEIGHT:
                return (rx, ry), d
            if any(o.collidepoint(rx, ry) for o in obs):
                return (rx, ry), d
        return (fx + max_d*ca, fy - max_d*sa), max_d

    def lookahead_best_heading(self, obs, cps, sweep=60, step=8):
        """
        Sweep candidate headings within ±sweep degrees.
        For each, simulate a multi-step path and score it.
        Returns the best heading offset and whether a detour is needed.

        A detour is flagged when:
        - The direct CP heading scores poorly (path blocked or narrow)
        - A different heading scores significantly better
        """
        cp_diff   = self.angle_to_checkpoint(cps)
        cp_dist   = self.dist_to_checkpoint(cps)

        best_score  = -1
        best_off    = 0
        direct_score = None

        candidates = range(-sweep, sweep+1, step)
        scores = {}

        for off in candidates:
            clearance, survived, fx, fy = self.simulate_path(
                self.angle + off, obs, steps=5, step_dist=22
            )
            if survived == 0:
                scores[off] = 0
                continue

            # distance from path endpoint to checkpoint
            if cps and self.next_cp < len(cps):
                cp  = cps[self.next_cp]
                cx  = cp.x + cp.width/2
                cy  = cp.y + cp.height/2
                end_dist = math.hypot(fx - cx, fy - cy)
                # reward getting closer to CP
                proximity_gain = max(0, cp_dist - end_dist)
            else:
                proximity_gain = 0

            # alignment bonus
            alignment = max(0, 1 - abs(off - cp_diff) / 180)
            # visited penalty
            v_pen = self.visited_penalty(off, cps)

            score = (clearance * 0.8
                     + survived * 15
                     + proximity_gain * 0.5
                     + alignment * 50
                     + v_pen)
            scores[off] = score

            if off == 0 or (direct_score is None and abs(off - cp_diff) < step):
                direct_score = score

            if score > best_score:
                best_score = score
                best_off   = off

        # detect if a detour is needed:
        # direct path scores <70% of the best alternative
        direct_score = scores.get(0, 0)
        detour_needed = (best_score > 0 and
                         direct_score < best_score * 0.70 and
                         abs(best_off) > step)

        return best_off, detour_needed, scores


    def scan_passage_width(self, heading, obs, probe_dist=120):
        """
        Walk forward along a heading in 10px steps.
        At each step measure left+right perpendicular clearance.
        Returns list of (step_x, step_y, width) tuples — the narrowest
        point tells us if the passage is physically passable.
        CAR_BODY = 34px wide, need at least 38px gap to pass safely.
        """
        CAR_BODY   = 34
        MIN_GAP    = 38
        ca = math.cos(math.radians(heading))
        sa = math.sin(math.radians(heading))
        profile = []
        for d in range(10, probe_dist+1, 10):
            px = self.x + d * ca
            py = self.y - d * sa
            if px < MARGIN or px > WIDTH-MARGIN or py < MARGIN or py > HEIGHT-MARGIN:
                break
            # check if this point itself is inside an obstacle
            pt_blocked = any(o.collidepoint(px, py) for o in obs)
            if pt_blocked:
                break
            _, ld = self.cast_ray_from(px, py, heading + 90, obs, max_d=80)
            _, rd = self.cast_ray_from(px, py, heading - 90, obs, max_d=80)
            width = ld + rd
            profile.append((px, py, width, ld, rd))
        return profile

    def can_pass_through(self, heading, obs):
        """
        Returns (passable: bool, min_width: float, bottleneck_pos: tuple|None).
        passable = True  → car fits, proceed
        passable = False → too narrow, must find another route
        """
        MIN_GAP = 38
        profile = self.scan_passage_width(heading, obs)
        if not profile:
            return False, 0, None
        min_width = min(w for _, _, w, _, _ in profile)
        bottleneck = min(profile, key=lambda p: p[2])
        passable = min_width >= MIN_GAP
        return passable, min_width, (bottleneck[0], bottleneck[1])

    def find_passable_heading(self, obs, cps, sweep=180):
        """
        Scan all headings in ±sweep degrees (10° steps).
        For each, check can_pass_through().
        Among passable headings, pick the one with best score_heading().
        Returns (best_heading_offset, passable_found, min_width_at_best).
        """
        cp_diff = self.angle_to_checkpoint(cps)
        best_score  = -9999
        best_off    = None
        best_width  = 0
        any_passable = False

        for off in range(-sweep, sweep+1, 10):
            passable, width, _ = self.can_pass_through(self.angle + off, obs)
            if not passable:
                continue
            any_passable = True
            s = self.score_heading(off, obs, cps) + width * 0.3
            if s > best_score:
                best_score = s
                best_off   = off
                best_width = width

        if best_off is None:
            # nothing passable found — pick least-bad heading
            widest_w   = -1
            widest_off = 0
            for off in range(-sweep, sweep+1, 10):
                _, w, _ = self.can_pass_through(self.angle + off, obs)
                if w > widest_w:
                    widest_w   = w
                    widest_off = off
            return widest_off, False, widest_w

        return best_off, True, best_width


    def record_path(self):
        """Append current position to path_log every 25 frames."""
        self.path_log_timer += 1
        if self.path_log_timer >= 25:
            self.path_log.append((self.x, self.y))
            self.path_log_timer = 0
            # cap log size — keep last 400 waypoints (~170 seconds of driving)
            if len(self.path_log) > 400:
                self.path_log.pop(0)

    def checkpoint_near_path(self, cps):
        """
        Check if the next checkpoint lies within 80px of any recorded waypoint.
        If yes, return the index of that waypoint so we can navigate toward it
        and follow the path forward to the checkpoint.
        Returns (found: bool, waypoint_index: int).
        """
        if not cps or self.next_cp >= len(cps) or not self.path_log:
            return False, -1
        cp  = cps[self.next_cp]
        cx  = cp.x + cp.width  / 2
        cy  = cp.y + cp.height / 2
        best_idx  = -1
        best_dist = 80   # threshold: within 80px of path counts as "on path"
        for i, (px, py) in enumerate(self.path_log):
            d = math.hypot(px - cx, py - cy)
            if d < best_dist:
                best_dist = d
                best_idx  = i
        return best_idx >= 0, best_idx

    def angle_to_waypoint(self, idx):
        """Return steering angle difference toward path_log[idx]."""
        if idx < 0 or idx >= len(self.path_log):
            return 0.0
        wx, wy = self.path_log[idx]
        dx =  wx - self.x
        dy = -(wy - self.y)
        target = math.degrees(math.atan2(dy, dx))
        diff   = (target - self.angle + 360) % 360
        if diff > 180:
            diff -= 360
        return diff

    def nearest_path_waypoint(self):
        """Return index of the closest waypoint in path_log to current position."""
        if not self.path_log:
            return -1
        best_i, best_d = 0, float('inf')
        for i, (px, py) in enumerate(self.path_log):
            d = math.hypot(px - self.x, py - self.y)
            if d < best_d:
                best_d, best_i = d, i
        return best_i

    def follow_path_steer(self, cps):
        """
        Navigate along recorded path toward checkpoint.
        Advances replay_waypoint as we get close to each one.
        Returns steer value and whether replay is still active.
        """
        if not self.path_log:
            self.replaying_path = False
            return 0.0, False

        # advance waypoint if we're within 30px of current target
        while self.replay_waypoint < len(self.path_log) - 1:
            wx, wy = self.path_log[self.replay_waypoint]
            if math.hypot(wx - self.x, wy - self.y) < 30:
                self.replay_waypoint += 1
            else:
                break

        # if we've passed all waypoints, stop replaying
        if self.replay_waypoint >= len(self.path_log):
            self.replaying_path = False
            return 0.0, False

        # steer toward next waypoint
        diff  = self.angle_to_waypoint(self.replay_waypoint)
        steer = max(-2.5, min(2.5, diff * 0.04))
        return steer, True

    def update_manual(self, keys, obs, cps):
        ox, oy = self.x, self.y
        if keys[pygame.K_UP]:
            self.speed = min(self.speed + 0.2, self.max_speed)
        elif keys[pygame.K_DOWN]:
            self.speed = max(self.speed - 0.2, -self.max_speed / 2)
        else:
            self.speed *= 0.9
        if keys[pygame.K_LEFT]:  self.angle += 3
        if keys[pygame.K_RIGHT]: self.angle -= 3
        self.move()
        if self.collides_anything(obs):
            self.x, self.y, self.speed = ox, oy, 0.0
            self.status = "Blocked"
        else:
            self.status = "Manual driving"
        self.clamp_to_screen()
        self.check_checkpoints(cps)

    def try_forward_angles(self, obs, angles_to_try):
        """Try each angle offset; return first one that has a clear forward path."""
        for da in angles_to_try:
            test_angle = self.angle + da
            tx = self.x + 2.5 * math.cos(math.radians(test_angle))
            ty = self.y - 2.5 * math.sin(math.radians(test_angle))
            ox, oy = self.x, self.y
            self.x, self.y = tx, ty
            hit = self.collides_anything(obs)
            self.x, self.y = ox, oy
            if not hit:
                return da
        return None

    def update_auto(self, dists, obs, cps, frame):
        if self.destination_reached:
            self.speed *= 0.92
            self.clamp_to_screen()
            return

        # Hard boundary rescue — if car somehow escaped, teleport back and turn inward
        if self.x <= MARGIN or self.x >= WIDTH-MARGIN or self.y <= MARGIN or self.y >= HEIGHT-MARGIN:
            self.clamp_to_screen()
            self.speed = 0
            # point toward screen center
            dx = WIDTH/2 - self.x
            dy = -(HEIGHT/2 - self.y)
            self.angle = math.degrees(math.atan2(dy, dx))
            self.steer_hold_timer = 0
            self.status = "Returning to field"

        # mark visited cell every 15 frames + record ordered path
        self.visit_timer += 1
        if self.visit_timer >= 15:
            self.mark_visited()
            self.visit_timer = 0
        self.record_path()

        # sensor aliases
        far_left    = dists[0]
        side_left   = dists[1]
        near_left   = dists[2]
        front_left  = dists[3]
        front       = dists[4]
        front_right = dists[5]
        near_right  = dists[6]
        side_right  = dists[7]
        far_right   = dists[8]

        WARN_FRONT = 85
        HARD_FRONT = 48
        HARD_SIDE  = 34

        danger_front = front < HARD_FRONT or (front_left < HARD_FRONT and front_right < HARD_FRONT)
        warn_front   = front < WARN_FRONT or front_left < WARN_FRONT or front_right < WARN_FRONT
        danger_left  = near_left < HARD_SIDE or side_left < HARD_SIDE
        danger_right = near_right < HARD_SIDE or side_right < HARD_SIDE
        near_wall    = (self.x < MARGIN+22 or self.x > WIDTH-MARGIN-22 or
                        self.y < MARGIN+22 or self.y > HEIGHT-MARGIN-22)

        cp_diff = self.angle_to_checkpoint(cps)
        cp_dist = self.dist_to_checkpoint(cps)
        left_d, right_d, gap, corridor_passable = self.gap_clearance(obs)
        in_corridor = (left_d < 58 and right_d < 58)

        # stuck detection
        moved = math.hypot(self.x-self.last_x, self.y-self.last_y) > 0.8
        self.stuck_counter = 0 if moved else self.stuck_counter+1
        self.last_x, self.last_y = self.x, self.y

        # loop detection every 90 frames
        if frame % 60 == 0:
            self.path_history.append((self.x, self.y))
            if len(self.path_history) > 4:
                self.path_history.pop(0)
            if len(self.path_history) == 4:
                spread = max(
                    math.hypot(self.path_history[i][0]-self.path_history[j][0],
                               self.path_history[i][1]-self.path_history[j][1])
                    for i in range(4) for j in range(i+1,4)
                )
                if spread < 50 and self.loop_escape_timer <= 0:
                    best_score, best_off = -1, 0
                    for off in range(-180, 181, 10):
                        s = self.score_heading(off, obs, cps)
                        if s > best_score:
                            best_score, best_off = s, off
                    # check if checkpoint lies along a known path — if so, replay it
                    on_path, cp_wpt = self.checkpoint_near_path(cps)
                    if on_path and cp_wpt > 0:
                        # start replay from nearest current position on the path
                        nearest = self.nearest_path_waypoint()
                        # pick the waypoint between nearest and cp_wpt to follow
                        self.replay_waypoint = max(0, min(nearest, cp_wpt - 1))
                        self.replaying_path  = True
                        self.loop_escape_timer = 220
                        self.speed             = 1.6
                        self.status            = f"Replaying known path → CP{self.next_cp+1}"
                    else:
                        self.angle += best_off
                        self.loop_escape_timer = 180
                        self.steer_hold_timer  = 0
                        self.held_steer        = 0
                        self.speed             = 1.5
                        self.status            = "Escaping loop → open space"
                    self.stuck_counter = 0
                    self.path_history  = []
                    for dx in [-GRID, 0, GRID]:
                        for dy in [-GRID, 0, GRID]:
                            self.visited_cells.add(self.cell_at(self.x+dx, self.y+dy))

        if self.loop_escape_timer > 0:
            self.loop_escape_timer -= 1

        # hard stuck: use passage-width scan to find genuinely passable exit
        if self.stuck_counter > 14:
            best_off, passable, min_w = self.find_passable_heading(obs, cps, sweep=180)
            self.angle += best_off
            self.speed  = 1.0
            self.steer_hold_timer = 0
            self.held_steer       = 0
            self.stuck_counter    = 0
            for dx in [-GRID, 0, GRID]:
                for dy in [-GRID, 0, GRID]:
                    self.visited_cells.add(self.cell_at(self.x+dx, self.y+dy))
            if passable:
                self.status = f"Passage found ({int(min_w)}px wide)"
            else:
                self.status = f"Widest gap ({int(min_w)}px) — attempting"
            return

        # reverse ONLY if truly cornered — verify with passage check first
        if self.reverse_timer <= 0 and self.stuck_counter > 9:
            # check if ANY forward heading is passable before reversing
            fwd_passable, fwd_width, _ = self.can_pass_through(self.angle, obs)
            escape_angle = self.try_forward_angles(obs,
                [0,10,-10,20,-20,30,-30,45,-45,60,-60,80,-80,100,-100,120,-120,150,-150])
            if escape_angle is not None:
                # verify that direction is actually wide enough
                turn_passable, turn_w, _ = self.can_pass_through(self.angle + escape_angle, obs)
                if turn_passable:
                    self.angle += escape_angle
                    self.steer_hold_timer = 12
                    self.held_steer = math.copysign(2.0, escape_angle) if escape_angle != 0 else 0
                    self.speed = max(self.speed, 0.8)
                    self.status = f"Verified gap ({int(turn_w)}px) → going"
                    self.stuck_counter = 0
                    return
            # no passable forward angle — brief reverse
            self.reverse_timer = 7
            self.reverse_dir   = self.best_turn_direction(dists, cps)
            self.speed         = 0
            self.status        = "Cornered — reversing"
            return

        if self.reverse_timer > 0:
            ox, oy = self.x, self.y
            self.speed = -1.0
            self.apply_steering(2.0 * self.reverse_dir, smoothing=0.35)
            self.status = "Brief reverse"
            self.move()
            self.clamp_to_screen()
            if self.collides_anything(obs):
                self.x, self.y = ox, oy
                self.speed = 0
                self.reverse_timer = 0
                self.angle += 45 * self.reverse_dir
                self.stuck_counter = 0
                return
            self.reverse_timer -= 1
            self.check_checkpoints(cps)
            return

        # ── Forward driving ───────────────────────────────────────────
        ox, oy = self.x, self.y

        if danger_front or danger_left or danger_right:
            target_speed = 1.4
        elif warn_front or in_corridor:
            target_speed = 2.0
        else:
            target_speed = 2.8
        self.speed += (target_speed - self.speed) * 0.10

        if self.replaying_path and self.loop_escape_timer > 0 and not danger_front and not danger_left and not danger_right:
            # follow recorded path toward checkpoint
            steer, still_active = self.follow_path_steer(cps)
            if not still_active:
                self.replaying_path = False
            else:
                self.apply_steering(steer, smoothing=0.18)
                self.move()
                self.clamp_to_screen()
                if self.collides_anything(obs):
                    self.x, self.y = ox, oy
                    self.clamp_to_screen()
                    self.speed = 0
                    self.replaying_path = False  # obstacle blocks path — abandon replay
                self.check_checkpoints(cps)
                return

        if self.steer_hold_timer > 0:
            steer = self.held_steer
            self.steer_hold_timer -= 1

        elif in_corridor and corridor_passable:
            # centre between walls + gentle CP pull
            center_offset = (left_d - right_d) * 0.045
            cp_pull = max(-1.5, min(1.5, cp_diff * 0.022))
            steer = center_offset + cp_pull
            self.status = f"Corridor → CP{self.next_cp+1}"

        elif in_corridor and not corridor_passable:
            # gap too narrow — scored exit
            best_score, best_off = -1, 0
            for off in range(-150, 151, 8):
                s = self.score_heading(off, obs, cps)
                if s > best_score:
                    best_score, best_off = s, off
            steer = math.copysign(3.0, best_off) if best_off != 0 else 0
            self.steer_hold_timer = 18
            self.held_steer       = steer
            self.status           = "Narrow — finding exit"

        elif danger_front or near_wall:
            # passage-verified obstacle turn
            best_off, passable, min_w = self.find_passable_heading(obs, cps, sweep=120)
            steer = math.copysign(3.2, best_off) if best_off != 0 else 3.2*self.best_turn_direction(dists,cps)
            self.steer_hold_timer = 14
            self.held_steer       = steer
            if passable:
                self.status = f"Clear path ({int(min_w)}px) → turning"
            else:
                self.status = f"Tight gap ({int(min_w)}px) — careful"

        elif warn_front:
            # lookahead: find best heading before hitting the obstacle
            la_off, detour, _ = self.lookahead_best_heading(obs, cps, sweep=70, step=7)
            if detour:
                steer = max(-3.0, min(3.0, la_off * 0.08))
                self.status = f"Detour → {la_off:+d}°"
                self.steer_hold_timer = 10
                self.held_steer       = steer
            else:
                dir_ = self.best_turn_direction(dists, cps)
                steer = 1.4 * dir_
                self.steer_hold_timer = 6
                self.held_steer       = steer
                self.status           = "Slowing — obstacle ahead"

        elif danger_left and not danger_right:
            steer = -1.6
            self.status = "Drifting right"
        elif danger_right and not danger_left:
            steer = 1.6
            self.status = "Drifting left"

        else:
            # lookahead cruise: simulate ±60° paths and pick best
            la_off, detour, scores = self.lookahead_best_heading(obs, cps, sweep=60, step=6)
            cp_pull   = max(-2.0, min(2.0, cp_diff * 0.030))
            la_pull   = max(-1.8, min(1.8, la_off  * 0.055))
            if detour:
                # significant detour needed — weight lookahead more
                steer = cp_pull * 0.3 + la_pull * 0.7
                self.status = f"Detour planned → {la_off:+d}°  CP{self.next_cp+1}"
            else:
                # direct path is fine — mostly follow CP with slight open-space bias
                steer = cp_pull * 0.65 + la_pull * 0.35
                self.status = f"→ CP{self.next_cp+1}  ({int(cp_diff)}°  {int(cp_dist)}px)"

        self.apply_steering(steer, smoothing=0.20)
        self.move()
        self.clamp_to_screen()

        if self.collides_anything(obs):
            self.x, self.y = ox, oy
            self.clamp_to_screen()
            self.speed = 0
            dir_ = self.best_turn_direction(dists, cps)
            self.angle += 15 * dir_
            self.steer_hold_timer = 14
            self.held_steer       = 3.0 * dir_
            self.status = "Collision avoided"

        self.check_checkpoints(cps)

    def draw(self, surface):
        L, W = 50, 30
        ca = math.cos(math.radians(self.angle))
        sa = math.sin(math.radians(self.angle))
        pts = [
            (self.x-L/2*ca-W/2*sa, self.y+L/2*sa-W/2*ca),
            (self.x-L/2*ca+W/2*sa, self.y+L/2*sa+W/2*ca),
            (self.x+L/2*ca+W/2*sa, self.y-L/2*sa+W/2*ca),
            (self.x+L/2*ca-W/2*sa, self.y-L/2*sa-W/2*ca),
        ]
        col = LIME if self.destination_reached else GREEN
        pygame.draw.polygon(surface, col, pts)
        fx = self.x + (L/2+5)*ca
        fy = self.y - (L/2+5)*sa
        pygame.draw.circle(surface, YELLOW, (int(fx), int(fy)), 5)


def draw_menu(surface):
    surface.fill(DARK)
    t = font_large.render("Self-Driving Car Simulator", True, GREEN)
    surface.blit(t, (WIDTH//2-t.get_width()//2, 110))
    s = font.render("Python · Pygame  |  Day 7 Final Build", True, CYAN)
    surface.blit(s, (WIDTH//2-s.get_width()//2, 168))
    rows = [
        ("ENTER / S", "Start Simulation"),
        ("SPACE",     "Toggle Manual ↔ Auto"),
        ("R",         "Restart with new random layout"),
        ("ESC",       "Return to menu"),
        ("Q",         "Quit"),
    ]
    y = 235
    for k, d in rows:
        surface.blit(font.render(f"[ {k} ]", True, YELLOW), (200,y))
        surface.blit(font.render(d, True, WHITE), (390,y))
        y += 38
    ft = font_small.render("github.com/YOUR-USERNAME/self-driving-car-simulator", True, GRAY)
    surface.blit(ft, (WIDTH//2-ft.get_width()//2, HEIGHT-34))
    pygame.display.flip()


def draw_hud(surface, car, cps):
    pygame.draw.rect(surface, DARK, (0,0,WIDTH,96))
    mode_col = CYAN if car.mode=="auto" else ORANGE
    surface.blit(font.render(f"Mode: {car.mode.upper()}  [SPACE]", True, mode_col), (12,8))
    surface.blit(font.render(f"Status: {car.status}", True, WHITE), (12,34))
    surface.blit(font.render(f"Speed: {abs(car.speed):.1f}", True, WHITE), (12,60))
    cp_txt = "ALL DONE!" if car.destination_reached else f"CP {car.next_cp+1}/{len(cps)}"
    cp_col = LIME if car.destination_reached else YELLOW
    surface.blit(font.render(f"Checkpoint: {cp_txt}", True, cp_col), (340,8))
    surface.blit(font.render(f"Dist: {int(car.total_distance)} px", True, WHITE), (340,34))
    surface.blit(font.render(f"Heading: {int(car.angle%360)}°", True, WHITE), (340,60))
    h = font_small.render("[R] Restart  [ESC] Menu  [Q] Quit", True, GRAY)
    surface.blit(h, (WIDTH-h.get_width()-10, 78))


def draw_sensor_bar(surface, dists):
    y0 = HEIGHT-28
    pygame.draw.rect(surface, DARK, (0,y0,WIDTH,28))
    surface.blit(font_small.render("SENSORS:", True, GRAY), (6,y0+6))
    seg_w = 76
    for i, d in enumerate(dists):
        col = GREEN if d>80 else (ORANGE if d>40 else RED)
        x0  = 90 + i*seg_w
        bl  = int((d/200)*(seg_w-12))
        pygame.draw.rect(surface, col, (x0, y0+8, bl, 12))
        surface.blit(font_small.render(str(int(d)), True, WHITE), (x0+bl+2,y0+6))


def draw_destination(surface):
    ov = pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA)
    ov.fill((0,0,0,150))
    surface.blit(ov,(0,0))
    t = font_large.render("DESTINATION REACHED!", True, LIME)
    surface.blit(t,(WIDTH//2-t.get_width()//2, HEIGHT//2-50))
    s = font.render("Press R to restart with a new layout", True, WHITE)
    surface.blit(s,(WIDTH//2-s.get_width()//2, HEIGHT//2+20))


# ── Main ──────────────────────────────────────────────────────────────
obstacles   = gen_obstacles()
checkpoints = gen_checkpoints(obstacles)
car   = Car()
STATE = "menu"
frame = 0
quit_game = False

def do_restart():
    global obstacles, checkpoints
    obstacles   = gen_obstacles()
    checkpoints = gen_checkpoints(obstacles)
    car.reset()

pygame.event.clear()

while not quit_game:
    clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if STATE == "menu":
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_s):
                    do_restart()
                    pygame.event.clear()
                    STATE = "game"
                elif event.key == pygame.K_q:
                    quit_game = True

            elif STATE == "game":
                if event.key == pygame.K_ESCAPE:
                    pygame.event.clear()
                    STATE = "menu"
                elif event.key == pygame.K_r:
                    do_restart()
                elif event.key == pygame.K_q:
                    quit_game = True
                elif event.key == pygame.K_SPACE:
                    car.mode = "auto" if car.mode == "manual" else "manual"

    if quit_game:
        break

    if STATE == "menu":
        draw_menu(screen)
        pygame.display.flip()
        continue

    # ── game tick ─────────────────────────────────────────────────────
    keys = pygame.key.get_pressed()
    rays, dists = car.get_sensor_data(obstacles)

    if car.mode == "manual":
        car.update_manual(keys, obstacles, checkpoints)
    else:
        car.update_auto(dists, obstacles, checkpoints, frame)

    frame += 1

    # ── draw ──────────────────────────────────────────────────────────
    screen.fill(BLACK)
    for i in range(0, HEIGHT, 40):
        pygame.draw.line(screen, GRAY, (0,i),(WIDTH,i),1)
    for i in range(0, WIDTH, 40):
        pygame.draw.line(screen, GRAY, (i,0),(i,HEIGHT),1)
    # draw visited cells as faint red tint
    for (gx, gy) in car.visited_cells:
        vsurf = pygame.Surface((GRID, GRID), pygame.SRCALPHA)
        vsurf.fill((180, 40, 40, 35))
        screen.blit(vsurf, (gx*GRID, gy*GRID))

    t_now = pygame.time.get_ticks()
    for i, cp in enumerate(checkpoints):
        if car.destination_reached:
            col = LIME
        elif i < car.next_cp:
            col = (40,80,40)
        elif i == car.next_cp:
            col = CP_COLORS[i % len(CP_COLORS)]
        else:
            col = (60,60,60)
        pygame.draw.rect(screen, col, cp)
        lbl = font_small.render(f"CP{i+1}", True, WHITE)
        screen.blit(lbl,(cp.x+3, cp.y+3))

    for obs in obstacles:
        pygame.draw.rect(screen, BLUE, obs)
        pygame.draw.rect(screen, (100,160,255), obs, 2)

    for i,(ex,ey) in enumerate(rays):
        d = dists[i]
        col = RED if d<40 else (ORANGE if d<80 else (60,180,60))
        pygame.draw.line(screen, col,(int(car.x),int(car.y)),(int(ex),int(ey)),1)
        pygame.draw.circle(screen, YELLOW,(int(ex),int(ey)),3)

    car.draw(screen)
    draw_hud(screen, car, checkpoints)
    draw_sensor_bar(screen, dists)

    if car.destination_reached:
        draw_destination(screen)

    pygame.display.flip()

pygame.quit()
sys.exit()
