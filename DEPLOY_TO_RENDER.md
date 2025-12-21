# 🎮 Deploy Twenty Dots to Render.com (FREE!)

## Step-by-Step Deployment Guide

### 1. Sign Up for Render
1. Go to [render.com](https://render.com)
2. Click **"Get Started"**
3. Sign up with your GitHub account (recommended) or email

### 2. Connect Your GitHub Repository
1. Once logged in, click **"New +"** in the top right
2. Select **"Web Service"**
3. Click **"Connect GitHub"** if not already connected
4. Find and select your repository: **`Twenty-Dots-Game`**

### 3. Configure the Web Service

Fill in these settings:

- **Name**: `twenty-dots-game` (or whatever you like - this will be in your URL)
- **Region**: Choose closest to you (e.g., Oregon USA)
- **Branch**: `main`
- **Root Directory**: Leave blank
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python game_server.py`
- **Instance Type**: **Free**

### 4. Click "Create Web Service"

Render will now:
- Pull your code from GitHub
- Install dependencies (Flask, Socket.IO, etc.)
- Start your game server
- Give you a public URL

This takes about 2-3 minutes.

### 5. Get Your Game URL

After deployment completes, you'll see a URL like:
```
https://twenty-dots-game.onrender.com
```

### 6. Play Your Game!

Share this link with friends:
```
https://twenty-dots-game.onrender.com/web_client.html
```

## How to Play Online

### Starting a Game:
1. **First Player** (Host):
   - Open the URL in browser
   - Leave "Server IP Address" empty
   - Enter a Game ID (e.g., "game_123")
   - Enter your name
   - Click "Join Game"

2. **Other Players**:
   - Open the same URL
   - Leave "Server IP Address" empty
   - Enter the SAME Game ID
   - Enter their name
   - Click "Join Game"

3. **Start Playing**:
   - The first player (host) will see a "Start Game" option once at least 2 players join
   - Game supports 2-4 players

## Important Notes

### Free Tier Limitations
- ✅ **Free forever** - no credit card required
- ⚠️ Server **spins down** after 15 minutes of inactivity
- ⚠️ Takes **~30 seconds** to wake up when someone connects
- ⚠️ Limited to 750 free hours per month

### Tips:
- The server wakes up automatically when players connect
- Keep the game window open to keep server active
- Perfect for casual gaming sessions with friends!

## Troubleshooting

### "Failed to connect to server"
- Wait 30-60 seconds for server to wake up
- Refresh the page
- Check Render dashboard to ensure deployment succeeded

### "Game not found"
- Make sure all players use the EXACT same Game ID (case-sensitive)
- The host must join first

### Players can't join
- Verify everyone is using the correct URL
- Make sure Game ID matches exactly

## Alternative: Play on Local Network (No Deploy Needed)

If you want to play without deploying online:

1. **Run the server locally**:
   - Double-click `start_online_server.bat`
   - Or run: `python game_server.py`

2. **Find your local IP address**:
   - Windows: `ipconfig` (look for IPv4 Address like 192.168.1.X)

3. **Share with friends on same WiFi**:
   - They visit: `http://YOUR_IP:5000/web_client.html`
   - They enter your IP address in "Server IP Address"
   - Everyone uses same Game ID

## Updating Your Deployed Game

Whenever you make changes to your code:

1. Commit and push to GitHub:
   ```
   git add .
   git commit -m "Update game"
   git push
   ```

2. Render automatically re-deploys! (takes 2-3 minutes)

## Support

Having issues? Check:
- Render Dashboard: https://dashboard.render.com
- Render Logs: Click on your service → "Logs" tab
- GitHub repository is updated and synced

---

🎉 **You're all set! Enjoy playing Twenty Dots online with friends!** 🎉
