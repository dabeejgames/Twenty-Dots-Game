"""
Game Server for Twenty Dots
Manages game state and coordinates multiple networked players
"""
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import json
import os
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
        self.game.shuffle_deck()  # CRITICAL: Shuffle the deck!
        print(f"Created new game {game_id}. First 5 cards in deck: {[(c.location, c.color) for c in self.game.deck[:5]]}")
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
        # Build board with proper format
        board_data = []
        for row_idx, row in enumerate(self.game.grid):
            row_data = []
            for col_idx, dot in enumerate(row):
                if dot:
                    row_data.append({'color': dot.color, 'location': (self.game.rows[row_idx], self.game.columns[col_idx])})
                else:
                    row_data.append(None)
            board_data.append(row_data)
        
        # Get landmines
        landmines_data = []
        for lm in self.game.landmines:
            landmines_data.append({
                'location': lm['location'],
                'color': lm['color'],
                'player': lm['player']
            })
        
        # Get yellow dot position
        yellow_position = None
        if self.game.yellow_dot_position:
            row_idx, col_idx = self.game.yellow_dot_position
            yellow_position = [self.game.rows[row_idx], self.game.columns[col_idx]]
        
        return {
            'board': board_data,
            'players': {name: {
                'score': data['score'],
                'total_dots': data['total_dots'],
                'hand_size': len(data['hand']),
                'discard_pile': []
            } for name, data in self.game.players.items()},
            'current_turn': self.game.get_current_player(),
            'turn_number': getattr(self.game, 'turn_number', 1),
            'deck_size': len(self.game.deck),
            'yellow_dot_position': yellow_position,
            'landmines': landmines_data,
            'can_roll_dice': getattr(self.game, 'can_roll_dice', False)
        }
    
    def get_player_hand(self, player_name):
        """Get specific player's hand"""
        hand = self.game.players[player_name]['hand']
        cards_data = []
        for c in hand:
            # Handle both string and tuple locations
            if isinstance(c.location, tuple):
                loc = c.location
            elif isinstance(c.location, str):
                if c.location == 'PWR':
                    loc = ('P', 'WR')  # Power card marker
                else:
                    loc = (c.location[0], c.location[1])
            else:
                loc = ('?', '?')
            
            card_data = {
                'color': c.color,
                'location': list(loc),
                'power': c.power if hasattr(c, 'power') and c.power else None
            }
            cards_data.append(card_data)
        
        print(f"Sending hand to {player_name}: colors = {[c.color for c in hand]}")
        return cards_data

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
    """Player joins an existing game (creates if doesn't exist)"""
    game_id = data.get('game_id')
    print(f"[JOIN_GAME] Received join_game request for game {game_id}")
    
    # Auto-create game if it doesn't exist (first player)
    if game_id not in games:
        player_name = data.get('player_name', 'Player 1')
        print(f"[JOIN_GAME] Game doesn't exist, creating. First player: {player_name}")
        game_session = GameSession(game_id, request.sid)
        success, message = game_session.add_player(request.sid, player_name)
        
        if not success:
            emit('error', {'message': message})
            return
        
        games[game_id] = game_session
        join_room(game_id)
        
        emit('join_success', {
            'game_id': game_id,
            'player_name': player_name,
            'players': game_session.player_order
        })
        print(f"[JOIN_GAME] Game auto-created: {game_id} by {player_name}. Player order: {game_session.player_order}")
        return
    
    # Game exists, join it
    game_session = games[game_id]
    player_name = data.get('player_name', f'Player {len(game_session.players) + 1}')
    print(f"[JOIN_GAME] Game exists. Second player joining: {player_name}")
    
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
    
    # Auto-start game when 2 players join
    if len(game_session.player_order) >= 2 and not game_session.started:
        print(f"[AUTO_START] Auto-starting game {game_id} with {len(game_session.player_order)} players")
        print(f"[AUTO_START] Player order: {game_session.player_order}")
        
        # Initialize game
        num_players = len(game_session.player_order)
        game_session.game = TwentyDots(num_players=num_players, difficulty='easy', ai_opponents={})
        print(f"[AUTO_START] Created TwentyDots with num_players={num_players}. Initial player names: {list(game_session.game.players.keys())}")
        game_session.game.shuffle_deck()  # SHUFFLE THE NEW GAME!
        
        # Update player names in the game
        old_names = list(game_session.game.players.keys())
        for i, pname in enumerate(game_session.player_order):
            if i < len(old_names):
                old_name = old_names[i]
                print(f"[AUTO_START] Renaming player {i}: {old_name} -> {pname}")
                game_session.game.players[pname] = game_session.game.players.pop(old_name)
        
        print(f"[AUTO_START] After renaming, player names: {list(game_session.game.players.keys())}")
        print(f"[AUTO_START] Current player (idx=0): {game_session.game.get_current_player()}")
        
        game_session.game.deal_cards(5)
        game_session.started = True
        
        # Send game state to all players
        game_state = game_session.get_game_state()
        emit('game_started', game_state, room=game_id)
        
        # Send each player their hand privately
        for sid, player_info in game_session.players.items():
            if not player_info['is_ai'] and player_info['connected']:
                hand = game_session.get_player_hand(player_info['name'])
                socketio.emit('your_hand', {'hand': hand}, room=sid)
        
        print(f"Game {game_id} auto-started with players: {game_session.player_order}")

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
    cards_data = data.get('cards')  # List of {color, location, power}
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    player_name = game_session.get_player_name(request.sid)
    
    if not player_name:
        emit('error', {'message': 'You are not in this game'})
        return
    
    if game_session.game.get_current_player() != player_name:
        emit('error', {'message': 'Not your turn'})
        return
    
    # Convert cards data back to Card objects
    from twenty_dots import Card
    hand = game_session.game.players[player_name]['hand']
    cards_to_play = []
    
    for card_data in cards_data:
        # Find matching card in hand
        for card in hand:
            card_loc = card.location if isinstance(card.location, str) else f"{card.location[0]}{card.location[1]}"
            req_loc = f"{card_data['location'][0]}{card_data['location'][1]}"
            
            if card.color == card_data['color'] and card_loc == req_loc:
                cards_to_play.append(card)
                break
    
    if len(cards_to_play) != len(cards_data):
        emit('error', {'message': 'Invalid cards selected'})
        return
    
    if len(cards_to_play) > 2:
        emit('error', {'message': 'Cannot play more than 2 cards per turn'})
        return
    
    # Play each card
    matches_made = False
    for card in cards_to_play:
        # Remove card from hand
        hand.remove(card)
        
        # Place dot on board
        if card.power:
            # Handle power cards (simplified for now)
            continue
            
        # Regular card - place dot
        row = card.location[0] if isinstance(card.location, tuple) else card.location[0]
        col = card.location[1] if isinstance(card.location, tuple) else card.location[1]
        
        success, replaced_color = game_session.game.place_card_dot(card)
        
        if success:
            # Check for matches
            match = game_session.game.check_line_match(row, col, card.color)
            if match:
                matches_made = True
                game_session.game.collect_dots(match, player_name, card.color)
    
    # Draw cards back to 5
    while len(hand) < 5 and game_session.game.deck:
        game_session.game.draw_card(player_name)
    
    # If matches were made, allow player to roll dice for yellow dot
    if matches_made:
        game_session.game.can_roll_dice = True
    
    # Broadcast updated game state
    game_state = game_session.get_game_state()
    emit('game_updated', game_state, room=game_id)
    
    # Send updated hand to all players
    for sid, player_info in game_session.players.items():
        if not player_info['is_ai'] and player_info['connected']:
            hand = game_session.get_player_hand(player_info['name'])
            socketio.emit('your_hand', {'hand': hand}, room=sid)
    
    print(f"{player_name} played {len(cards_to_play)} card(s) in game {game_id}")

