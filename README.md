# 🎮 Twenty Dots Game

A strategic multiplayer board game where players compete to collect colored dots by forming lines on a 6x6 grid.

## 🌐 Play Online

**Live Demo:** [https://twenty-dots-game.onrender.com/web_client.html](https://twenty-dots-game.onrender.com/web_client.html)

⚠️ **First load may take 30-60 seconds** as the free server wakes up.

## 🎯 How to Play

1. **Start a Game:**
   - First player opens the web client
   - Leaves "Server IP Address" blank (uses same server)
   - Enters a unique Game ID (e.g., "game_123")
   - Enters their name and clicks "Join Game"

2. **Join a Game:**
   - Other players open the same URL
   - Leave "Server IP Address" blank
   - Enter the SAME Game ID
   - Enter their name and click "Join Game"

3. **Game Rules:**
   - 2-4 players
   - Play up to 2 cards per turn
   - Match 4+ dots in a line (horizontal, vertical, or diagonal) to score
   - First to 20 dots wins (Easy mode)
   - Yellow wild dots can complete any color match

## 🚀 Features

- **Multiplayer Support:** 2-4 players online
- **Power Cards:** Special abilities like dot swaps, removals, and wildcards
- **Landmines:** Strategic traps for opponents
- **AI Opponents:** Play against computer players
- **Real-time Updates:** Instant game state synchronization

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
4. Friends enter your IP in "Server IP Address" field
5. Everyone uses the same Game ID

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
