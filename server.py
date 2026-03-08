import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
GAME_HTML = ROOT / "game.html"
STATIC_FILES = {
    "/Carrier.png": ("Carrier.png", "image/png"),
    "/carrier.png": ("Carrier.png", "image/png"),
    "/Cruiser.png": ("Cruiser.png", "image/png"),
    "/cruiser.png": ("Cruiser.png", "image/png"),
    "/Battleship.png": ("Battleship.png", "image/png"),
    "/battleship.png": ("Battleship.png", "image/png"),
    "/Destroyer.png": ("Destroyer.png", "image/png"),
    "/destroyer.png": ("Destroyer.png", "image/png"),
    "/Submarine_gemini.png": ("Submarine_gemini.png", "image/png"),
    "/submarine_gemini.png": ("Submarine_gemini.png", "image/png"),
    "/Submarine.png": ("Submarine.png", "image/png"),
    "/submarine.png": ("Submarine.png", "image/png"),
    "/Explosion1.mp3": ("Explosion1.mp3", "audio/mpeg"),
    "/Explosion2.mp3": ("Explosion2.mp3", "audio/mpeg"),
    "/Explosion3.mp3": ("Explosion3.mp3", "audio/mpeg"),
    "/Explosion4.mp3": ("Explosion4.mp3", "audio/mpeg"),
    "/Explosion5.mp3": ("Explosion5.mp3", "audio/mpeg"),
    "/Explosion6.mp3": ("Explosion6.mp3", "audio/mpeg"),
    "/Explosion7.mp3": ("Explosion7.mp3", "audio/mpeg"),
    "/Bubbles.mp3": ("Bubbles.mp3", "audio/mpeg"),
    "/bubbles.mp3": ("Bubbles.mp3", "audio/mpeg"),
    "/Victory.mp3": ("Victory.mp3", "audio/mpeg"),
    "/victory.mp3": ("Victory.mp3", "audio/mpeg"),
}
BOARD_SIZE = 10
SHIP_LENGTHS = [5, 4, 3, 3, 2]
SHIP_CLASSES = ["Aircraft Carrier", "Battleship", "Cruiser", "Submarine", "Destroyer"]
SESSION_TIMEOUT_SECONDS = 60 * 60 * 6


def now_ts() -> float:
    return time.time()