@socketio.on('end_turn')
def handle_end_turn(data):
    """Player ends their turn"""
    game_id = data.get('game_id')
    print(f"[END_TURN] Received end_turn request for game {game_id}")
    
    if game_id not in games:
        print(f"[END_TURN] ERROR: Game {game_id} not found")
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    player_name = game_session.get_player_name(request.sid)
    print(f"[END_TURN] Player name from session: {player_name}")
    
    if not player_name:
        print(f"[END_TURN] ERROR: Player not found in session {request.sid}")
        emit('error', {'message': 'You are not in this game'})
        return
    
    current_player = game_session.game.get_current_player()
    print(f"[END_TURN] Current player: {current_player}, Ending player: {player_name}")
    
    if current_player != player_name:
        print(f"[END_TURN] ERROR: Not this player's turn! Current={current_player}, Request from={player_name}")
        emit('error', {'message': 'Not your turn'})
        return
    
    print(f"[END_TURN] Validations passed. Drawing cards...")
    # Draw cards to 5 before ending turn
    hand = game_session.game.players[player_name]['hand']
    cards_drawn = 0
    while len(hand) < 5 and game_session.game.deck:
        game_session.game.draw_card(player_name)
        cards_drawn += 1
    print(f"[END_TURN] Drew {cards_drawn} cards. Hand size now: {len(hand)}")
    
    print(f"[END_TURN] Current player index before: {game_session.game.current_player_idx}")
    # Move to next turn
    game_session.game.next_player()
    # Reset dice rolling flag
    game_session.game.can_roll_dice = False
    print(f"[END_TURN] Current player index after: {game_session.game.current_player_idx}")
    print(f"[END_TURN] New current player: {game_session.game.get_current_player()}")
    
    # Broadcast updated game state
    game_state = game_session.get_game_state()
    print(f"[END_TURN] Broadcasting game state with current_turn: {game_state['current_turn']}")
    emit('game_updated', game_state, room=game_id)
    
    # Send hand to all players
    print(f"[END_TURN] Sending hands to {len(game_session.players)} players")
    for sid, player_info in game_session.players.items():
        if not player_info['is_ai'] and player_info['connected']:
            player_hand = game_session.get_player_hand(player_info['name'])
            socketio.emit('your_hand', {'hand': player_hand}, room=sid)
            print(f"[END_TURN] Sent hand to {player_info['name']}")
    
    print(f"[END_TURN] Turn ended successfully. Now: {game_session.game.get_current_player()}")

