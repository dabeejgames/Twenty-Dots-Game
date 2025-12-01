"""
Game Server for Twenty Dots
Manages game state and coordinates multiple networked players
"""
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import json
from twenty_dots import TwentyDots
from ai_player import AIPlayer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'twentydots_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Active games dictionary: game_id -> game_data
games = {}

class GameSession:
    def __init__(self, game_id, host_sid):
        self.game_id = game_id
        self.game = TwentyDots()
        self.players = {}  # sid -> player_info
        self.player_order = []  # List of player names in turn order
        self.ai_players = {}  # player_name -> AIPlayer instance
        self.host_sid = host_sid
        self.started = False
        
    def add_player(self, sid, player_name, is_ai=False):
        """Add a player to the game"""
        if len(self.players) >= 4:
            return False, "Game is full"
        
        if player_name in self.player_order:
            return False, f"Player name '{player_name}' already taken"
            
        self.players[sid] = {
            'name': player_name,
            'is_ai': is_ai,
            'connected': True
        }
        self.player_order.append(player_name)
        
        if is_ai:
            self.ai_players[player_name] = AIPlayer('medium')
        
        return True, "Player added"
    
    def remove_player(self, sid):
        """Remove a player from the game"""
        if sid in self.players:
            player_name = self.players[sid]['name']
            self.player_order.remove(player_name)
            if player_name in self.ai_players:
                del self.ai_players[player_name]
            del self.players[sid]
    
    def get_player_name(self, sid):
        """Get player name from session ID"""
        return self.players.get(sid, {}).get('name')
    
    def get_game_state(self):
        """Get current game state for broadcasting"""
        return {
            'board': [[{'color': dot.color, 'location': dot.location} if dot else None 
                      for dot in row] for row in self.game.grid],
            'players': {name: {
                'score': data['score'],
                'total_dots': data['total_dots'],
                'hand_size': len(data['hand']),
                'discard_pile': [{'color': c.color, 'location': c.location} 
                                for c in data.get('discard_pile', [])[-2:]]
            } for name, data in self.game.players.items()},
            'current_turn': self.game.get_current_player(),
            'turn_number': getattr(self.game, 'turn_number', 1),
            'deck_size': len(self.game.deck)
        }
    
    def get_player_hand(self, player_name):
        """Get specific player's hand"""
        hand = self.game.players[player_name]['hand']
        return [{'color': c.color, 'location': c.location} for c in hand]

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # Find and update player's connection status
    for game_id, game_session in games.items():
        if request.sid in game_session.players:
            game_session.players[request.sid]['connected'] = False
            emit('player_disconnected', {
                'player': game_session.players[request.sid]['name']
            }, room=game_id)

@socketio.on('create_game')
def handle_create_game(data):
    """Host creates a new game"""
    game_id = data.get('game_id', f"game_{len(games)}")
    player_name = data.get('player_name', 'Player 1')
    
    if game_id in games:
        emit('error', {'message': 'Game ID already exists'})
        return
    
    game_session = GameSession(game_id, request.sid)
    success, message = game_session.add_player(request.sid, player_name)
    
    if not success:
        emit('error', {'message': message})
        return
    
    games[game_id] = game_session
    join_room(game_id)
    
    emit('game_created', {
        'game_id': game_id,
        'player_name': player_name,
        'players': game_session.player_order
    })
    print(f"Game created: {game_id} by {player_name}")

@socketio.on('join_game')
def handle_join_game(data):
    """Player joins an existing game"""
    game_id = data.get('game_id')
    player_name = data.get('player_name', f'Player {len(games.get(game_id, {}).players) + 1}')
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    
    if game_session.started:
        emit('error', {'message': 'Game already started'})
        return
    
    success, message = game_session.add_player(request.sid, player_name)
    
    if not success:
        emit('error', {'message': message})
        return
    
    join_room(game_id)
    
    # Notify all players in the room
    emit('player_joined', {
        'player_name': player_name,
        'players': game_session.player_order
    }, room=game_id)
    
    emit('join_success', {
        'game_id': game_id,
        'player_name': player_name,
        'players': game_session.player_order
    })
    
    print(f"{player_name} joined game {game_id}")

@socketio.on('add_ai_player')
def handle_add_ai(data):
    """Host adds an AI player"""
    game_id = data.get('game_id')
    ai_name = data.get('ai_name', 'AI Player')
    difficulty = data.get('difficulty', 'medium')
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    
    if request.sid != game_session.host_sid:
        emit('error', {'message': 'Only host can add AI players'})
        return
    
    # Use a dummy SID for AI
    ai_sid = f"ai_{ai_name}"
    success, message = game_session.add_player(ai_sid, ai_name, is_ai=True)
    
    if not success:
        emit('error', {'message': message})
        return
    
    game_session.ai_players[ai_name].difficulty = difficulty
    
    emit('player_joined', {
        'player_name': ai_name,
        'players': game_session.player_order,
        'is_ai': True
    }, room=game_id)
    
    print(f"AI player {ai_name} added to game {game_id}")

