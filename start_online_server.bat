@echo off
echo Starting Twenty Dots Online Game Server...
echo.
echo Players can access the game at:
echo   http://localhost:5000/web_client.html (this device)
echo   http://YOUR_IP_ADDRESS:5000/web_client.html (other devices)
echo.
echo To stop the server, press Ctrl+C
echo.
.venv\Scripts\python.exe game_server.py
pause
