"""
Start all servers needed for Twenty Dots multiplayer
"""
import subprocess
import sys
import os
import time

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = sys.executable
    
    print("\n" + "="*60)
    print("Starting Twenty Dots Multiplayer Servers")
    print("="*60)
    
    # Start game server
    print("\n[1/2] Starting Game Server (port 5000)...")
    game_server = subprocess.Popen(
        [python_exe, os.path.join(script_dir, "game_server.py")],
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )
    
    time.sleep(2)
    
    # Start web server
    print("[2/2] Starting Web Server (port 8000)...")
    web_server = subprocess.Popen(
        [python_exe, os.path.join(script_dir, "web_server.py")],
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )
    
    time.sleep(1)
    
    print("\n" + "="*60)
    print("✅ All servers started!")
    print("="*60)
    print("\nNOW YOU NEED TO:")
    print("1. Run launcher.py and click 'Host Network Game'")
    print("2. Create a game and add AI players")
    print("3. Share the connection info with players:")
    print(f"\n   Web Client URL: http://localhost:8000/web_client.html")
    print(f"   (Replace 'localhost' with your IP for other devices)")
    print("\n" + "="*60)
    print("\nPress Ctrl+C to stop all servers")
    print("="*60)
    
    try:
        # Keep script running
        game_server.wait()
    except KeyboardInterrupt:
        print("\n\nStopping servers...")
        game_server.terminate()
        web_server.terminate()
        print("Servers stopped.")

if __name__ == '__main__':
    main()