@socketio.on('start_game')
def handle_start_game(data):
    """Host starts the game"""
    game_id = data.get('game_id')
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    
    if request.sid != game_session.host_sid:
        emit('error', {'message': 'Only host can start the game'})
        return
    
    if len(game_session.player_order) < 2:
        emit('error', {'message': 'Need at least 2 players to start'})
        return
    
    # Initialize game with players
    # Build ai_opponents dict for TwentyDots constructor
    ai_opponents = {}
    for player_name in game_session.player_order:
        if player_name in game_session.ai_players:
            ai_opponents[player_name] = 'medium'
    
    # Create new game with correct number of players
    num_players = len(game_session.player_order)
    game_session.game = TwentyDots(num_players=num_players, difficulty='easy', ai_opponents=ai_opponents)
    
    # Update player names in the game
    old_names = list(game_session.game.players.keys())
    for i, player_name in enumerate(game_session.player_order):
        if i < len(old_names):
            # Rename the player
            old_name = old_names[i]
            game_session.game.players[player_name] = game_session.game.players.pop(old_name)
    
    game_session.game.deal_cards(5)  # Deal 5 cards to each player
    game_session.started = True
    
    # Send game state to all players
    game_state = game_session.get_game_state()
    emit('game_started', game_state, room=game_id)
    
    # Send each player their hand privately
    for sid, player_info in game_session.players.items():
        if not player_info['is_ai'] and player_info['connected']:
            hand = game_session.get_player_hand(player_info['name'])
            socketio.emit('your_hand', {'hand': hand}, room=sid)
    
    print(f"Game {game_id} started with players: {game_session.player_order}")

@socketio.on('play_cards')
def handle_play_cards(data):
    """Player plays one or more cards"""
    game_id = data.get('game_id')
    cards_data = data.get('cards')  # List of {color, location}
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    player_name = game_session.get_player_name(request.sid)
    
    if not player_name:
        emit('error', {'message': 'You are not in this game'})
        return
    
    if game_session.game.current_turn != player_name:
        emit('error', {'message': 'Not your turn'})
        return
    
    # Convert cards data back to Card objects
    from twenty_dots import Card
    cards = [Card(c['color'], tuple(c['location'])) for c in cards_data]
    
    # Validate and play cards
    success, message = game_session.game.play_cards(player_name, cards)
    
    if not success:
        emit('error', {'message': message})
        return
    
    # Broadcast updated game state
    game_state = game_session.get_game_state()
    emit('game_updated', game_state, room=game_id)
    
    # Send updated hand to player
    hand = game_session.get_player_hand(player_name)
    emit('your_hand', {'hand': hand})
    
    print(f"{player_name} played {len(cards)} card(s) in game {game_id}")

@socketio.on('end_turn')
def handle_end_turn(data):
    """Player ends their turn"""
    game_id = data.get('game_id')
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    player_name = game_session.get_player_name(request.sid)
    
    if not player_name:
        emit('error', {'message': 'You are not in this game'})
        return
    
    if game_session.game.current_turn != player_name:
        emit('error', {'message': 'Not your turn'})
        return
    
    # Move to next turn
    game_session.game.next_turn()
    
    # Broadcast updated game state
    game_state = game_session.get_game_state()
    emit('game_updated', game_state, room=game_id)
    
    # Send hand to new current player
    next_player = game_session.game.current_turn
    for sid, player_info in game_session.players.items():
        if player_info['name'] == next_player and not player_info['is_ai']:
            hand = game_session.get_player_hand(next_player)
            socketio.emit('your_hand', {'hand': hand}, room=sid)
            break
    
    # If next player is AI, execute their turn
    if next_player in game_session.ai_players:
        execute_ai_turn(game_session, next_player)
    
    print(f"Turn ended. Now: {next_player}")

def execute_ai_turn(game_session, ai_name):
    """Execute an AI player's turn"""
    ai_player = game_session.ai_players[ai_name]
    
    # AI chooses cards to play
    cards = ai_player.choose_cards(
        game_session.game.players[ai_name]['hand'],
        game_session.game.grid
    )
    
    if cards:
        success, message = game_session.game.play_cards(ai_name, cards)
        if not success:
            print(f"AI {ai_name} play failed: {message}")
    
    # AI ends turn
    game_session.game.next_turn()
    
    # Broadcast updated game state
    game_state = game_session.get_game_state()
    socketio.emit('game_updated', game_state, room=game_session.game_id)
    
    # If next player is also AI, continue
    next_player = game_session.game.current_turn
    if next_player in game_session.ai_players:
        socketio.sleep(1)  # Brief delay for visibility
        execute_ai_turn(game_session, next_player)
    else:
        # Send hand to human player
        for sid, player_info in game_session.players.items():
            if player_info['name'] == next_player:
                hand = game_session.get_player_hand(next_player)
                socketio.emit('your_hand', {'hand': hand}, room=sid)
                break

@socketio.on('list_games')
def handle_list_games():
    """List all available games"""
    available_games = []
    for game_id, game_session in games.items():
        if not game_session.started:
            available_games.append({
                'game_id': game_id,
                'players': len(game_session.players),
                'max_players': 4,
                'player_names': game_session.player_order
            })
    
    emit('games_list', {'games': available_games})

if __name__ == '__main__':
    print("Starting Twenty Dots Game Server...")
    print("Server will be accessible at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
