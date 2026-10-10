# 🎮 Twenty Dots Game

A strategic multiplayer board game where players compete to collect colored dots by forming lines on a 6x6 grid.

## 🌐 Play Online

**Live Demo:** [https://twenty-dots-game.onrender.com/web_client.html](https://twenty-dots-game.onrender.com/web_client.html)

⚠️ **First load may take 30-60 seconds** as the free server wakes up.

## 🎯 How to Play

1. **Create a Room:**
   - Open the web client and enter your name.
   - Choose **Create room**, 2–4 players, and a game goal.
   - Optionally enable **Power Play** for Paint, color-matched one-step Shift, and Swap cards. Swap exchanges any two non-wild dots anywhere on the board. Leave Power Play off for regular-card play.
   - Send the **Invite friends** link, or copy the room code.

2. **Join Friends:**
   - Open an invite link, enter your name, and take your seat.
   - Or choose **Join friends** and enter the room code exactly as shared.
   - The game starts when every seat is filled and connected.
   - Prefer a warm-up? Choose **Practice** for computer opponents.

3. **Game Rules:**
   - 2-4 players
   - Play up to 2 cards per turn
   - Tap a card to preview its position, then confirm your move.
   - Match 3+ dots in a line (horizontal, vertical, or diagonal) to score.
   - First to 20 dots wins in **The classic**.
   - **Color collector** requires 5 of each regular color; **Wild ambition** also requires 5 yellow dots.
   - Yellow wild dots can complete any color match
   - Roll at the start and whenever yellow is collected or replaced. A roll that makes a match requires another roll.
   - Your hand stays visible between turns so you can plan ahead.
   - When the deck runs out, played cards are shuffled back in. Held cards, scores, and the board stay untouched.

4. **Stay at the Table:**
   - Connection interruptions trigger automatic rejoining; moves stay disabled until the state is restored.
   - After refreshing, choose **Rejoin** to recover your saved seat and private hand.
   - A saved seat belongs to this browser/device and expires locally after 24 hours.
   - Rooms are held in server memory, so a server restart ends existing games.

5. **Play Another:**
   - Choose **Play again** on the results screen. The next round starts when every human player is connected and ready; computer opponents are ready automatically.
   - Keep the same room, invite link, and seats. The starting player rotates each round.
   - Each round win earns one series point. First to **two wins** takes game night: best of three for two players, potentially more rounds with three or four.
   - After a series finishes, ready up for a fresh series. The host can change the next round’s goal or Power Play setting; changing either clears readiness so everyone agrees to the new rules.
   - Refreshing after a win still lets you rejoin. **Leave & create a different table** is separate from a rematch.

6. **Make It Your Table:**
   - Send **Nice move!**, **Well played!**, **Close one!**, or **Rematch?** during play or from the results screen. Reactions have a three-second cooldown and can be muted.
   - **Music & preferences** is available from the home screen, lobby, table, and results. Turn on **Background music** for a shuffled playlist of original songs; **Next song** skips ahead. Only the song that is playing is downloaded. If no song can load, the game falls back to *A Little Company*, a mellow instrumental synthesized in your browser.
   - To add a song, put the MP3 in `static/music/` and add its title and path to the `SONGS` list at the top of `static/music.js`.
   - Music has its own volume slider, separate from game sounds. It defaults to on, pauses when the page is hidden, and remembers your choice on this device. After a reload or a browser audio interruption, a tap or keypress may be required to resume.
   - Preferences also offer optional game sounds, supported-device vibration, and reduced motion. Music and game sounds default to on and start after your first tap or keypress (browsers block sound before then); vibration defaults to off.
   - Last-move highlights and collection summaries stay readable without animation. Motion also respects the operating system’s reduced-motion setting.

## 🚀 Features

- **Multiplayer Support:** 2-4 players online
- **Mobile-first Table:** Responsive board, card previews, touch controls, and persistent private hands
- **Room Invites:** Native mobile sharing, clipboard links, and a live waiting room
- **Reconnect:** Token-protected saved seats and automatic connection recovery
- **Optional Power Play:** Three tactical online powers with target previews, full-turn costs, and server-validated effects; [power rules](POWER_CARDS_README.md)
- **Desktop Variant:** The existing desktop powers and landmines remain separate from the focused online set
- **AI Opponents:** Play against computer players
- **Real-time Updates:** Instant game state synchronization
- **Game Nights:** Same-room rematches, rotating starters, and first-to-two series scores
- **Fresh Decks:** Played cards recycle when the draw pile empties, including in four-player games
- **Table Talk:** Preset reactions, cooldowns, and a local mute preference
- **Move Feedback:** Collection effects, line/wild-finish callouts, optional audio and haptics
- **Background Music:** Original instrumental loop with independent volume and automatic background pause

## 💻 Local Development

### Requirements
- Python 3.11+
- Flask, Flask-SocketIO

### Installation

```bash
# Clone the repository
git clone https://github.com/dabeejgames/Twenty-Dots-Game.git
cd Twenty-Dots-Game

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the game server
python game_server.py
```

Visit `http://localhost:5000/web_client.html` in your browser.

### Local Network Play

To play with friends on the same WiFi:

1. Run the server on one computer
2. Find your local IP address:
   - Windows: `ipconfig` (look for IPv4)
   - Mac/Linux: `ifconfig` or `ip addr`
3. Share your IP with friends
4. Friends open `http://[YOUR_IP]:5000/web_client.html` in their browser.
5. Create a room from that address and share its invite link or room code. A localhost invite only works on the host computer.

### Validation

- Server regression tests: `python -m unittest discover -s tests -p test_multiplayer.py -v`.
- Browser test setup: `npm install --prefix tests`, then `npx --prefix tests playwright install chromium`.
- With the game server running locally, run `npm test --prefix tests`.
- Set `GAME_URL` to test another **local/test** server. Browser checks create real rooms and run four players through turns, refresh/rejoin, offline recovery, and AI practice.
- Browser checks also audit accessibility and layouts from 320 px to desktop, and save screenshots under `test-results/` (ignored by git).
- Run `npm run test:replay --prefix tests` for deterministic real-backend rematch, series, reaction, preferences, and deck-recycling checks. It starts and stops its own loopback-only fixture server on port 5001. Set `TEST_PYTHON` to your Python interpreter path if needed, or `BROWSER_FIXTURE_PORT` to another unused port. Fixture setup is authenticated with an ephemeral key and exists only in the separate test entry point, never in the production server.
- Set `PLAYWRIGHT_BROWSER=webkit` to run either browser suite in WebKit (install it with `npx --prefix tests playwright install webkit`). Browser emulation does not replace testing sound/haptics on physical devices.
- With a local game server running, `npm run test:music --prefix tests` checks actual synthesized audio output, opt-in playback, volume, preference migration, lifecycle pause/resume, and mobile accessibility. It uses `GAME_URL` and `PLAYWRIGHT_BROWSER` like the smoke suite.
- The replay suite also covers all three powers: target/cancel previews, full-turn costs, yellow rolls, winning moves, private hands, refresh/rejoin, and host Power Play changes at 320px.
- Browser code and styles are in `static/game.js` and `static/game.css`; no frontend build step is needed.

## 📁 Project Structure

- `game_server.py` - Flask-SocketIO game server
- `web_client.html` - Browser-based game client
- `twenty_dots.py` - Core game logic
- `ai_player.py` - AI opponent logic
- `gui_game.py` - Desktop GUI version (PyQt6)
- `launcher.py` - Game launcher with network options

## 🎮 Desktop Version

For the full-featured desktop version with GUI:

```bash
# Install additional dependencies
pip install PyQt6

# Launch the game
python launcher.py
```

Choose from:
- **Local Game:** Play on one computer with AI
- **Host Network Game:** Create a game others can join
- **Join Network Game:** Connect to someone else's game

## 📖 Documentation

- [Deployment Guide](DEPLOY_TO_RENDER.md) - How to deploy to Render.com
- [Power Cards Guide](POWER_CARDS_README.md) - Special card abilities
- [Landmine Feature](LANDMINE_FEATURE.md) - Trap mechanics
- [Network Guide](NETWORK_README.md) - Multiplayer setup

## 🐛 Troubleshooting

**"Failed to connect to server"**
- Wait 30-60 seconds for free server to wake up
- Check that you're using the correct URL
- Make sure game server is running (if local)

**"Game not found"**
- Verify all players use the exact same Game ID (case-sensitive)
- Host must create the game first

**Players can't join**
- Check firewall settings (local network)
- Ensure all players are on the same WiFi (local network)
- Verify the Game ID matches exactly

## 📝 License

Created by dabeejgames

## 🎉 Have Fun!

Enjoy playing Twenty Dots with your friends!