def make_empty_board() -> List[List[str]]:
    return [["~" for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]


def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE


@dataclass
class PlayerState:
    token: str
    display_name: str
    ships_board: List[List[str]] = field(default_factory=make_empty_board)
    tracking_board: List[List[str]] = field(default_factory=make_empty_board)
    ships: List[Dict] = field(default_factory=list)
    placed: bool = False


@dataclass
class RoomState:
    code: str
    players: Dict[str, PlayerState] = field(default_factory=dict)
    turn_token: Optional[str] = None
    phase: str = "lobby"  # lobby -> placement -> battle -> finished
    winner_token: Optional[str] = None
    created_at: float = field(default_factory=now_ts)
    updated_at: float = field(default_factory=now_ts)


class GameStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.rooms: Dict[str, RoomState] = {}

    def _cleanup_stale(self) -> None:
        cutoff = now_ts() - SESSION_TIMEOUT_SECONDS
        stale = [code for code, room in self.rooms.items() if room.updated_at < cutoff]
        for code in stale:
            del self.rooms[code]

    def create_room(self, display_name: str) -> Tuple[RoomState, PlayerState]:
        with self._lock:
            self._cleanup_stale()
            while True:
                code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
                if code not in self.rooms:
                    break
            token = secrets.token_urlsafe(18)
            player = PlayerState(token=token, display_name=display_name[:24] or "Player 1")
            room = RoomState(code=code, phase="placement")
            room.players[token] = player
            room.updated_at = now_ts()
            self.rooms[code] = room
            return room, player

    def join_room(self, code: str, display_name: str) -> Tuple[Optional[RoomState], Optional[PlayerState], str]:
        with self._lock:
            self._cleanup_stale()
            room = None
            if code:
                room = self.rooms.get(code)
                if not room:
                    return None, None, "Room not found"
            else:
                # Auto-join the oldest open host session for simple 2-player LAN setup.
                joinable = [
                    r for r in self.rooms.values()
                    if r.phase == "placement" and len(r.players) < 2
                ]
                if joinable:
                    joinable.sort(key=lambda r: r.created_at)
                    room = joinable[0]

            if not room:
                return None, None, "No open host session found. Ask host to click Host Game first."
            if len(room.players) >= 2:
                return None, None, "Room is full"
            if room.phase != "placement":
                return None, None, "Room is not accepting new players"
            token = secrets.token_urlsafe(18)
            player_num = len(room.players) + 1
            player = PlayerState(token=token, display_name=display_name[:24] or f"Player {player_num}")
            room.players[token] = player
            room.updated_at = now_ts()
            return room, player, ""

    def _room_and_player(self, code: str, token: str) -> Tuple[Optional[RoomState], Optional[PlayerState], str]:
        room = self.rooms.get(code)
        if not room:
            return None, None, "Room not found"
        player = room.players.get(token)
        if not player:
            return None, None, "Invalid player token"
        room.updated_at = now_ts()
        return room, player, ""

    def place_ships(self, code: str, token: str, ships: List[Dict]) -> Tuple[bool, str]:
        with self._lock:
            room, player, msg = self._room_and_player(code, token)
            if not room:
                return False, msg
            if room.phase not in {"placement", "lobby"}:
                return False, "Cannot place ships right now"
            if len(ships) != len(SHIP_LENGTHS):
                return False, "You must place all classic ships"

            lengths = sorted([int(s.get("length", 0)) for s in ships])
            if lengths != sorted(SHIP_LENGTHS):
                return False, "Ship lengths do not match classic rules"

            board = make_empty_board()
            normalized = []
            for idx, ship in enumerate(ships):
                x = int(ship.get("x", -1))
                y = int(ship.get("y", -1))
                length = int(ship.get("length", 0))
                direction = str(ship.get("direction", "H")).upper()
                if direction not in {"H", "V"}:
                    return False, f"Ship {idx + 1} has invalid direction"
                if length not in SHIP_LENGTHS:
                    return False, f"Ship {idx + 1} has invalid length"

                cells = []
                for offset in range(length):
                    cx = x + offset if direction == "H" else x
                    cy = y if direction == "H" else y + offset
                    if not in_bounds(cx, cy):
                        return False, f"Ship {idx + 1} is out of bounds"
                    if board[cy][cx] == "S":
                        return False, "Ships cannot overlap"
                    for ny in range(cy - 1, cy + 2):
                        for nx in range(cx - 1, cx + 2):
                            if not in_bounds(nx, ny):
                                continue
                            if board[ny][nx] == "S":
                                return False, "Ships cannot touch, including diagonally"
                    cells.append((cx, cy))

                for cx, cy in cells:
                    board[cy][cx] = "S"

                normalized.append({
                    "id": idx,
                    "x": x,
                    "y": y,
                    "length": length,
                    "direction": direction,
                    "hits": 0,
                })

            player.ships_board = board
            player.ships = normalized
            player.placed = True

            if len(room.players) == 2 and all(p.placed for p in room.players.values()):
                room.phase = "battle"
                # Deterministic first player: earliest token sort for fairness across refresh.
                room.turn_token = sorted(room.players.keys())[0]
            return True, "Ships locked in"

    def fire(self, code: str, token: str, x: int, y: int) -> Tuple[bool, str, Dict]:
        with self._lock:
            room, player, msg = self._room_and_player(code, token)
            if not room:
                return False, msg, {}
            if room.phase != "battle":
                return False, "Battle has not started", {}
            if room.turn_token != token:
                return False, "Not your turn", {}
            if not in_bounds(x, y):
                return False, "Shot is out of bounds", {}

            enemy_token = next((t for t in room.players.keys() if t != token), None)
            if not enemy_token:
                return False, "Opponent not found", {}
            enemy = room.players[enemy_token]

            if player.tracking_board[y][x] in {"H", "M"}:
                return False, "You already fired there", {}

            cell = enemy.ships_board[y][x]
            sunk = False
            sunk_length = None
            hit_ship_length = None
            hit_ship_class = None
            sunk_ship_class = None
            announce_hit_voice = False
            sunk_cells: List[Tuple[int, int]] = []
            auto_marked_cells: List[Tuple[int, int]] = []
            if cell == "S":
                enemy.ships_board[y][x] = "X"
                player.tracking_board[y][x] = "H"
                for ship in enemy.ships:
                    sx, sy = ship["x"], ship["y"]
                    cells = []
                    for i in range(ship["length"]):
                        cx = sx + i if ship["direction"] == "H" else sx
                        cy = sy if ship["direction"] == "H" else sy + i
                        cells.append((cx, cy))
                    if (x, y) in cells:
                        ship_id = int(ship.get("id", -1))
                        hit_ship_length = ship["length"]
                        if 0 <= ship_id < len(SHIP_CLASSES):
                            hit_ship_class = SHIP_CLASSES[ship_id]
                        hit_count = sum(1 for cx, cy in cells if enemy.ships_board[cy][cx] == "X")
                        ship["hits"] = hit_count
                        announce_hit_voice = hit_count == 1
                        if all(enemy.ships_board[cy][cx] == "X" for cx, cy in cells):
                            sunk = True
                            sunk_length = ship["length"]
                            sunk_ship_class = hit_ship_class
                            sunk_cells = cells
                        break
                result = "hit"
            else:
                player.tracking_board[y][x] = "M"
                enemy.ships_board[y][x] = "O"
                result = "miss"

            if sunk and sunk_cells:
                ship_cell_set = set(sunk_cells)
                ring_set = set()
                for sx, sy in sunk_cells:
                    for ny in range(sy - 1, sy + 2):
                        for nx in range(sx - 1, sx + 2):
                            if not in_bounds(nx, ny):
                                continue
                            if (nx, ny) in ship_cell_set:
                                continue
                            ring_set.add((nx, ny))
                auto_marked_cells = sorted(ring_set, key=lambda c: (c[1], c[0]))
                for mx, my in auto_marked_cells:
                    if player.tracking_board[my][mx] == "~":
                        player.tracking_board[my][mx] = "M"

            # House rule: a hit grants another shot; turn only passes on miss.
            if result == "miss":
                room.turn_token = enemy_token

            # Win check
            enemy_remaining = any("S" in row for row in enemy.ships_board)
            if not enemy_remaining:
                room.phase = "finished"
                room.winner_token = token

            payload = {
                "result": result,
                "sunk": sunk,
                "sunkLength": sunk_length,
                "sunkShipClass": sunk_ship_class,
                "hitShipLength": hit_ship_length,
                "hitShipClass": hit_ship_class,
                "announceHitVoice": announce_hit_voice,
                "sunkCells": [{"x": cx, "y": cy} for cx, cy in sunk_cells],
                "autoMarkedCells": [{"x": cx, "y": cy} for cx, cy in auto_marked_cells],
                "gameFinished": room.phase == "finished",
                "winnerToken": room.winner_token,
                "nextTurnToken": room.turn_token,
            }
            return True, "Shot accepted", payload

    def state_for(self, code: str, token: str) -> Tuple[bool, str, Dict]:
        with self._lock:
            room, me, msg = self._room_and_player(code, token)
            if not room:
                return False, msg, {}
            enemy_token = next((t for t in room.players if t != token), None)
            enemy = room.players.get(enemy_token) if enemy_token else None

            public_enemy_board = make_empty_board()
            if enemy:
                for y in range(BOARD_SIZE):
                    for x in range(BOARD_SIZE):
                        v = enemy.ships_board[y][x]
                        if v == "X":
                            public_enemy_board[y][x] = "H"

            players_public = [
                {
                    "token": p.token,
                    "displayName": p.display_name,
                    "placed": p.placed,
                }
                for p in room.players.values()
            ]

            payload = {
                "roomCode": room.code,
                "phase": room.phase,
                "me": {
                    "token": me.token,
                    "displayName": me.display_name,
                    "shipsBoard": me.ships_board,
                    "trackingBoard": me.tracking_board,
                    "placed": me.placed,
                    "ships": [
                        {
                            "id": int(ship.get("id", -1)),
                            "x": int(ship.get("x", -1)),
                            "y": int(ship.get("y", -1)),
                            "length": int(ship.get("length", 0)),
                            "direction": str(ship.get("direction", "H")),
                        }
                        for ship in me.ships
                    ],
                },
                "enemy": {
                    "displayName": enemy.display_name if enemy else "Waiting...",
                    "revealedBoard": public_enemy_board,
                    "present": enemy is not None,
                    "placed": enemy.placed if enemy else False,
                },
                "turnToken": room.turn_token,
                "winnerToken": room.winner_token,
                "players": players_public,
            }
            return True, "", payload


STORE = GameStore()


class Handler(BaseHTTPRequestHandler):
    server_version = "BattleshipLAN/1.0"

    def _set_headers(self, status=200, content_type="application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json_response(self, status: int, data: Dict) -> None:
        self._set_headers(status=status, content_type="application/json")
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._set_headers(status=204, content_type="text/plain")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/game.html"}:
            if not GAME_HTML.exists():
                self._set_headers(status=500, content_type="text/plain")
                self.wfile.write(b"game.html not found")
                return
            content = GAME_HTML.read_bytes()
            self._set_headers(status=200, content_type="text/html; charset=utf-8")
            self.wfile.write(content)
            return

        static = STATIC_FILES.get(parsed.path)
        if static:
            filename, content_type = static
            static_path = ROOT / filename
            if not static_path.exists():
                self._set_headers(status=404, content_type="text/plain")
                self.wfile.write(b"Asset not found")
                return
            self._set_headers(status=200, content_type=content_type)
            self.wfile.write(static_path.read_bytes())
            return

        if parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            code = (query.get("code") or [""])[0].strip().upper()
            token = (query.get("token") or [""])[0].strip()
            ok, msg, state = STORE.state_for(code, token)
            if not ok:
                self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": msg})
                return
            self._json_response(200, {"ok": True, "state": state})
            return

        self._set_headers(status=404, content_type="text/plain")
        self.wfile.write(b"Not found")

    def _read_json_body(self) -> Dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = self._read_json_body()

        if parsed.path == "/api/create_room":
            name = str(body.get("displayName", "")).strip() or "Player 1"
            room, player = STORE.create_room(name)
            self._json_response(200, {
                "ok": True,
                "roomCode": room.code,
                "token": player.token,
                "displayName": player.display_name,
            })
            return

        if parsed.path == "/api/join_room":
            code = str(body.get("roomCode", "")).strip().upper()
            name = str(body.get("displayName", "")).strip() or "Player 2"
            room, player, msg = STORE.join_room(code, name)
            if not room:
                self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": msg})
                return
            self._json_response(200, {
                "ok": True,
                "roomCode": room.code,
                "token": player.token,
                "displayName": player.display_name,
            })
            return

        if parsed.path == "/api/place_ships":
            code = str(body.get("roomCode", "")).strip().upper()
            token = str(body.get("token", "")).strip()
            ships = body.get("ships", [])
            ok, msg = STORE.place_ships(code, token, ships)
            if not ok:
                self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": msg})
                return
            self._json_response(200, {"ok": True, "message": msg})
            return

        if parsed.path == "/api/fire":
            code = str(body.get("roomCode", "")).strip().upper()
            token = str(body.get("token", "")).strip()
            x = int(body.get("x", -1))
            y = int(body.get("y", -1))
            ok, msg, payload = STORE.fire(code, token, x, y)
            if not ok:
                self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": msg})
                return
            self._json_response(200, {"ok": True, "message": msg, "shot": payload})
            return

        self._json_response(404, {"ok": False, "error": "Not found"})


def detect_local_ip() -> str:
    import socket

    ip = "127.0.0.1"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
    except OSError:
        pass
    return ip


def main() -> None:
    host = "0.0.0.0"
    port = 8000
    httpd = ThreadingHTTPServer((host, port), Handler)

    local_ip = detect_local_ip()
    print("\nBattleship LAN server is running.")
    print(f"Open on host laptop: http://localhost:{port}")
    print(f"Open on other laptop: http://{local_ip}:{port}\n")
    print("Keep this window open while playing. Press Ctrl+C to stop.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

