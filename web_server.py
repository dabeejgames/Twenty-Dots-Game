"""
Simple HTTP server to serve the web client
Run this along with the game server to allow web browsers to connect
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

if __name__ == '__main__':
    port = 8000
    server_address = ('', port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    
    print(f"\n{'='*60}")
    print(f"Web Client Server Running!")
    print(f"{'='*60}")
    print(f"\nPlayers can connect from their browsers at:")
    print(f"  http://localhost:8000/web_client.html  (this device)")
    print(f"  http://[YOUR_IP]:8000/web_client.html  (other devices)")
    print(f"\nPress Ctrl+C to stop")
    print(f"{'='*60}\n")
    
    httpd.serve_forever()
