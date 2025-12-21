# Twenty Dots - Network Multiplayer

## What I've Implemented

I've created a complete network multiplayer system for Twenty Dots! Here's what was added:

### New Files Created:

1. **game_server.py** - The game server that manages game state and coordinates players
2. **network_client.py** - Handles communication between the GUI and server
3. **launcher.py** - Main menu to choose game mode
4. **gui_game_network.py** - Network-enabled GUI for playing online

### How to Use:

## To Play on Separate Devices:

### Option 1: Host a Game
1. Run `launcher.py` on your computer
2. Click "Host Network Game"
3. Enter a Game ID (e.g., "game_001")
4. Enter your name
5. Choose how many AI players (0-3)
6. Click "Create Game"
7. Wait for other players to join
8. When ready, click "Start Game"

### Option 2: Join a Game
1. Run `launcher.py` on another device
2. Click "Join Network Game"
3. Enter the host's IP address (e.g., 192.168.1.100)
4. Enter the Game ID (must match the host's)
5. Enter your name
6. Click "Join Game"
7. Wait for host to start

### Option 3: Play Locally (Original Mode)
1. Run `launcher.py`
2. Click "Play Local Game"
3. Play as before with AI opponents on one device

## What You Need to Do:

### 1. Find Your IP Address (If Hosting):
On the host computer, open PowerShell and run:
```powershell
ipconfig
```
Look for "IPv4 Address" (usually looks like 192.168.1.xxx)

### 2. Make Sure Devices Are on Same Network:
- All players must be connected to the same WiFi/network
- Firewall might need to allow port 5000

### 3. To Start Playing:

**On Host Computer:**
```powershell
cd "C:\Users\ProPetro\OneDrive\Documents\python_projects\Twenty Dots v.1"
.\.venv\Scripts\python.exe launcher.py
```

**On Other Devices:**
- Install Python and required packages (PyQt6, python-socketio)
- Copy the game files to their computer
- Run launcher.py
- Use host's IP address when joining

### Features:
- ✅ Up to 4 players on different devices
- ✅ Mix of human and AI players
- ✅ Real-time game state synchronization
- ✅ Host can start game when ready
- ✅ Automatic turn management
- ✅ All players see the same board

### Technical Notes:
- Server runs on port 5000
- Uses WebSocket (SocketIO) for real-time communication
- Game state managed on server, GUIs are just viewers
- Host computer must keep server running

## Troubleshooting:

**Can't connect?**
- Make sure server is running (launcher starts it automatically for host)
- Check firewall settings
- Verify you're on the same network
- Use "localhost" if testing on same computer

**Game not starting?**
- Need at least 2 players total (human + AI)
- Only host can start the game

Let me know if you need help setting it up or have questions!
