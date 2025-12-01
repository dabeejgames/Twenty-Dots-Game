"""
Network Client for Twenty Dots
Handles communication with the game server
"""
import socketio as sio_module
from PyQt6.QtCore import QObject, pyqtSignal
import json

class NetworkClient(QObject):
    # Signals for communicating with GUI
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    game_created = pyqtSignal(dict)
    game_joined = pyqtSignal(dict)
    player_joined = pyqtSignal(dict)
    game_started = pyqtSignal(dict)
    game_updated = pyqtSignal(dict)
    your_hand = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    games_list_received = pyqtSignal(list)
    
    def __init__(self, server_url='http://localhost:5000'):
        super().__init__()
        self.server_url = server_url
        self.sio = sio_module.Client()
        self.game_id = None
        self.player_name = None
        self.connected_to_server = False
        
        # Register event handlers
        self.sio.on('connect', self._on_connect)
        self.sio.on('disconnect', self._on_disconnect)
        self.sio.on('connected', self._on_connected)
        self.sio.on('game_created', self._on_game_created)
        self.sio.on('join_success', self._on_join_success)
        self.sio.on('player_joined', self._on_player_joined)
        self.sio.on('game_started', self._on_game_started)
        self.sio.on('game_updated', self._on_game_updated)
        self.sio.on('your_hand', self._on_your_hand)
        self.sio.on('error', self._on_error)
        self.sio.on('games_list', self._on_games_list)
    
    def connect_to_server(self):
        """Connect to the game server"""
        import time
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"Connection attempt {attempt + 1}/{max_retries} to {self.server_url}")
                self.sio.connect(self.server_url, wait_timeout=10)
                self.connected_to_server = True
                print("Successfully connected!")
                return True
            except Exception as e:
                print(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    self.error_occurred.emit(f"Failed to connect after {max_retries} attempts: {str(e)}")
                    return False
    
    def disconnect_from_server(self):
        """Disconnect from the game server"""
        if self.connected_to_server:
            self.sio.disconnect()
            self.connected_to_server = False
    
    def create_game(self, game_id, player_name):
        """Create a new game"""
        self.game_id = game_id
        self.player_name = player_name
        self.sio.emit('create_game', {
            'game_id': game_id,
            'player_name': player_name
        })
    
    def join_game(self, game_id, player_name):
        """Join an existing game"""
        self.game_id = game_id
        self.player_name = player_name
        self.sio.emit('join_game', {
            'game_id': game_id,
            'player_name': player_name
        })
    
    def add_ai_player(self, ai_name, difficulty='medium'):
        """Add an AI player (host only)"""
        self.sio.emit('add_ai_player', {
            'game_id': self.game_id,
            'ai_name': ai_name,
            'difficulty': difficulty
        })
    
    def start_game(self):
        """Start the game (host only)"""
        self.sio.emit('start_game', {
            'game_id': self.game_id
        })
    
    def play_cards(self, cards):
        """Send card play action to server"""
        # Convert Card objects to dict
        cards_data = [{'color': c.color, 'location': list(c.location)} for c in cards]
        self.sio.emit('play_cards', {
            'game_id': self.game_id,
            'cards': cards_data
        })
    
    def end_turn(self):
        """End current turn"""
        self.sio.emit('end_turn', {
            'game_id': self.game_id
        })
    
    def list_games(self):
        """Request list of available games"""
        self.sio.emit('list_games')
    
    # Event handlers
    def _on_connect(self):
        print("Connected to server")
    
    def _on_disconnect(self):
        print("Disconnected from server")
        self.connected_to_server = False
        self.disconnected.emit()
    
    def _on_connected(self, data):
        print(f"Session ID: {data.get('sid')}")
        self.connected.emit()
    
    def _on_game_created(self, data):
        print(f"Game created: {data}")
        self.game_created.emit(data)
    
    def _on_join_success(self, data):
        print(f"Joined game: {data}")
        self.game_joined.emit(data)
    
    def _on_player_joined(self, data):
        print(f"Player joined: {data}")
        self.player_joined.emit(data)
    
    def _on_game_started(self, data):
        print("Game started!")
        self.game_started.emit(data)
    
    def _on_game_updated(self, data):
        print("Game state updated")
        self.game_updated.emit(data)
    
    def _on_your_hand(self, data):
        print(f"Received hand update: {len(data.get('hand', []))} cards")
        self.your_hand.emit(data)
    
    def _on_error(self, data):
        error_msg = data.get('message', 'Unknown error')
        print(f"Error: {error_msg}")
        self.error_occurred.emit(error_msg)
    
    def _on_games_list(self, data):
        games = data.get('games', [])
        print(f"Received {len(games)} available games")
        self.games_list_received.emit(games)