@socketio.on('roll_dice')
def handle_roll_dice(data):
    """Player rolls dice for yellow wild dot"""
    game_id = data.get('game_id')
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    player_name = game_session.get_player_name(request.sid)
    
    if not player_name:
        emit('error', {'message': 'You are not in this game'})
        return
    
    if game_session.game.get_current_player() != player_name:
        emit('error', {'message': 'Not your turn'})
        return
    
    # Roll for yellow dot position
    row_idx, col_idx = game_session.game.roll_dice()
    
    # Place yellow dot
    from twenty_dots import Dot
    old_dot = game_session.game.grid[row_idx][col_idx]
    game_session.game.grid[row_idx][col_idx] = Dot('yellow')
    game_session.game.yellow_dot_position = (row_idx, col_idx)
    
    # Check for matches created by yellow dot
    row = game_session.game.rows[row_idx]
    col = game_session.game.columns[col_idx]
    match = game_session.game.check_line_match(row, col, 'yellow')
    
    if match:
        # Collect the match with yellow
        game_session.game.collect_dots(match, player_name, 'yellow')
    
    # Reset the roll dice flag
    game_session.game.can_roll_dice = False
    
    # Broadcast updated game state
    game_state = game_session.get_game_state()
    emit('game_updated', game_state, room=game_id)
    
    # Send updated hand to all players
    for sid, player_info in game_session.players.items():
        if not player_info['is_ai'] and player_info['connected']:
            player_hand = game_session.get_player_hand(player_info['name'])
            socketio.emit('your_hand', {'hand': player_hand}, room=sid)
    
    print(f"{player_name} rolled dice, placed yellow at {row}{col}")

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

@app.route('/')
def index():
    """Serve the web client"""
    return send_from_directory('.', 'web_client.html')

@app.route('/favicon.ico')
def favicon():
    """Return empty favicon to prevent 404 errors"""
    return '', 204

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    try:
        return send_from_directory('.', path)
    except:
        return '', 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("Starting Twenty Dots Game Server...")
    print(f"Server will be accessible at http://0.0.0.0:{port}")
    print(f"Web client at: http://0.0.0.0:{port}/web_client.html")
    print("Deck shuffle: ENABLED")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
