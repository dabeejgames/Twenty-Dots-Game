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
    def __init__(self, game_id, host_sid, game_mode='twenty_dots', player_count=2):
        self.game_id = game_id
        self.game_mode = game_mode
        self.required_players = player_count  # Store the required player count
        self.game = TwentyDots(num_players=2, difficulty='easy', ai_opponents={}, power_cards=False)
        self.game.shuffle_deck()  # CRITICAL: Shuffle the deck!
        self.game.can_roll_dice = True  # First player must roll to place initial wild dot
        print(f"Created new game {game_id} with mode {game_mode}, requires {player_count} players. First 5 cards in deck: {[(c.location, c.color) for c in self.game.deck[:5]]}")
        self.players = {}  # sid -> player_info
        self.player_order = []  # List of player names in turn order
        self.ai_players = {}  # player_name -> AIPlayer instance
        self.host_sid = host_sid
        self.started = False
        self.discard_piles = {}  # Track discard piles for each player
        self.ai_move_in_progress = False  # Flag to prevent overlapping AI moves
        
    def add_player(self, sid, player_name, is_ai=False):
        """Add a player to the game"""
        if len(self.players) >= self.required_players:
            print(f"[ADD_PLAYER] REJECTED: Game is full. Current: {len(self.players)}, Required: {self.required_players}")
            return False, f"Game is full ({self.required_players} players required)"
        
        print(f"[ADD_PLAYER] Adding {player_name} to game {self.game_id}. Current players: {len(self.players)}, Required: {self.required_players}")
        if player_name in self.player_order:
            return False, f"Player name '{player_name}' already taken"
            
        self.players[sid] = {
            'name': player_name,
            'is_ai': is_ai,
            'connected': True
        }
        self.player_order.append(player_name)
        
        if is_ai:
            self.ai_players[player_name] = AIPlayer('medium')  # Will be updated later if needed
        
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
            'game_id': self.game_id,
            'board': board_data,
            'players': {name: {
                'score': data['score'],
                'total_dots': data['total_dots'],
                'yellow_dots': data.get('yellow_dots', 0),
                'hand_size': len(data['hand']),
                'discard_pile': self.discard_piles.get(name, [])
            } for name, data in self.game.players.items()},
            'current_turn': self.game.get_current_player(),
            'turn_number': getattr(self.game, 'turn_number', 1),
            'deck_size': len(self.game.deck),
            'yellow_dot_position': yellow_position,
            'landmines': landmines_data,
            'can_roll_dice': getattr(self.game, 'can_roll_dice', False),
            'game_mode': self.game_mode
        }
    
    def get_player_hand(self, player_name):
        """Get specific player's hand"""
        hand = self.game.players[player_name]['hand']
        cards_data = []
        for c in hand:
            # Skip power cards for now
            if hasattr(c, 'power') and c.power:
                continue
                
            # Handle both string and tuple locations
            if isinstance(c.location, tuple):
                loc = c.location
            elif isinstance(c.location, str):
                loc = (c.location[0], c.location[1])
            else:
                loc = ('?', '?')
            
            card_data = {
                'color': c.color,
                'location': list(loc),
                'power': None
            }
            cards_data.append(card_data)
        
        print(f"Sending hand to {player_name}: colors = {[c.color for c in hand]}")
        return cards_data
    
    def execute_ai_move(self):
        """Execute AI move if current player is AI"""
        if self.ai_move_in_progress:
            return
        
        current_player = self.game.get_current_player()
        
        if current_player not in self.ai_players:
            return
        
        self.ai_move_in_progress = True
        try:
            ai_player = self.ai_players[current_player]
            hand = self.game.players[current_player]['hand']
            
            # Initialize turn_cards_played if not exists
            if not hasattr(self.game, 'turn_cards_played'):
                self.game.turn_cards_played = {}
            if current_player not in self.game.turn_cards_played:
                self.game.turn_cards_played[current_player] = 0
            
            cards_played_this_turn = self.game.turn_cards_played[current_player]
            
            # AI must roll first if can_roll_dice is True
            if self.game.can_roll_dice:
                print(f"[AI_MOVE] {current_player} must roll first (hand has {len(hand)} cards)")
                # Simulate roll_dice (same as human player)
                self.game.can_roll_dice = False
                row, col = self.game.roll_dice()
                row_idx = self.game.rows.index(row)
                col_idx = self.game.columns.index(col)
                
                # Place yellow dot
                from twenty_dots import Dot
                old_dot = self.game.grid[row_idx][col_idx]
                self.game.grid[row_idx][col_idx] = Dot('yellow')
                self.game.yellow_dot_position = (row_idx, col_idx)
                print(f"[AI_MOVE] {current_player} rolled {row}{col}, placed yellow dot")
                
                # Broadcast updated game state
                socketio.emit('game_updated', self.get_game_state(), room=self.game_id)
                # After rolling, AI needs to play cards
                print(f"[AI_MOVE] {current_player} rolled, now choosing cards to play")
            
            # Check if AI already played 2 cards this turn
            if cards_played_this_turn >= 2:
                print(f"[AI_MOVE] {current_player} already played {cards_played_this_turn} cards, advancing turn")
                self.game.next_player()
                new_player = self.game.get_current_player()
                self.game.turn_cards_played[new_player] = 0
                socketio.emit('game_updated', self.get_game_state(), room=self.game_id)
                import time
                time.sleep(0.5)
                self.ai_move_in_progress = False
                self.execute_ai_move()
                return
            
            # Choose cards to play (up to 2 - cards_played_this_turn)
            cards_needed = 2 - cards_played_this_turn
            cards_to_play_indices = ai_player.choose_cards(hand)[:cards_needed]
            
            if len(cards_to_play_indices) == 0:
                print(f"[AI_MOVE] {current_player} has no cards to play, advancing turn")
                self.game.next_player()
                new_player = self.game.get_current_player()
                self.game.turn_cards_played[new_player] = 0
                socketio.emit('game_updated', self.get_game_state(), room=self.game_id)
                import time
                time.sleep(0.5)
                self.ai_move_in_progress = False
                self.execute_ai_move()
                return
            
            cards_to_play = [hand[i] for i in cards_to_play_indices if i < len(hand)]
            yellow_replaced = False
            yellow_collected = False
            
            # Play the cards (similar to handle_play_cards but for AI)
            for card in cards_to_play:
                if card not in hand:
                    continue
                
                # Remove from hand
                hand.remove(card)
                self.game.turn_cards_played[current_player] += 1
                
                # Place dot on board
                success, replaced_color = self.game.place_card_dot(card)
                if success:
                    # Track if yellow was replaced
                    if replaced_color == 'yellow':
                        yellow_replaced = True
                        self.game.players[current_player]['yellow_dots'] += 1
                        self.game.players[current_player]['total_dots'] += 1
                    elif replaced_color and replaced_color in ['red', 'blue', 'purple', 'green']:
                        self.game.players[current_player]['score'][replaced_color] += 1
                        self.game.players[current_player]['total_dots'] += 1
                    
                    # Check for matches
                    row = card.location[0]
                    col = card.location[1]
                    row_idx = self.game.rows.index(row)
                    col_idx = self.game.columns.index(col)
                    match_result = self.game.check_line_match(row, col, card.color)
                    match, match_color = match_result
                    if match:
                        # Check if yellow dot is in the matched positions
                        for col_idx_m, row_idx_m in match:
                            dot = self.game.grid[row_idx_m][col_idx_m]
                            if dot and dot.color == 'yellow':
                                yellow_collected = True
                                break
                        self.game.collect_dots(match, current_player, match_color)
            
            # After playing cards
            total_played_this_turn = self.game.turn_cards_played[current_player]
            print(f"[AI_MOVE] {current_player} played cards, total this turn: {total_played_this_turn}")
            
            # Check if AI played 2 cards this turn
            if total_played_this_turn >= 2:
                # Draw replacement cards
                while len(hand) < 5 and self.game.deck:
                    self.game.draw_card(current_player)
                
                # If yellow was replaced or collected, AI must roll again
                if yellow_replaced or yellow_collected:
                    self.game.can_roll_dice = True
                    print(f"[AI_MOVE] {current_player} replaced/collected yellow after 2 cards, must roll then end turn")
                    socketio.emit('game_updated', self.get_game_state(), room=self.game_id)
                    import time
                    time.sleep(0.5)
                    self.ai_move_in_progress = False
                    # Roll then end turn
                    self.execute_ai_move()
                    return
                else:
                    # Advance to next player
                    print(f"[AI_MOVE] {current_player} played 2 cards, advancing turn")
                    self.game.can_roll_dice = False
                    self.game.next_player()
                    new_player = self.game.get_current_player()
                    self.game.turn_cards_played[new_player] = 0
                    socketio.emit('game_updated', self.get_game_state(), room=self.game_id)
                    
                    # Check for winner
                    winner_result = self.check_winner()
                    if winner_result:
                        socketio.emit('game_over', {
                            'winner': winner_result['winner'],
                            'condition': winner_result['mode']
                        }, room=self.game_id)
                        return
                    
                    import time
                    time.sleep(0.5)
                    self.ai_move_in_progress = False
                    self.execute_ai_move()
                    return
            else:
                # Still need to play more cards
                if yellow_replaced or yellow_collected:
                    self.game.can_roll_dice = True
                    print(f"[AI_MOVE] {current_player} replaced/collected yellow, must roll again")
                socketio.emit('game_updated', self.get_game_state(), room=self.game_id)
                import time
                time.sleep(0.5)
                self.ai_move_in_progress = False
                self.execute_ai_move()
                return
                
        except Exception as e:
            print(f"[AI_MOVE] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.ai_move_in_progress = False
    
    def check_winner(self):
        """Check if anyone has won based on game_mode"""
        
        # Check if deck is empty - player with most dots wins
        if len(self.game.deck) == 0:
            print(f"[GAME_OVER] Deck is empty, determining winner by total dots")
            max_dots = -1
            winner = None
            for player_name in self.player_order:
                player_data = self.game.players[player_name]
                total = player_data['total_dots']
                print(f"[GAME_OVER] {player_name}: {total} dots")
                if total > max_dots:
                    max_dots = total
                    winner = player_name
            if winner:
                print(f"[GAME_OVER] Winner by deck depletion: {winner} with {max_dots} dots")
                return {'winner': winner, 'mode': 'deck_empty'}
        
        for player_name in self.player_order:
            player_data = self.game.players[player_name]
            
            if self.game_mode == 'twenty_dots':
                if player_data['total_dots'] >= 20:
                    return {'winner': player_name, 'mode': 'twenty_dots'}
            
            elif self.game_mode == 'five_colors':
                # Check if player has 5 of each color (red, blue, green, purple)
                if all(player_data['score'].get(color, 0) >= 5 for color in ['red', 'blue', 'green', 'purple']):
                    return {'winner': player_name, 'mode': 'five_colors'}
            
            elif self.game_mode == 'five_with_yellow':
                # Check if player has 5 yellow dots AND 5 of each color
                yellow_dots = player_data.get('yellow_dots', 0)
                if yellow_dots >= 5 and all(player_data['score'].get(color, 0) >= 5 for color in ['red', 'blue', 'green', 'purple']):
                    return {'winner': player_name, 'mode': 'five_with_yellow'}
        
        return None

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
    player_count = data.get('player_count', 2)
    # Ensure player_count is an integer
    try:
        player_count = int(player_count)
    except (ValueError, TypeError):
        player_count = 2
    print(f"[JOIN_GAME] Received join_game request for game {game_id}, player_count: {player_count} (type: {type(player_count).__name__})")
    
    # Auto-create game if it doesn't exist (first player)
    if game_id not in games:
        player_name = data.get('player_name', 'Player 1')
        game_mode = data.get('game_mode', 'twenty_dots')
        print(f"[JOIN_GAME] Game doesn't exist, creating. First player: {player_name}, mode: {game_mode}, player_count: {player_count}")
        game_session = GameSession(game_id, request.sid, game_mode, player_count)
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
    print(f"[JOIN_GAME] Game exists. Player joining: {player_name}")
    
    game_session = games[game_id]
    
    # Check if this is a reconnecting player
    existing_player_name = None
    for sid, player_info in game_session.players.items():
        if player_info['name'] == player_name:
            existing_player_name = player_name
            print(f"[JOIN_GAME] Player {player_name} is reconnecting to game {game_id}")
            # Update their session ID
            old_sid = sid
            break
    
    if game_session.started and not existing_player_name:
        emit('error', {'message': 'Game already started - cannot add new players'})
        return
    
    if existing_player_name:
        # Reconnecting player - update their session ID
        for sid in list(game_session.players.keys()):
            if game_session.players[sid]['name'] == player_name:
                # Transfer player data to new session
                player_data = game_session.players[sid]
                del game_session.players[sid]
                game_session.players[request.sid] = player_data
                game_session.players[request.sid]['connected'] = True
                print(f"[JOIN_GAME] Updated {player_name}'s session ID from {sid} to {request.sid}")
                break
        
        join_room(game_id)
        
        # Send current game state to reconnecting player
        emit('game_started', game_session.get_game_state())
        
        # Send their hand
        hand = game_session.game.players[player_name]['hand']
        emit('your_hand', {'hand': [card.__dict__ for card in hand]})
        
        print(f"[JOIN_GAME] {player_name} reconnected to game {game_id}")
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
    
    # Auto-start game when required player count is reached
    if len(game_session.player_order) >= game_session.required_players and not game_session.started:
        print(f"[AUTO_START] Auto-starting game {game_id}")
        print(f"[AUTO_START] Players joined: {len(game_session.player_order)}, Required: {game_session.required_players}")
        print(f"[AUTO_START] Player order: {game_session.player_order}")
        
        # Initialize game with correct parameters
        num_players = len(game_session.player_order)
        game_session.game = TwentyDots(num_players=num_players, difficulty='easy', ai_opponents={}, power_cards=False)
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
        
        # Shuffle deck before dealing
        game_session.game.shuffle_deck()
        game_session.game.deal_cards(5)
        game_session.started = True
        
        # Initialize discard piles and turn card counters for all players
        game_session.game.turn_cards_played = {}
        game_session.game.must_advance_after_roll = {}
        for pname in game_session.player_order:
            game_session.discard_piles[pname] = []
            game_session.game.turn_cards_played[pname] = 0
        
        # Player 1 must roll wild dot first - enable roll dice
        game_session.game.can_roll_dice = True
        print(f"[AUTO_START] Set can_roll_dice=True. Player {game_session.game.get_current_player()} must roll first.")
        
        # Send game state to all players
        game_state = game_session.get_game_state()
        emit('game_started', game_state, room=game_id)
        
        # Send each player their hand privately
        for sid, player_info in game_session.players.items():
            if not player_info['is_ai'] and player_info['connected']:
                hand = game_session.get_player_hand(player_info['name'])
                socketio.emit('your_hand', {'hand': hand}, room=sid)
        
        # Execute AI move if starting player is AI (AI must roll first)
        if game_session.game.get_current_player() in game_session.ai_players:
            import threading
            thread = threading.Thread(target=game_session.execute_ai_move)
            thread.daemon = True
            thread.start()
        
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

@socketio.on('start_single_player')
def handle_start_single_player(data):
    """Start a single-player game with AI opponents"""
    player_name = data.get('player_name', 'Player')
    num_players = data.get('num_players', 2)
    difficulty = data.get('difficulty', 'medium')
    game_mode = data.get('game_mode', 'twenty_dots')
    
    # Ensure num_players is an integer
    try:
        num_players = int(num_players)
    except (ValueError, TypeError):
        num_players = 2
    
    # Create a unique game ID for single-player
    import uuid
    game_id = f"sp_{uuid.uuid4().hex[:8]}"
    
    # Create game session
    game_session = GameSession(game_id, request.sid, game_mode, num_players)
    games[game_id] = game_session
    join_room(game_id)
    
    # Add human player
    success, message = game_session.add_player(request.sid, player_name, is_ai=False)
    if not success:
        emit('error', {'message': message})
        return
    
    # Add AI players
    ai_names = ['AI 1', 'AI 2', 'AI 3']
    for i in range(num_players - 1):
        ai_sid = f"ai_{game_id}_{i}"
        ai_name = ai_names[i] if i < len(ai_names) else f"AI {i+1}"
        success, msg = game_session.add_player(ai_sid, ai_name, is_ai=True)
        if success:
            game_session.ai_players[ai_name].difficulty = difficulty
    
    # Initialize game
    game_session.game = TwentyDots(num_players=num_players, difficulty='easy', ai_opponents={}, power_cards=False)
    game_session.game.shuffle_deck()
    
    # Deal initial cards to all players
    game_session.game.deal_cards(5)
    
    # Update player names in the game
    old_names = list(game_session.game.players.keys())
    print(f"[SINGLE_PLAYER] Old player names: {old_names}")
    print(f"[SINGLE_PLAYER] New player order: {game_session.player_order}")
    for i, pname in enumerate(game_session.player_order):
        if i < len(old_names):
            old_name = old_names[i]
            game_session.game.players[pname] = game_session.game.players.pop(old_name)
            print(f"[SINGLE_PLAYER] Renamed {old_name} -> {pname}")
    
    print(f"[SINGLE_PLAYER] Final player names: {list(game_session.game.players.keys())}")
    print(f"[SINGLE_PLAYER] Current player: {game_session.game.get_current_player()}")
    
    # Initialize discard piles and turn_cards_played tracking
    game_session.game.turn_cards_played = {}
    for pname in game_session.player_order:
        game_session.discard_piles[pname] = []
        game_session.game.turn_cards_played[pname] = 0
    
    # First player must roll wild dot
    game_session.game.can_roll_dice = True
    game_session.started = True
    
    # Send game state
    game_state = game_session.get_game_state()
    emit('game_started', game_state, room=game_id)
    
    # Send player their hand privately
    hand = game_session.get_player_hand(player_name)
    emit('your_hand', {'hand': hand})
    
    print(f"Single-player game {game_id} started with {player_name} vs {num_players - 1} AI opponents")

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
    
    print(f"[PLAY_CARDS] Received play_cards from player. Cards: {cards_data}")
    
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
    print(f"[PLAY_CARDS] Hand before: {[(c.color, c.location) for c in hand]}")
    
    cards_to_play = []
    
    for card_data in cards_data:
        # Normalize card location to string format
        if isinstance(card_data['location'], list):
            req_loc = f"{card_data['location'][0]}{card_data['location'][1]}"
        else:
            req_loc = card_data['location']
        
        # Find matching card in hand
        for card in hand:
            # Normalize card location to string format
            card_loc = card.location if isinstance(card.location, str) else f"{card.location[0]}{card.location[1]}"
            
            if card.color == card_data['color'] and card_loc == req_loc:
                cards_to_play.append(card)
                print(f"[PLAY_CARDS] Found matching card: {card.color} at {card_loc}")
                break
    
    print(f"[PLAY_CARDS] Found {len(cards_to_play)} cards to play")
    
    if len(cards_to_play) != len(cards_data):
        print(f"[PLAY_CARDS] ERROR: Could not find all cards. Expected {len(cards_data)}, found {len(cards_to_play)}")
        print(f"[PLAY_CARDS] Requested: {[(c['color'], c['location']) for c in cards_data]}")
        emit('error', {'message': 'Invalid cards selected'})
        return
    
    if len(cards_to_play) > 2:
        emit('error', {'message': 'Cannot play more than 2 cards per turn'})
        return
    
    # Check for duplicate locations
    if len(cards_to_play) == 2:
        loc1 = cards_to_play[0].location if isinstance(cards_to_play[0].location, str) else f"{cards_to_play[0].location[0]}{cards_to_play[0].location[1]}"
        loc2 = cards_to_play[1].location if isinstance(cards_to_play[1].location, str) else f"{cards_to_play[1].location[0]}{cards_to_play[1].location[1]}"
        if loc1 == loc2:
            emit('error', {'message': 'Cannot play 2 cards on the same location in one turn'})
            return
    
    # Track cards played this turn (discard piles now persist across turns)
    if not hasattr(game_session.game, 'turn_cards_played'):
        game_session.game.turn_cards_played = {}
    
    current_player = game_session.game.get_current_player()
    
    # Always reset counter if player hasn't played yet this turn or if it's somehow still at 2
    # (this can happen if there's any desync between client and server)
    if current_player not in game_session.game.turn_cards_played:
        game_session.game.turn_cards_played[current_player] = 0
    
    # If counter is at 2, reset it (means we just started this player's turn after advancing)
    if game_session.game.turn_cards_played[current_player] >= 2:
        print(f"[PLAY_CARDS] Resetting {current_player}'s counter from {game_session.game.turn_cards_played[current_player]} to 0")
        game_session.game.turn_cards_played[current_player] = 0
    
    cards_played_this_turn = game_session.game.turn_cards_played[current_player]
    
    # Prevent playing more cards if already at 2 this turn
    total_played_this_turn = cards_played_this_turn + len(cards_to_play)
    if total_played_this_turn > 2:
        emit('error', {'message': f'Can only play 2 cards per turn. Already played {cards_played_this_turn}'})
        print(f"[PLAY_CARDS] ERROR: {current_player} tried to play {len(cards_to_play)} cards but already played {cards_played_this_turn} this turn")
        return
    
    # Play each card
    matches_made = False
    yellow_replaced = False
    yellow_collected = False
    for card in cards_to_play:
        # Add card to discard pile first
        if player_name not in game_session.discard_piles:
            game_session.discard_piles[player_name] = []
        
        card_info = {
            'location': card.location if isinstance(card.location, str) else f"{card.location[0]}{card.location[1]}",
            'color': card.color
        }
        game_session.discard_piles[player_name].append(card_info)
        print(f"[PLAY_CARDS] Added {card.color} {card.location} to {player_name}'s discard pile")
        
        # Remove card from hand
        hand.remove(card)
        print(f"[PLAY_CARDS] Removed {card.color} {card.location} from hand")
        
        # Place dot on board
        if card.power:
            # Handle power cards (simplified for now)
            continue
        
        # Check if we're placing on yellow
        row = card.location[0]
        col = card.location[1]
        row_idx = game_session.game.rows.index(row)
        col_idx = game_session.game.columns.index(col)
        current_dot = game_session.game.grid[row_idx][col_idx]
        if current_dot and current_dot.color == 'yellow':
            yellow_replaced = True
            print(f"[PLAY_CARDS] Yellow dot will be replaced at {row}{col}")
            
        # Regular card - place dot
        success, replaced_color = game_session.game.place_card_dot(card)
        print(f"[PLAY_CARDS] Placed {card.color} at {row}{col}: success={success}, replaced={replaced_color}")
        
        if success:
            # Award point if we replaced a colored dot (red, blue, purple, green)
            if replaced_color and replaced_color in ['red', 'blue', 'purple', 'green']:
                game_session.game.players[player_name]['score'][replaced_color] += 1
                game_session.game.players[player_name]['total_dots'] += 1
                print(f"[PLAY_CARDS] Awarded point for replacing {replaced_color} dot")
            
            # Track yellow dots collected - when a yellow dot is replaced
            if replaced_color == 'yellow':
                game_session.game.players[player_name]['yellow_dots'] += 1
                game_session.game.players[player_name]['total_dots'] += 1
                print(f"[PLAY_CARDS] {player_name} collected a yellow dot! Total yellow: {game_session.game.players[player_name]['yellow_dots']}")
            
            # Check for matches
            match_result = game_session.game.check_line_match(row, col, card.color)
            match, match_color = match_result
            if match:  # Check if match list has items
                matches_made = True
                # Check if yellow dot is in the matched positions
                for col_idx, row_idx in match:
                    dot = game_session.game.grid[row_idx][col_idx]
                    if dot and dot.color == 'yellow':
                        yellow_collected = True
                        print(f"[PLAY_CARDS] Yellow dot collected in match")
                        break
                game_session.game.collect_dots(match, player_name, match_color)
    
    # If yellow was replaced or collected, allow player to roll again for new yellow
    if yellow_replaced or yellow_collected:
        game_session.game.can_roll_dice = True
        print(f"[PLAY_CARDS] Yellow was replaced/collected - can_roll_dice set to True")
    else:
        game_session.game.can_roll_dice = False
        print(f"[PLAY_CARDS] Yellow not affected - can_roll_dice set to False")
    
    # Auto-advance turn after playing 2 cards THIS TURN
    total_played_this_turn = cards_played_this_turn + len(cards_to_play)
    game_session.game.turn_cards_played[current_player] = total_played_this_turn
    print(f"[PLAY_CARDS] Updated {current_player}'s counter to {total_played_this_turn}")
    
    # Only draw cards when turn is ending (at 2 cards played)
    if total_played_this_turn >= 2:
        print(f"[PLAY_CARDS] {player_name} has played {total_played_this_turn} cards this turn, drawing replacements")
        # Draw cards back to 5 AFTER playing 2 cards
        cards_drawn = 0
        while len(hand) < 5 and game_session.game.deck:
            game_session.game.draw_card(player_name)
            cards_drawn += 1
        print(f"[PLAY_CARDS] Drew {cards_drawn} cards")
        
        # Only advance turn if yellow was NOT replaced or collected
        # If yellow was affected, current player must roll again
        if not (yellow_replaced or yellow_collected):
            print(f"[PLAY_CARDS] Auto-advancing turn (yellow not affected)")
            game_session.game.can_roll_dice = False
            game_session.game.next_player()
            # Reset card counter for new player
            new_player = game_session.game.get_current_player()
            game_session.game.turn_cards_played[new_player] = 0
            print(f"[PLAY_CARDS] Turn advanced to {new_player}")
        else:
            print(f"[PLAY_CARDS] Yellow was affected - {player_name} must roll again")
            # Mark that this player must advance their turn after rolling
            if not hasattr(game_session.game, 'must_advance_after_roll'):
                game_session.game.must_advance_after_roll = {}
            game_session.game.must_advance_after_roll[current_player] = True
            # Keep the current card counter - player will continue from where they left off after rolling
            # DO NOT reset to 0 - they've already played some cards this turn
    else:
        print(f"[PLAY_CARDS] {player_name} has played {total_played_this_turn} card(s) this turn, waiting for more or 2nd card")
    
    # Broadcast updated game state BEFORE modifying discard pile
    game_state = game_session.get_game_state()
    emit('game_updated', game_state, room=game_id)
    
    # Check for winner
    winner_result = game_session.check_winner()
    if winner_result:
        print(f"[PLAY_CARDS] GAME OVER! Winner: {winner_result['winner']} (mode: {winner_result['mode']})")
        emit('game_over', {
            'winner': winner_result['winner'],
            'condition': winner_result['mode']
        }, room=game_id)
        return
    
    # Don't reset discard pile - keep it visible to show what was played
    
    # Send updated hand to all players
    for sid, player_info in game_session.players.items():
        if not player_info['is_ai'] and player_info['connected']:
            hand = game_session.get_player_hand(player_info['name'])
            socketio.emit('your_hand', {'hand': hand}, room=sid)
    
    # Execute AI move if next player is AI
    next_player_name = game_session.game.get_current_player()
    
    if next_player_name in game_session.ai_players:
        import threading
        thread = threading.Thread(target=game_session.execute_ai_move)
        thread.daemon = True
        thread.start()
    
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
    # Don't automatically enable roll dice - it should only be enabled at game start or when yellow is affected
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
    
    # Execute AI move if next player is AI
    next_player = game_session.game.get_current_player()
    print(f"[END_TURN] Next player: {next_player}")
    print(f"[END_TURN] AI players: {list(game_session.ai_players.keys())}")
    print(f"[END_TURN] Is next player AI? {next_player in game_session.ai_players}")
    
    if next_player in game_session.ai_players:
        print(f"[END_TURN] Spawning thread to execute AI move for {next_player}")
        import threading
        thread = threading.Thread(target=game_session.execute_ai_move)
        thread.daemon = True
        thread.start()
    else:
        print(f"[END_TURN] Next player {next_player} is not AI, waiting for player action")
    
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
    
    # Check if this player needs to advance their turn after rolling
    if not hasattr(game_session.game, 'must_advance_after_roll'):
        game_session.game.must_advance_after_roll = {}
    
    # Track if this player must advance turn after rolling
    must_advance = player_name in game_session.game.must_advance_after_roll and game_session.game.must_advance_after_roll[player_name]
    if must_advance:
        print(f"[ROLL_DICE] {player_name} must advance turn after this roll")
    
    # Roll for yellow dot position (returns row, col as strings like 'A', '1')
    row, col = game_session.game.roll_dice()
    row_idx = game_session.game.rows.index(row)
    col_idx = game_session.game.columns.index(col)
    
    print(f"[ROLL_DICE] Rolled {row}{col} (indices: {row_idx}, {col_idx})")
    
    # Place yellow dot
    from twenty_dots import Dot
    old_dot = game_session.game.grid[row_idx][col_idx]
    game_session.game.grid[row_idx][col_idx] = Dot('yellow')
    game_session.game.yellow_dot_position = (row_idx, col_idx)
    print(f"[ROLL_DICE] Placed yellow dot at grid[{row_idx}][{col_idx}] (replaced: {old_dot.color if old_dot else 'empty'})")
    
    # Log surrounding grid state for debugging
    print(f"[ROLL_DICE] Grid around {row}{col}:")
    for check_row in range(max(0, row_idx-2), min(6, row_idx+3)):
        for check_col in range(max(0, col_idx-2), min(6, col_idx+3)):
            dot = game_session.game.grid[check_row][check_col]
            dot_str = f"{dot.color[0].upper()}" if dot else "."
            if check_row == row_idx and check_col == col_idx:
                dot_str = f"[{dot_str}]"  # Mark placed dot
            print(dot_str, end=" ")
        print()
    
    # Check for matches created by yellow dot
    print(f"[ROLL_DICE] About to call check_line_match for {row}{col} (indices {row_idx},{col_idx})")
    match_result = game_session.game.check_line_match(row, col, 'yellow')
    match, match_color = match_result
    
    if match:  # Check if match list has items
        print(f"[ROLL_DICE] check_line_match returned match of {len(match)} positions: {match} (color={match_color})")
        # Collect the match with the detected color (not 'yellow')
        print(f"[ROLL_DICE] MATCH FOUND! Collecting {len(match)} positions for color {match_color}")
        game_session.game.collect_dots(match, player_name, match_color)
        print(f"[ROLL_DICE] After collect_dots, checking player stats...")
        print(f"[ROLL_DICE] {player_name}'s score: {game_session.game.players[player_name]['score']}")
        print(f"[ROLL_DICE] {player_name}'s total_dots: {game_session.game.players[player_name]['total_dots']}")
        # Can roll again if matched
        game_session.game.can_roll_dice = True
    else:
        print(f"[ROLL_DICE] NO MATCH detected at {row}{col}")
        # No match - if player must advance after roll, do it now
        if must_advance:
            print(f"[ROLL_DICE] Advancing {player_name}'s turn after rolling")
            game_session.game.must_advance_after_roll[player_name] = False
            new_player = game_session.game.next_player()
            game_session.game.turn_cards_played[new_player] = 0
            game_session.game.can_roll_dice = False
        else:
            # Normal case - player can now play cards
            game_session.game.can_roll_dice = False
    
    print(f"[ROLL_DICE] {player_name} rolled at {row}{col}. Match: {bool(match)}. can_roll_dice={game_session.game.can_roll_dice}")
    
    # Broadcast updated game state
    game_state = game_session.get_game_state()
    emit('game_updated', game_state, room=game_id)
    
    # Check for winner
    winner_result = game_session.check_winner()
    if winner_result:
        print(f"[ROLL_DICE] GAME OVER! Winner: {winner_result['winner']} (mode: {winner_result['mode']})")
        emit('game_over', {
            'winner': winner_result['winner'],
            'condition': winner_result['mode']
        }, room=game_id)
        return
    
    # Send updated hand to all players
    for sid, player_info in game_session.players.items():
        if not player_info['is_ai'] and player_info['connected']:
            player_hand = game_session.get_player_hand(player_info['name'])
            socketio.emit('your_hand', {'hand': player_hand}, room=sid)
    
    print(f"{player_name} rolled dice, placed yellow at {row}{col}")

@socketio.on('pass_turn')
def handle_pass_turn(data):
    """Player passes their turn without playing cards"""
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
    
    # Check if player has already rolled dice (can't pass if need to roll first)
    if game_session.game.can_roll_dice:
        emit('error', {'message': 'You must roll the wild dice first'})
        return
    
    print(f"[PASS_TURN] {player_name} is passing their turn")
    
    # Advance to next player
    game_session.game.next_player()
    new_player = game_session.game.get_current_player()
    
    # Initialize turn tracking for new player
    if not hasattr(game_session.game, 'turn_cards_played'):
        game_session.game.turn_cards_played = {}
    game_session.game.turn_cards_played[new_player] = 0
    game_session.game.can_roll_dice = False
    
    print(f"[PASS_TURN] Turn advanced to {new_player}")
    
    # Broadcast updated game state
    emit('game_updated', game_session.get_game_state(), room=game_id)
    
    # Check for winner
    winner_result = game_session.check_winner()
    if winner_result:
        emit('game_over', {
            'winner': winner_result['winner'],
            'condition': winner_result['mode']
        }, room=game_id)
        return
    
    # Execute AI turn if next player is AI
    if game_session.players[game_session.sid_map[new_player]]['is_ai']:
        import threading
        thread = threading.Thread(target=game_session.execute_ai_move)
        thread.daemon = True
        thread.start()

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
