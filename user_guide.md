# Battleship Game - User Guide

## Overview
Battleship Game is a 2-player LAN browser game.

- Host runs the local server.
- Guest joins using the host's LAN URL.
- Classic fleet sizes: 5, 4, 3, 3, 2.

## Requirements
- Windows PC (host and guest on same network)
- Python 3 installed on host
- Modern browser (Chrome/Edge/Firefox)

## Start the Host Session
1. Open the project folder.
2. Run `start_server.bat`.
3. Keep the server terminal open.
4. Open `http://localhost:8000` in browser.
5. Enter your player name and click **Host Game**.

The server console will display your LAN URL (for example, `http://192.168.1.20:8000`).

## Join as Guest
1. On second device, open host LAN URL in browser.
2. Enter player name.
3. Click **Join Game**.

## Ship Placement
1. Use **Rotate** to switch orientation.
2. Click board cells to place ships.
3. Ships cannot overlap or touch diagonally.
4. Click **Lock Ships** when done.

## Battle Controls
- Fire by clicking unknown cells on the right tracking board.
- Hit sounds use random explosion clips.
- First hit on a ship calls out class (`You hit a [class]!`).
- Sinks play bubbles and then a random funny line.
- Winning plays `Victory.mp3` before the final victory message.

## Audio
Click **Enable Audio** once per browser tab.

If audio does not play:
1. Ensure tab is not muted.
2. Click **Enable Audio** again.
3. Check browser autoplay settings.

## Troubleshooting
- **Guest cannot join:** verify both devices are on same network and host firewall allows Python.
- **No game updates:** keep host server running and refresh page.
- **Images/sounds missing:** hard refresh with `Ctrl+F5`.

## Project Files
- `server.py` - game server and API
- `game.html` - UI, gameplay, audio, ship rendering
- `start_server.bat` - host launcher
- `user_guide.md` - this guide
