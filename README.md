![Battleship Screenshot](<Battleship Screenshot 2026-03-08.png>)

# Battleship: Iron Tides (LAN)

A 2-player Battleship game for Windows laptops on the same home network.

## Start (Host laptop)

1. Double-click `start_server.bat`.
2. Keep that terminal window open.
3. Open `http://localhost:8000` in a browser.
4. Click **Host Game**.

The server window also shows a LAN URL such as `http://192.168.1.20:8000`.

## Join (Guest laptop)

1. Open the host LAN URL in a browser (example: `http://192.168.1.20:8000`).
2. Enter name and click **Join Game** (auto-connects to host session).
3. Place ships on the left board and lock in.

## Gameplay

- Left board: your fleet (ship positions, incoming hits/misses).
- Right board: your shots on enemy waters.
- Strict turn-based: one shot per turn.
- Classic ships: 5, 4, 3, 3, 2.
- Ships cannot touch each other, including diagonally.

## Audio

Click **Enable Audio** once per browser tab (required by browser audio policy).

Sound mapping:
- Launch: bomb whistle
- Miss: splash
- Hit: explosion
- Sunk ship: alarm + bubbling


## Files

- `server.py`: LAN HTTP game server (no external Python packages).
- `game.html`: UI and game logic.
- `start_server.bat`: easiest launch for Windows.



