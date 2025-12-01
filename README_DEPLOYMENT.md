# Twenty Dots - Online Deployment Guide

## Quick Start - Deploy to Render (FREE)

### 1. Push to GitHub
Your code is already on GitHub at: `https://github.com/dabeejgames/Twenty-Dots-Game`

### 2. Deploy to Render
1. Go to [render.com](https://render.com) and sign up (free)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository: `dabeejgames/Twenty-Dots-Game`
4. Configure:
   - **Name**: `twenty-dots-game` (or any name you want)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python game_server.py`
   - **Plan**: Select **Free**

5. Click "Create Web Service"

### 3. Get Your Game URL
After deployment (takes 2-3 minutes), Render will give you a URL like:
`https://twenty-dots-game.onrender.com`

### 4. Update web_client.html
Change the default server from `localhost` to your Render URL

### 5. Share and Play!
Players can access the game at:
`https://twenty-dots-game.onrender.com/web_client.html`

## Important Notes

### Port Configuration
Render automatically assigns a PORT environment variable. The game server needs to use this.

### Free Tier Limitations
- Server spins down after 15 minutes of inactivity
- Takes ~30 seconds to wake up when someone connects
- Perfect for casual gaming with friends!

## Alternative: Play on Local Network

### For Local Network Play (Free, No Deploy Needed):
1. Run both servers on your computer:
   ```
   python game_server.py  # In one terminal
   python web_server.py   # In another terminal
   ```

2. Find your local IP address:
   - Windows: `ipconfig` (look for IPv4 Address)
   - Mac/Linux: `ifconfig` (look for inet)

3. Share with friends on same WiFi:
   - They visit: `http://YOUR_IP:8000/web_client.html`
   - Enter your IP in the "Server IP Address" field
   - Everyone uses same Game ID

## Troubleshooting

### "Failed to connect to server"
- Make sure game_server.py is running
- Check firewall settings
- For Render: wait for deployment to complete

### "Game not found"
- Make sure all players use the exact same Game ID
- Game IDs are case-sensitive

### Players can't join
- Verify everyone is using the correct server IP
- On Render, use the full URL without port number
