"""
Game Server for Twenty Dots
Manages game state and coordinates multiple networked players
"""
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import json
import os
import secrets
import time
from threading import RLock
from functools import wraps
from importlib import import_module
from twenty_dots import TwentyDots, Card, Dot
from ai_player import AIPlayer
from room_store import open_store

app = Flask(__name__)
app.config['SECRET_KEY'] = 'twentydots_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Active games dictionary: game_id -> game_data
games = {}
room_store = open_store()

ONLINE_POWERS = ('paint', 'shift', 'swap')


def make_round_lock():
    """Reentrant ownership must follow the Socket.IO worker, not just its OS thread."""
    # These optional modules are available only when Socket.IO selected that backend.
    module = {'eventlet': 'eventlet.green.threading', 'gevent': 'gevent.lock',
              'gevent_uwsgi': 'gevent.lock'}.get(socketio.async_mode)
    return import_module(module).RLock() if module else RLock()


def serialized_event(handler):
    """Serialize gameplay against rematches, including legacy packets queued at the lock."""
    @wraps(handler)
    def locked(data):
        if not isinstance(data, dict) or not isinstance(data.get('game_id'), str):
            emit('error', {'message': 'Expected game_id'})
            return
        session = games.get(data['game_id'])
        if session is None:
            emit('error', {'message': 'Game not found'})
            return
        received_round = session.round_id
        with session.round_lock:
            if received_round != session.round_id:
                emit('error', {'message': 'Stale round_id'})
                return
            return handler(data)
    return locked


def persist(game_id):
    """Save one room's latest state (or forget it once it is gone); never interrupts play."""
    session = games.get(game_id)
    try:
        if session is None:
            room_store.delete(game_id)
            return
        with session.round_lock:
            snapshot = json.dumps(session.snapshot())
        room_store.save(game_id, snapshot)
    except Exception as exc:
        print(f'[ROOM_STORE] Could not save {game_id}: {exc!r}')


def persisted(handler):
    """After a socket event, save every room it could have touched."""
    @wraps(handler)
    def saving(*args):
        before = set(games)
        try:
            return handler(*args)
        finally:
            data = args[0] if args and isinstance(args[0], dict) else {}
            touched = before ^ set(games)
            if isinstance(data.get('game_id'), str):
                touched.add(data['game_id'])
            touched.update(game_id for game_id, session in list(games.items())
                           if request.sid in session.players)
            for game_id in touched:
                persist(game_id)
    return saving


def restore_rooms():
    """Reload saved rooms at startup and resume any computer opponent mid-turn."""
    for game_id, data in room_store.load_all().items():
        try:
            games[game_id] = GameSession.restore(data)
        except Exception as exc:
            print(f'[ROOM_STORE] Skipping unreadable room {game_id}: {exc!r}')
            room_store.delete(game_id)
    for session in games.values():
        session.schedule_ai()
    print(f'[ROOM_STORE] Restored {len(games)} room(s) from {room_store.name}')


class GameSession:
    def __init__(self, game_id, host_sid, game_mode='twenty_dots', player_count=2, power_cards=False):
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
        self.winner = None
        self.round_id = 1
        self.series_number = 1
        self.series_round = 1
        self.series_wins = {}
        self.series_winner = None
        self.awarded_round = None
        self.ready_players = set()  # Human readiness only; AI seats are always ready.
        self.next_game_mode = game_mode
        self.power_cards = power_cards
        self.next_power_cards = power_cards
        self.recycle_pool = []  # Actual played Card objects, never public discard metadata.
        self.deck_reshuffles = 0
        self.last_move = None
        self.move_id = 0
        self.reaction_times = {}
        self.round_lock = make_round_lock()
        
    def add_player(self, sid, player_name, is_ai=False, token_enabled=False):
        """Add a player to the game"""
        if sid in self.players:
            return False, 'Already in this game'
        if len(self.players) >= self.required_players:
            print(f"[ADD_PLAYER] REJECTED: Game is full. Current: {len(self.players)}, Required: {self.required_players}")
            return False, f"Game is full ({self.required_players} players required)"
        
        print(f"[ADD_PLAYER] Adding {player_name} to game {self.game_id}. Current players: {len(self.players)}, Required: {self.required_players}")
        if player_name in self.player_order:
            return False, f"Player name '{player_name}' already taken"
            
        self.players[sid] = {
            'name': player_name,
            'is_ai': is_ai,
            'connected': True,
            'resume_token': secrets.token_urlsafe(32) if token_enabled and not is_ai else None
        }
        self.player_order.append(player_name)
        self.series_wins[player_name] = 0
        
        if is_ai:
            self.ai_players[player_name] = AIPlayer('medium')  # Will be updated later if needed
        
        return True, "Player added"
    
    def remove_player(self, sid):
        """Remove a player from the game"""
        if sid in self.players:
            player_name = self.players[sid]['name']
            self.player_order.remove(player_name)
            self.series_wins.pop(player_name, None)
            self.ready_players.discard(player_name)
            if player_name in self.ai_players:
                del self.ai_players[player_name]
            del self.players[sid]
    
    def snapshot(self):
        """JSON-safe copy of everything needed to resume this room after a restart."""
        def card(c):
            return {'location': c.location, 'color': c.color, 'power': c.power}
        game = self.game
        return {
            'version': 1,
            'game_id': self.game_id, 'game_mode': self.game_mode,
            'required_players': self.required_players, 'host_sid': self.host_sid,
            'players': self.players, 'player_order': self.player_order,
            'ai_players': {name: ai.difficulty for name, ai in self.ai_players.items()},
            'started': self.started, 'discard_piles': self.discard_piles,
            'winner': self.winner, 'round_id': self.round_id,
            'series_number': self.series_number, 'series_round': self.series_round,
            'series_wins': self.series_wins, 'series_winner': self.series_winner,
            'awarded_round': self.awarded_round,
            'next_game_mode': self.next_game_mode, 'power_cards': self.power_cards,
            'next_power_cards': self.next_power_cards,
            'recycle_pool': [card(c) for c in self.recycle_pool],
            'deck_reshuffles': self.deck_reshuffles, 'last_move': self.last_move,
            'move_id': self.move_id,
            'game': {
                'num_players': game.num_players,
                'grid': [[dot.color if dot else None for dot in row] for row in game.grid],
                'deck': [card(c) for c in game.deck],
                'players': {name: {**p, 'hand': [card(c) for c in p['hand']]}
                            for name, p in game.players.items()},
                'current_player_idx': game.current_player_idx,
                'yellow_dot_position': game.yellow_dot_position,
                'landmines': game.landmines,
                'can_roll_dice': getattr(game, 'can_roll_dice', False),
                'turn_cards_played': getattr(game, 'turn_cards_played', {}),
                'must_advance_after_roll': getattr(game, 'must_advance_after_roll', {}),
            },
        }

    @classmethod
    def restore(cls, data):
        """Rebuild a room from snapshot(); every human seat waits for its owner to rejoin."""
        def card(c):
            return Card(c['location'], c['color'], c['power'])
        session = cls(data['game_id'], data['host_sid'], data['game_mode'],
                      data['required_players'], data['power_cards'])
        session.players = data['players']
        for player in session.players.values():
            player['connected'] = player['is_ai']
        session.player_order = data['player_order']
        session.ai_players = {name: AIPlayer(difficulty)
                              for name, difficulty in data['ai_players'].items()}
        for key in ('started', 'discard_piles', 'winner', 'round_id', 'series_number',
                    'series_round', 'series_wins', 'series_winner', 'awarded_round',
                    'next_game_mode', 'next_power_cards', 'deck_reshuffles',
                    'last_move', 'move_id'):
            setattr(session, key, data[key])
        session.recycle_pool = [card(c) for c in data['recycle_pool']]

        saved = data['game']
        game = TwentyDots(num_players=saved['num_players'], difficulty='easy',
                          ai_opponents={}, power_cards=False)
        game.grid = [[Dot(color) if color else None for color in row] for row in saved['grid']]
        game.deck = [card(c) for c in saved['deck']]
        game.players = {name: {**p, 'hand': [card(c) for c in p['hand']]}
                        for name, p in saved['players'].items()}
        game.current_player_idx = saved['current_player_idx']
        position = saved['yellow_dot_position']
        game.yellow_dot_position = tuple(position) if position else None
        game.landmines = saved['landmines']
        game.can_roll_dice = saved['can_roll_dice']
        game.turn_cards_played = saved['turn_cards_played']
        game.must_advance_after_roll = saved['must_advance_after_roll']
        session.game = game
        return session

    def get_player_name(self, sid):
        """Get player name from session ID"""
        player = self.players.get(sid, {})
        return player.get('name') if player.get('connected') else None

    def get_lobby_state(self):
        """Public lobby data: never expose seat credentials."""
        round_state = self.get_round_state()
        by_name = {p['name']: (sid, p) for sid, p in self.players.items()}
        return {
            **round_state,
            'game_id': self.game_id,
            'players': [
                {'name': name, 'connected': by_name[name][1]['connected'],
                 'is_host': by_name[name][0] == self.host_sid}
                for name in self.player_order
            ],
            'required_players': self.required_players,
            'game_mode': self.game_mode,
            'started': self.started,
        }

    def broadcast_lobby(self):
        socketio.emit('lobby_updated', self.get_lobby_state(), room=self.game_id)

    def send_join_success(self, sid):
        player = self.players[sid]
        socketio.emit('join_success', {
            **self.get_lobby_state(), 'player_name': player['name'],
            'resume_token': player.get('resume_token'),
        }, room=sid)

    def initialize_game(self, power_cards=None):
        """Initialize every route identically, without overlapping-name pop collisions."""
        if power_cards is not None:
            self.power_cards = power_cards
        self.next_power_cards = self.power_cards
        self.winner = None
        self.ready_players.clear()
        self.recycle_pool = []
        self.deck_reshuffles = 0
        self.last_move = None
        self.game = TwentyDots(num_players=len(self.player_order), difficulty='easy',
                               ai_opponents={}, power_cards=False)
        if self.power_cards:
            self.game.deck.extend(Card('PWR', color, power)
                                  for color in self.game.colors for power in ONLINE_POWERS)
        self.game.players = dict(zip(self.player_order, self.game.players.values()))
        for name, player in self.game.players.items():
            player['is_ai'] = name in self.ai_players
        self.game.shuffle_deck()
        self.game.deal_cards(5)
        self.game.turn_cards_played = dict.fromkeys(self.player_order, 0)
        self.game.must_advance_after_roll = {}
        self.game.current_player_idx = (self.round_id - 1) % len(self.player_order)
        self.discard_piles = {name: [] for name in self.player_order}
        self.game.can_roll_dice = True
        self.started = True

    def start_if_ready(self):
        """Only auto-start when every reserved seat is present at the table."""
        if (not self.started and len(self.player_order) == self.required_players
                and all(player['connected'] for player in self.players.values())):
            self.initialize_game()
            return True
        return False

    def send_started_game(self, sid=None):
        """Send the board publicly or to one returning player; hands stay private."""
        socketio.emit('game_started', self.get_game_state(), room=sid or self.game_id)
        for player_sid, player in self.players.items():
            if (not player['is_ai'] and player['connected']
                    and (sid is None or sid == player_sid)):
                socketio.emit('your_hand', {
                    'hand': self.get_player_hand(player['name']),
                }, room=player_sid)

    def advance_turn(self):
        self.game.next_player()
        new_player = self.game.get_current_player()
        self.game.turn_cards_played[new_player] = 0
        self.game.must_advance_after_roll[new_player] = False
        # A hand may have emptied while every remaining card was held elsewhere.
        if not self.game.players[new_player]['hand'] and self.refill_hand(new_player):
            for sid, player in self.players.items():
                if player['name'] == new_player and player['connected'] and not player['is_ai']:
                    socketio.emit('your_hand', {'hand': self.get_player_hand(new_player)}, room=sid)

    def action_allowed(self, sid, data=None):
        if data is not None and 'round_id' in data and not self.valid_round(data):
            return False
        if not self.started:
            emit('error', {'message': 'Game has not started'})
            return False
        if self.check_winner():
            emit('error', {'message': 'Game is over'})
            emit('game_over', self.winner_payload())
            return False
        if not self.get_player_name(sid):
            emit('error', {'message': 'You are not in this game'})
            return False
        return True

    def valid_round(self, data):
        if type(data.get('round_id')) is not int or data['round_id'] != self.round_id:
            emit('error', {'message': 'Stale or missing round_id'})
            return False
        return True

    def get_round_state(self):
        # Latch and award BEFORE constructing the series, including the first terminal snapshot.
        with self.round_lock:
            self.check_winner()
            return {
                'round_id': self.round_id,
                'power_cards': self.power_cards,
                'series': {'number': self.series_number, 'round': self.series_round,
                           'wins': dict(self.series_wins), 'target_wins': 2,
                           'winner': self.series_winner},
                'rematch': {'ready': [name for name in self.player_order
                                      if name in self.ai_players or name in self.ready_players],
                            'next_game_mode': self.next_game_mode,
                            'next_power_cards': self.next_power_cards},
            }

    def broadcast_rematch(self):
        socketio.emit('rematch_updated', {
            'game_id': self.game_id, **self.get_round_state(),
        }, room=self.game_id)

    def start_rematch_if_ready(self):
        """Called under round_lock so simultaneous ready requests cannot start twice."""
        humans = [p for p in self.players.values() if not p['is_ai']]
        if not self.check_winner() or not all(
                p['connected'] and p['name'] in self.ready_players for p in humans):
            return False
        if self.series_winner:
            self.series_number += 1
            self.series_round = 1
            self.series_wins = dict.fromkeys(self.player_order, 0)
            self.series_winner = None
        else:
            self.series_round += 1
        self.round_id += 1
        self.game_mode = self.next_game_mode
        self.initialize_game(power_cards=self.next_power_cards)
        self.broadcast_lobby()
        self.send_started_game()
        self.schedule_ai()
        return True

    def refill_hand(self, player_name):
        """Recycle only played objects, only on depletion, without touching the board."""
        hand = self.game.players[player_name]['hand']
        drawn = 0
        while len(hand) < 5:
            if not self.game.deck:
                if not self.recycle_pool:
                    break
                self.game.deck, self.recycle_pool = self.recycle_pool, []
                self.game.shuffle_deck()
                self.deck_reshuffles += 1
            self.game.draw_card(player_name)
            drawn += 1
        return drawn

    def begin_move(self, player_name, kind):
        self.move_id += 1
        return {'id': self.move_id, 'player': player_name, 'kind': kind,
                'placements': [], 'collected': [],
                'points': -self.game.players[player_name]['total_dots'], 'lines': 0}

    def finish_move(self, move):
        # Points are the actual total_dots delta, not an estimate from removed dots.
        move['points'] += self.game.players[move['player']]['total_dots']
        self.last_move = move

    def collect_match(self, player_name, row, col, match, match_color, move, seen_lines=None):
        """Snapshot actual dot colors before removal; count completed axes, not triples."""
        positions = set(match)
        x, y = self.game.columns.index(col), self.game.rows.index(row)
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            line = {(x, y)}
            for sign in (-1, 1):
                step = 1
                while (x + sign * step * dx, y + sign * step * dy) in positions:
                    line.add((x + sign * step * dx, y + sign * step * dy))
                    step += 1
            if len(line) >= 3:
                key = frozenset(line)
                if seen_lines is None or key not in seen_lines:
                    move['lines'] += 1
                if seen_lines is not None:
                    seen_lines.add(key)
        for col_idx, row_idx in match:
            dot = self.game.grid[row_idx][col_idx]
            if dot:
                move['collected'].append({
                    'location': self.game.rows[row_idx] + self.game.columns[col_idx],
                    'color': dot.color,
                })
        self.game.collect_dots(match, player_name, match_color)

    def apply_cards(self, player_name, cards):
        """Shared human/AI placement, recycling, scoring and last-move recording."""
        if any(card.power is not None or card.location == 'PWR' for card in cards):
            raise ValueError('Power cards require play_power')
        hand = self.game.players[player_name]['hand']
        player = self.game.players[player_name]
        move = self.begin_move(player_name, 'play')
        yellow_replaced = yellow_collected = False
        for card in cards:
            if card not in hand:
                continue
            hand.remove(card)
            self.recycle_pool.append(card)
            info = {'location': ''.join(card.location), 'color': card.color}
            self.discard_piles.setdefault(player_name, []).append(info)
            self.game.turn_cards_played[player_name] += 1
            success, replaced_color = self.game.place_card_dot(card)
            if not success:
                continue
            move['placements'].append(info)
            if replaced_color == 'yellow':
                yellow_replaced = True
                player['yellow_dots'] += 1
                player['total_dots'] += 1
            elif replaced_color in self.game.colors:
                player['score'][replaced_color] += 1
                player['total_dots'] += 1
            if replaced_color:
                move['collected'].append({'location': info['location'], 'color': replaced_color})
            row, col = card.location
            match, match_color = self.game.check_line_match(row, col, card.color)
            if match:
                yellow_collected |= any(self.game.grid[y][x].color == 'yellow' for x, y in match)
                self.collect_match(player_name, row, col, match, match_color, move)
        self.finish_move(move)
        return yellow_replaced, yellow_collected

    def resolve_power(self, player_name, card_data, targets):
        """Validate completely before mutation; callers hold round_lock."""
        if (not self.started or self.winner or not self.power_cards
                or player_name != self.game.get_current_player()):
            raise ValueError('Power Play is unavailable or not your turn')
        if self.game.can_roll_dice:
            raise ValueError('You must roll the wild dice first')
        if self.game.turn_cards_played.get(player_name, 0) != 0:
            raise ValueError('A power costs your entire turn; play it before regular cards')
        if (not isinstance(card_data, dict) or card_data.get('location') != 'PWR'
                or card_data.get('power') not in ONLINE_POWERS
                or card_data.get('color') not in self.game.colors):
            raise ValueError('Invalid power card')
        card = next((c for c in self.game.players[player_name]['hand']
                     if c.location == 'PWR' and c.color == card_data['color']
                     and c.power == card_data['power']), None)
        if card is None:
            raise ValueError('Power card is not in your hand')
        count = {'paint': 1, 'shift': 2, 'swap': 2}[card.power]
        if not isinstance(targets, list) or len(targets) != count:
            raise ValueError('Invalid power targets')
        for target in targets:
            if (not isinstance(target, str) or len(target) != 2
                    or target[0] not in self.game.rows or target[1] not in self.game.columns):
                raise ValueError('Invalid power target coordinate')
        if len(set(targets)) != len(targets):
            raise ValueError('Power targets must be distinct')
        cells = [(self.game.rows.index(t[0]), self.game.columns.index(t[1])) for t in targets]
        if card.power == 'swap':
            if any(self.game.grid[row][col] is None
                   or self.game.grid[row][col].color not in self.game.colors
                   for row, col in cells):
                raise ValueError('Swap requires two regular colored dots; wild dots cannot swap')
        else:
            row, col = cells[-1]
            if self.game.grid[row][col] is not None:
                raise ValueError('Power destination must be empty')
        if card.power == 'shift':
            row, col = cells[0]
            dot = self.game.grid[row][col]
            if dot is None or dot.color not in self.game.colors:
                raise ValueError('Shift source must contain a regular colored dot')
            if dot.color != card.color:
                raise ValueError(f'Shift requires a {card.color} dot matching the card color')
            dest_row, dest_col = cells[1]
            if abs(dest_row - row) + abs(dest_col - col) != 1:
                raise ValueError('Shift destination must be an empty neighboring square '
                                 'up, down, left, or right (not diagonal)')
        return card, cells

    def apply_power(self, player_name, card_data, targets):
        """Shared human/AI execution; validation precedes every state change."""
        card, cells = self.resolve_power(player_name, card_data, targets)
        hand = self.game.players[player_name]['hand']
        move = self.begin_move(player_name, 'power')
        move['power'] = card.power
        hand.remove(card)
        self.recycle_pool.append(card)
        self.discard_piles.setdefault(player_name, []).append(
            {'location': 'PWR', 'color': card.color, 'power': card.power})
        self.game.turn_cards_played[player_name] = 2
        yellow_collected = False
        if card.power == 'swap':
            (row_a, col_a), (row_b, col_b) = cells
            self.game.grid[row_a][col_a], self.game.grid[row_b][col_b] = (
                self.game.grid[row_b][col_b], self.game.grid[row_a][col_a])
            # Find BOTH endpoints' matches on the swapped board before collecting.
            # They may share a wild dot or even the same line (same-color swaps).
            matches = []
            for target, (row, col) in zip(targets, cells):
                dot = self.game.grid[row][col]
                move['placements'].append({'location': target, 'color': dot.color})
                match, color = self.game.check_line_match(target[0], target[1], dot.color)
                if match:
                    yellow_collected |= any(self.game.grid[y][x].color == 'yellow' for x, y in match)
                    matches.append((target, match, color))
            seen_lines = set()
            for target, match, color in matches:
                # collect_dots and collect_match skip dots already collected.
                self.collect_match(player_name, target[0], target[1], match, color, move, seen_lines)
        else:
            dot = Dot(card.color)
            if card.power == 'shift':
                row, col = cells[0]
                dot = self.game.grid[row][col]
                self.game.grid[row][col] = None
                move['removed'] = [targets[0]]
            row_idx, col_idx = cells[-1]
            self.game.grid[row_idx][col_idx] = dot
            move['placements'].append({'location': targets[-1], 'color': dot.color})
            row, col = targets[-1]
            match, color = self.game.check_line_match(row, col, dot.color)
            if match:
                yellow_collected = any(self.game.grid[y][x].color == 'yellow' for x, y in match)
                self.collect_match(player_name, row, col, match, color, move)
        if yellow_collected:
            self.game.yellow_dot_position = None
        self.finish_move(move)
        self.refill_hand(player_name)
        if self.check_winner():
            self.game.can_roll_dice = False
            self.game.must_advance_after_roll[player_name] = False
        elif yellow_collected:
            self.game.can_roll_dice = True
            self.game.must_advance_after_roll[player_name] = True
        else:
            self.advance_turn()

    def ai_power_options(self, player_name):
        """Every legal (card, targets) power play, validated exactly like human plays."""
        empty = [r + c for y, r in enumerate(self.game.rows)
                 for x, c in enumerate(self.game.columns) if self.game.grid[y][x] is None]
        sources = [r + c for y, r in enumerate(self.game.rows)
                   for x, c in enumerate(self.game.columns)
                   if self.game.grid[y][x] is not None
                   and self.game.grid[y][x].color in self.game.colors]
        color_at = {r + c: self.game.grid[y][x].color for y, r in enumerate(self.game.rows)
                    for x, c in enumerate(self.game.columns) if r + c in sources}
        options, seen = [], set()
        for card in self.get_player_hand(player_name):
            power = card['power']
            if power is None or (power, card['color']) in seen:
                continue
            seen.add((power, card['color']))
            if power == 'swap':
                # Swapping two dots of one color changes nothing.
                candidates = [[a, b] for i, a in enumerate(sources) for b in sources[i + 1:]
                              if color_at[a] != color_at[b]]
            elif power == 'paint':
                candidates = [[cell] for cell in empty]
            else:
                candidates = [[source, destination] for source in sources for destination in empty]
            for targets in candidates:
                try:
                    _, cells = self.resolve_power(player_name, card, targets)
                except ValueError:
                    continue
                options.append((card, targets, cells))
        return options

    def ai_context(self, player_name, power_options=None):
        """What a seated player can see: the board, every score, and their own hand."""
        hand = self.game.players[player_name]['hand']
        return {
            'board': [[dot.color if dot else None for dot in row] for row in self.game.grid],
            'me': player_name,
            'order': list(self.player_order),
            'mode': self.game_mode,
            'players': {name: {'score': dict(p['score']), 'total_dots': p['total_dots'],
                               'yellow_dots': p.get('yellow_dots', 0)}
                        for name, p in self.game.players.items()},
            'cards_left': 2 - self.game.turn_cards_played.get(player_name, 0),
            'regular_hand': [c for c in hand if c.power is None and c.location != 'PWR'],
            'power_options': [(card, card['power'], card['color'], cells)
                              for card, _, cells in power_options or []],
        }

    def choose_ai_power(self, player_name):
        """The seat's AI picks among all legal powers; humans' seats get the first legal one."""
        options = self.ai_power_options(player_name)
        if not options:
            return None
        ai = self.ai_players.get(player_name)
        context = self.ai_context(player_name, options)
        index = ai.choose_power(context['power_options'], context) if ai else 0
        card, targets, _ = options[index]
        return card, targets

    def broadcast_action(self):
        """Public board/recycling notice and one private hand per connected human."""
        socketio.emit('game_updated', self.get_game_state(), room=self.game_id)
        if self.check_winner():
            socketio.emit('game_over', self.winner_payload(), room=self.game_id)
        for sid, player in self.players.items():
            if player['connected'] and not player['is_ai']:
                socketio.emit('your_hand', {'hand': self.get_player_hand(player['name'])}, room=sid)

    def winner_payload(self):
        result = self.check_winner()
        return {'winner': result['winner'], 'condition': result['mode']} if result else None

    def schedule_ai(self):
        if (self.started and not self.check_winner()
                and self.game.get_current_player() in self.ai_players):
            socketio.start_background_task(self.execute_ai_move)
    
    def get_game_state(self):
        """Get current game state for broadcasting"""
        round_state = self.get_round_state()
        connected = {p['name']: p['connected'] for p in self.players.values()}
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
            **round_state,
            'game_id': self.game_id,
            'board': board_data,
            'players': {name: {
                'score': data['score'],
                'total_dots': data['total_dots'],
                'yellow_dots': data.get('yellow_dots', 0),
                'hand_size': len(data['hand']),
                'connected': connected.get(name, False),
                'discard_pile': self.discard_piles.get(name, [])
            } for name, data in self.game.players.items()},
            'current_turn': self.game.get_current_player(),
            'turn_number': getattr(self.game, 'turn_number', 1),
            'deck_size': len(self.game.deck),
            'deck_reshuffles': self.deck_reshuffles,
            'last_move': self.last_move,
            'yellow_dot_position': yellow_position,
            'landmines': landmines_data,
            'can_roll_dice': getattr(self.game, 'can_roll_dice', False),
            'game_mode': self.game_mode,
            'required_players': self.required_players,
            'cards_played_this_turn': getattr(self.game, 'turn_cards_played', {}).get(
                self.game.get_current_player(), 0),
            'winner': self.winner_payload(),
        }
    
    def get_player_hand(self, player_name):
        """Get specific player's hand"""
        hand = self.game.players[player_name]['hand']
        cards_data = []
        for c in hand:
            if c.power is not None:
                if c.location == 'PWR' and c.power in ONLINE_POWERS:
                    cards_data.append({'location': 'PWR', 'color': c.color, 'power': c.power})
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
    
    def roll_wild(self, player_name):
        """Roll the wild dice, place yellow, and collect any match it completes. Returns the match."""
        from twenty_dots import Dot
        move = self.begin_move(player_name, 'roll')
        row, col = self.game.roll_dice()
        row_idx = self.game.rows.index(row)
        col_idx = self.game.columns.index(col)
        old_dot = self.game.grid[row_idx][col_idx]
        self.game.grid[row_idx][col_idx] = Dot('yellow')
        self.game.yellow_dot_position = (row_idx, col_idx)
        move['placements'].append({'location': row + col, 'color': 'yellow'})
        print(f"[ROLL_DICE] {player_name} rolled {row}{col} (replaced: {old_dot.color if old_dot else 'empty'})")

        match, match_color = self.game.check_line_match(row, col, 'yellow')
        if match:
            print(f"[ROLL_DICE] MATCH FOUND! Collecting {len(match)} positions for color {match_color}")
            self.collect_match(player_name, row, col, match, match_color, move)
            self.game.yellow_dot_position = None
        self.finish_move(move)
        return match

    def execute_ai_move(self):
        """Run one AI turn iteratively; never feed PWR locations to the desktop AI."""
        with self.round_lock:
            if not self.started or self.check_winner() or self.ai_move_in_progress:
                return
            name = self.game.get_current_player()
            if name not in self.ai_players:
                return
            self.ai_move_in_progress = True
            try:
                # Bound repeated matching rolls; continuation uses scheduling, not recursion.
                for _ in range(64):
                    if self.check_winner() or self.game.get_current_player() != name:
                        break
                    used = self.game.turn_cards_played.get(name, 0)
                    if self.game.can_roll_dice:
                        match = self.roll_wild(name)
                        self.game.can_roll_dice = bool(match)
                        if not self.check_winner() and not match and (
                                used >= 2 or self.game.must_advance_after_roll.get(name, False)):
                            self.refill_hand(name)
                            self.advance_turn()
                        self.broadcast_action()
                        continue
                    if used >= 2:
                        self.refill_hand(name)
                        self.advance_turn()
                        self.broadcast_action()
                        break
                    hand = self.game.players[name]['hand']
                    if not hand:
                        self.refill_hand(name)
                    regular = [c for c in hand if c.power is None and c.location != 'PWR']
                    powers = self.ai_power_options(name) if used == 0 and self.power_cards else []
                    indices = (self.ai_players[name].choose_cards(
                        regular, self.ai_context(name, powers)) if regular else [])
                    selected = []
                    locations = set()
                    for index in indices:
                        if type(index) is not int or not 0 <= index < len(regular):
                            continue
                        card = regular[index]
                        location = ''.join(card.location)
                        if location not in locations:
                            selected.append(card)
                            locations.add(location)
                        if len(selected) == 2 - used:
                            break
                    if not selected:
                        power = self.choose_ai_power(name) if used == 0 else None
                        if power:
                            self.apply_power(name, *power)
                        else:
                            self.refill_hand(name)
                            self.advance_turn()
                        self.broadcast_action()
                        continue
                    replaced, collected = self.apply_cards(name, selected)
                    if replaced or collected:
                        self.game.yellow_dot_position = None
                        self.game.can_roll_dice = True
                    if self.game.turn_cards_played[name] >= 2 and not self.check_winner():
                        self.refill_hand(name)
                        if self.game.can_roll_dice:
                            self.game.must_advance_after_roll[name] = True
                        else:
                            self.advance_turn()
                    self.broadcast_action()
            finally:
                self.ai_move_in_progress = False
        persist(self.game_id)
        self.schedule_ai()
    
    def check_winner(self):
        """Latch the round result and award its series point exactly once."""
        with self.round_lock:
            result = self._find_winner()
            if result and self.awarded_round != self.round_id:
                name = result['winner']
                self.series_wins[name] += 1
                self.awarded_round = self.round_id
                if self.series_wins[name] >= 2:
                    self.series_winner = name
            return result

    def _find_winner(self):
        """Check if anyone has won based on game_mode"""
        if self.winner:
            return self.winner
        if not self.started:
            return None
        
        # Don't end game just because deck is empty - players can still play their hand cards
        # Only check for winner based on actual win conditions
        
        for player_name in self.player_order:
            player_data = self.game.players[player_name]
            
            if self.game_mode == 'twenty_dots':
                total = player_data['total_dots']
                print(f"[CHECK_WINNER] {player_name} has {total} total dots")
                if total >= 20:
                    print(f"[CHECK_WINNER] {player_name} WINS with {total} dots!")
                    self.winner = {'winner': player_name, 'mode': 'twenty_dots'}
                    return self.winner
            
            elif self.game_mode == 'five_colors':
                # Check if player has 5 of each color (red, blue, green, purple)
                if all(player_data['score'].get(color, 0) >= 5 for color in ['red', 'blue', 'green', 'purple']):
                    print(f"[CHECK_WINNER] {player_name} WINS with 5 of each color!")
                    self.winner = {'winner': player_name, 'mode': 'five_colors'}
                    return self.winner
            
            elif self.game_mode == 'five_with_yellow':
                # Check if player has 5 yellow dots AND 5 of each color
                yellow_dots = player_data.get('yellow_dots', 0)
                if yellow_dots >= 5 and all(player_data['score'].get(color, 0) >= 5 for color in ['red', 'blue', 'green', 'purple']):
                    print(f"[CHECK_WINNER] {player_name} WINS with 5 yellow and 5 of each color!")
                    self.winner = {'winner': player_name, 'mode': 'five_with_yellow'}
                    return self.winner
        
        print(f"[CHECK_WINNER] No winner yet (mode: {self.game_mode})")
        return None

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'sid': request.sid})

@socketio.on('disconnect')
@persisted
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # Find and update player's connection status
    for game_id, game_session in games.items():
        if request.sid in game_session.players:
            with game_session.round_lock:
                name = game_session.players[request.sid]['name']
                game_session.players[request.sid]['connected'] = False
                game_session.ready_players.discard(name)
                emit('player_disconnected', {'player': name}, room=game_id)
                game_session.broadcast_lobby()
                game_session.broadcast_rematch()


def event_session(data):
    """Validate the new event envelope and authorize a connected human seat."""
    if not isinstance(data, dict) or not isinstance(data.get('game_id'), str):
        emit('error', {'message': 'Expected game_id'})
        return None
    session = games.get(data['game_id'])
    if (session is None or not session.get_player_name(request.sid)
            or session.players[request.sid]['is_ai']):
        emit('error', {'message': 'You are not in this game'})
        return None
    return session


def rematch_allowed(session, data):
    # Recheck after acquiring round_lock: a disconnect may have won the race.
    if not session.get_player_name(request.sid):
        emit('error', {'message': 'You are not in this game'})
        return False
    if not session.valid_round(data):
        return False
    if not session.started or not session.check_winner():
        emit('error', {'message': 'Rematch is only available after a winner'})
        return False
    return True


@socketio.on('rematch_ready')
@persisted
def handle_rematch_ready(data):
    session = event_session(data)
    if session is None:
        return
    with session.round_lock:
        if not rematch_allowed(session, data):
            return
        if type(data.get('ready')) is not bool:
            emit('error', {'message': 'ready must be a boolean'})
            return
        name = session.get_player_name(request.sid)
        if data['ready']:
            session.ready_players.add(name)
        else:
            session.ready_players.discard(name)
        session.broadcast_rematch()
        session.start_rematch_if_ready()


@socketio.on('rematch_options')
@persisted
def handle_rematch_options(data):
    session = event_session(data)
    if session is None:
        return
    with session.round_lock:
        if not rematch_allowed(session, data):
            return
        if request.sid != session.host_sid:
            emit('error', {'message': 'Only host can change rematch options'})
            return
        mode = data.get('game_mode', session.next_game_mode)
        if mode not in ('twenty_dots', 'five_colors', 'five_with_yellow'):
            emit('error', {'message': 'Invalid game_mode'})
            return
        powers = data.get('power_cards', session.next_power_cards)
        if type(powers) is not bool:
            emit('error', {'message': 'power_cards must be a boolean'})
            return
        if mode != session.next_game_mode or powers != session.next_power_cards:
            session.next_game_mode = mode
            session.next_power_cards = powers
            session.ready_players.clear()
        session.broadcast_rematch()


@socketio.on('reaction')
def handle_reaction(data):
    session = event_session(data)
    if session is None:
        return
    with session.round_lock:
        key = data.get('reaction')
        name = session.get_player_name(request.sid)
        if not name:
            emit('error', {'message': 'You are not in this game'})
            return
        if not session.started or key not in ('nice_move', 'well_played', 'close_one', 'rematch'):
            emit('error', {'message': 'Invalid reaction or game not started'})
            return
        now = time.monotonic()
        previous = session.reaction_times.get(name)
        if previous is not None and now - previous < 3:
            emit('error', {'message': 'Reaction cooldown: wait 3 seconds'})
            return
        session.reaction_times[name] = now
        emit('reaction', {'game_id': session.game_id, 'player': name, 'reaction': key},
             room=session.game_id)


def validate_join_data(data):
    """Validate room options before lookup or engine construction; retain integer strings."""
    if not isinstance(data, dict):
        raise ValueError('Expected an object')
    if type(data.get('power_cards', False)) is not bool:
        raise ValueError('power_cards must be a boolean')
    for field, limit in (('player_name', 24), ('game_id', 64)):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f'{field} must be nonempty and at most {limit} characters')
    count = data.get('player_count', 2)
    if isinstance(count, bool) or not isinstance(count, (str, int)):
        raise ValueError('player_count must be an integer from 2 to 4')
    try:
        count = int(count)
    except ValueError:
        raise ValueError('player_count must be an integer from 2 to 4') from None
    if not 2 <= count <= 4:
        raise ValueError('player_count must be an integer from 2 to 4')
    mode = data.get('game_mode', 'twenty_dots')
    if mode not in ('twenty_dots', 'five_colors', 'five_with_yellow'):
        raise ValueError('Invalid game_mode')
    if 'intent' in data and data['intent'] not in ('create', 'join', 'rejoin'):
        raise ValueError('Invalid intent')
    token = data.get('resume_token')
    if token is not None and (not isinstance(token, str) or len(token) > 256):
        raise ValueError('Invalid resume_token')
    return count, mode


@socketio.on('leave_game')
@persisted
def handle_leave_game(data):
    """Leave a lobby, or mark a started seat disconnected without deleting its game data."""
    game_id = data.get('game_id')
    session = games.get(game_id)
    if session is None or request.sid not in session.players:
        emit('error', {'message': 'You are not in this game'})
        return
    if session.started:
        with session.round_lock:
            name = session.players[request.sid]['name']
            session.players[request.sid]['connected'] = False
            session.ready_players.discard(name)
            emit('player_disconnected', {'player': name}, room=game_id)
            session.broadcast_rematch()
    else:
        session.remove_player(request.sid)
        if request.sid == session.host_sid:
            # Prefer a connected human, then a disconnected human, then any seat.
            session.host_sid = next((sid for sid, p in session.players.items()
                                     if p['connected'] and not p['is_ai']), None)
            if session.host_sid is None:
                session.host_sid = next((sid for sid, p in session.players.items()
                                         if not p['is_ai']), next(iter(session.players), None))
    session.broadcast_lobby()
    leave_room(game_id)
    if not session.players:
        del games[game_id]

@socketio.on('create_game')
@persisted
def handle_create_game(data):
    """Host creates a new game"""
    if not isinstance(data, dict):
        emit('error', {'message': 'Expected an object'})
        return
    game_id = data.get('game_id', f"game_{len(games)}")
    player_name = data.get('player_name', 'Player 1')
    try:
        player_count, game_mode = validate_join_data({**data, 'game_id': game_id, 'player_name': player_name})
    except ValueError as exc:
        emit('error', {'message': str(exc)})
        return
    
    if game_id in games:
        emit('error', {'message': 'Game ID already exists'})
        return
    
    game_session = GameSession(game_id, request.sid, game_mode, player_count,
                               power_cards=data.get('power_cards', False))
    success, message = game_session.add_player(
        request.sid, player_name, token_enabled='intent' in data or 'resume_token' in data)
    
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
    game_session.send_join_success(request.sid)
    game_session.broadcast_lobby()
    print(f"Game created: {game_id} by {player_name}")

@socketio.on('join_game')
@persisted
def handle_join_game(data):
    """Explicit create/join/rejoin, with auto-create retained for legacy clients.

    Explicit intent or the presence of resume_token opts new seats into tokens.
    Omitted intent and token keeps legacy disconnected-only name-based resume.
    """
    try:
        player_count, game_mode = validate_join_data(data)
    except ValueError as exc:
        emit('error', {'message': str(exc)})
        return
    game_id = data['game_id']
    player_name = data['player_name']
    intent = data.get('intent')
    game_session = games.get(game_id)
    if game_session is None and intent in ('join', 'rejoin'):
        emit('error', {'message': 'Game not found'})
        return
    if game_session is not None and intent == 'create':
        emit('error', {'message': 'Game ID already exists'})
        return
    if game_session is None:
        game_session = GameSession(game_id, request.sid, game_mode, player_count,
                                   power_cards=data.get('power_cards', False))

    existing_sid = next((sid for sid, p in game_session.players.items()
                         if p['name'] == player_name), None)
    if existing_sid is not None:
        player = game_session.players[existing_sid]
        if player['is_ai'] or (player['connected'] and existing_sid != request.sid):
            emit('error', {'message': 'Player name is already connected'})
            return
        if request.sid in game_session.players and request.sid != existing_sid:
            emit('error', {'message': 'Already in this game'})
            return
        token = player.get('resume_token')
        supplied_token = data.get('resume_token')
        if token and (not isinstance(supplied_token, str)
                      or not secrets.compare_digest(token.encode(), supplied_token.encode())):
            emit('error', {'message': 'Invalid resume token'})
            return
        del game_session.players[existing_sid]
        game_session.players[request.sid] = player
        player['connected'] = True
        if game_session.host_sid == existing_sid:
            game_session.host_sid = request.sid
        join_room(game_id)
        auto_start = game_session.start_if_ready()
        game_session.send_join_success(request.sid)
        game_session.broadcast_lobby()
        if game_session.started:
            game_session.send_started_game(None if auto_start else request.sid)
            if game_session.check_winner():
                emit('game_over', game_session.winner_payload())
        if auto_start:
            game_session.schedule_ai()
        return
    if intent == 'rejoin':
        emit('error', {'message': 'Player not found'})
        return
    if game_session.started:
        emit('error', {'message': 'Game already started - cannot add new players'})
        return
    success, message = game_session.add_player(
        request.sid, player_name, token_enabled='intent' in data or 'resume_token' in data)
    if not success:
        emit('error', {'message': message})
        return
    games[game_id] = game_session
    join_room(game_id)
    emit('player_joined', {
        'player_name': player_name,
        'players': game_session.player_order
    }, room=game_id)
    auto_start = game_session.start_if_ready()
    game_session.send_join_success(request.sid)
    game_session.broadcast_lobby()
    if auto_start:
        game_session.send_started_game()
        game_session.schedule_ai()

@socketio.on('add_ai_player')
@persisted
@serialized_event
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
    if game_session.started:
        emit('error', {'message': 'Game already started'})
        return
    if not isinstance(ai_name, str) or not ai_name.strip() or len(ai_name) > 24:
        emit('error', {'message': 'AI name must be nonempty and at most 24 characters'})
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
    game_session.broadcast_lobby()
    
    print(f"AI player {ai_name} added to game {game_id}")

@socketio.on('start_single_player')
@persisted
def handle_start_single_player(data):
    """Start a single-player game with AI opponents"""
    if not isinstance(data, dict):
        emit('error', {'message': 'Expected an object'})
        return
    player_name = data.get('player_name', 'Player')
    num_players = data.get('num_players', 2)
    difficulty = data.get('difficulty', 'medium')
    game_mode = data.get('game_mode', 'twenty_dots')
    
    # Validate before constructing a game or joining its room.
    try:
        num_players, game_mode = validate_join_data({
            **data, 'game_id': 'single-player', 'player_name': player_name,
            'player_count': num_players,
        })
    except ValueError as exc:
        emit('error', {'message': str(exc)})
        return
    
    # Create a unique game ID for single-player
    import uuid
    game_id = f"sp_{uuid.uuid4().hex[:8]}"
    
    # Create game session
    game_session = GameSession(game_id, request.sid, game_mode, num_players,
                               power_cards=data.get('power_cards', False))
    games[game_id] = game_session
    join_room(game_id)
    
    # Add human player
    success, message = game_session.add_player(
        request.sid, player_name, is_ai=False,
        token_enabled='intent' in data or 'resume_token' in data)
    if not success:
        emit('error', {'message': message})
        return
    
    # Add AI players
    ai_names = ['AI 1', 'AI 2', 'AI 3']
    for i in range(num_players - 1):
        ai_sid = f"ai_{game_id}_{i}"
        ai_name = ai_names[i] if i < len(ai_names) else f"AI {i+1}"
        while ai_name in game_session.player_order:
            ai_name += ' AI'
        success, msg = game_session.add_player(ai_sid, ai_name, is_ai=True)
        if success:
            game_session.ai_players[ai_name].difficulty = difficulty
    
    game_session.initialize_game()
    game_session.send_join_success(request.sid)
    game_session.broadcast_lobby()
    
    # Send game state
    game_state = game_session.get_game_state()
    emit('game_started', game_state, room=game_id)
    
    # Send player their hand privately
    hand = game_session.get_player_hand(player_name)
    emit('your_hand', {'hand': hand})
    
    print(f"Single-player game {game_id} started with {player_name} vs {num_players - 1} AI opponents")

@socketio.on('start_game')
@persisted
@serialized_event
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
    if game_session.started:
        emit('error', {'message': 'Game already started'})
        return
    
    if len(game_session.player_order) < 2:
        emit('error', {'message': 'Need at least 2 players to start'})
        return
    
    game_session.initialize_game()
    game_session.broadcast_lobby()
    
    # Send game state to all players
    game_state = game_session.get_game_state()
    emit('game_started', game_state, room=game_id)
    
    # Send each player their hand privately
    for sid, player_info in game_session.players.items():
        if not player_info['is_ai'] and player_info['connected']:
            hand = game_session.get_player_hand(player_info['name'])
            socketio.emit('your_hand', {'hand': hand}, room=sid)
    
    game_session.schedule_ai()
    print(f"Game {game_id} started with players: {game_session.player_order}")

@socketio.on('play_power')
@persisted
@serialized_event
def handle_play_power(data):
    session = event_session(data)
    if session is None or not session.valid_round(data):
        return
    if not session.action_allowed(request.sid, data):
        return
    try:
        session.apply_power(session.get_player_name(request.sid), data.get('card'), data.get('targets'))
    except ValueError as exc:
        emit('error', {'message': str(exc)})
        return
    session.broadcast_action()
    session.schedule_ai()


@socketio.on('play_cards')
@persisted
@serialized_event
def handle_play_cards(data):
    """Player plays one or more cards"""
    game_id = data.get('game_id')
    cards_data = data.get('cards')  # List of {color, location, power}
    
    print(f"[PLAY_CARDS] Received play_cards from player. Cards: {cards_data}")
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    if not game_session.action_allowed(request.sid, data):
        return
    player_name = game_session.get_player_name(request.sid)
    
    if not player_name:
        emit('error', {'message': 'You are not in this game'})
        return
    
    if game_session.game.get_current_player() != player_name:
        emit('error', {'message': 'Not your turn'})
        return
    if game_session.game.can_roll_dice:
        emit('error', {'message': 'You must roll the wild dice first'})
        return
    if not isinstance(cards_data, list) or not 1 <= len(cards_data) <= 2:
        emit('error', {'message': 'Select one or two cards'})
        return
    for card_data in cards_data:
        if not isinstance(card_data, dict):
            emit('error', {'message': 'Invalid cards selected'})
            return
        if card_data.get('power') is not None:
            emit('error', {'message': 'Power cards require play_power'})
            return
        location = card_data.get('location')
        if (not isinstance(location, (str, list, tuple)) or len(location) != 2
                or location[0] not in game_session.game.rows
                or location[1] not in game_session.game.columns
                or card_data.get('color') not in game_session.game.colors):
            emit('error', {'message': 'Invalid cards selected'})
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
            
            if card.power is None and card.color == card_data['color'] and card_loc == req_loc:
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
    
    # Counters reset only when the turn advances, never on a play request.
    if current_player not in game_session.game.turn_cards_played:
        game_session.game.turn_cards_played[current_player] = 0
    
    cards_played_this_turn = game_session.game.turn_cards_played[current_player]
    
    # Prevent playing more cards if already at 2 this turn
    total_played_this_turn = cards_played_this_turn + len(cards_to_play)
    if total_played_this_turn > 2:
        emit('error', {'message': f'Can only play 2 cards per turn. Already played {cards_played_this_turn}'})
        print(f"[PLAY_CARDS] ERROR: {current_player} tried to play {len(cards_to_play)} cards but already played {cards_played_this_turn} this turn")
        return
    
    yellow_replaced, yellow_collected = game_session.apply_cards(player_name, cards_to_play)
    
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
        cards_drawn = game_session.refill_hand(player_name)
        print(f"[PLAY_CARDS] Drew {cards_drawn} cards")
        
        # Only advance turn if yellow was NOT replaced or collected
        # If yellow was affected, current player must roll again
        if not (yellow_replaced or yellow_collected):
            print(f"[PLAY_CARDS] Auto-advancing turn (yellow not affected)")
            game_session.game.can_roll_dice = False
            game_session.advance_turn()
            new_player = game_session.game.get_current_player()
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
    
    game_session.schedule_ai()
    
    print(f"{player_name} played {len(cards_to_play)} card(s) in game {game_id}")


@socketio.on('end_turn')
@persisted
@serialized_event
def handle_end_turn(data):
    """Player ends their turn"""
    game_id = data.get('game_id')
    print(f"[END_TURN] Received end_turn request for game {game_id}")
    
    if game_id not in games:
        print(f"[END_TURN] ERROR: Game {game_id} not found")
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    if not game_session.action_allowed(request.sid, data):
        return
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
    if game_session.game.can_roll_dice:
        emit('error', {'message': 'You must roll the wild dice first'})
        return
    
    print(f"[END_TURN] Validations passed. Drawing cards...")
    # Draw cards to 5 before ending turn
    hand = game_session.game.players[player_name]['hand']
    cards_drawn = game_session.refill_hand(player_name)
    print(f"[END_TURN] Drew {cards_drawn} cards. Hand size now: {len(hand)}")
    
    print(f"[END_TURN] Current player index before: {game_session.game.current_player_idx}")
    # Move to next turn
    game_session.advance_turn()
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
    
    game_session.schedule_ai()
    
    print(f"[END_TURN] Turn ended successfully. Now: {game_session.game.get_current_player()}")


@socketio.on('roll_dice')
@persisted
@serialized_event
def handle_roll_dice(data):
    """Player rolls dice for yellow wild dot"""
    game_id = data.get('game_id')
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    if not game_session.action_allowed(request.sid, data):
        return
    player_name = game_session.get_player_name(request.sid)
    
    if not player_name:
        emit('error', {'message': 'You are not in this game'})
        return
    
    if game_session.game.get_current_player() != player_name:
        emit('error', {'message': 'Not your turn'})
        return
    if not game_session.game.can_roll_dice:
        emit('error', {'message': 'Wild dice roll is not required'})
        return
    
    # Check if this player needs to advance their turn after rolling
    if not hasattr(game_session.game, 'must_advance_after_roll'):
        game_session.game.must_advance_after_roll = {}
    
    # Track if this player must advance turn after rolling
    must_advance = player_name in game_session.game.must_advance_after_roll and game_session.game.must_advance_after_roll[player_name]
    if must_advance:
        print(f"[ROLL_DICE] {player_name} must advance turn after this roll")
    
    match = game_session.roll_wild(player_name)

    if match:
        # Can roll again if matched
        game_session.game.can_roll_dice = True
    else:
        # No match - if player must advance after roll, do it now
        if must_advance:
            print(f"[ROLL_DICE] Advancing {player_name}'s turn after rolling")
            game_session.game.must_advance_after_roll[player_name] = False
            game_session.advance_turn()
            game_session.game.can_roll_dice = False
        else:
            # Normal case - player can now play cards
            game_session.game.can_roll_dice = False
    
    print(f"[ROLL_DICE] {player_name} Match: {bool(match)}. can_roll_dice={game_session.game.can_roll_dice}")
    
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
    
    game_session.schedule_ai()
    print(f"{player_name} rolled dice")

@socketio.on('pass_turn')
@persisted
@serialized_event
def handle_pass_turn(data):
    """Player passes their turn without playing cards"""
    game_id = data.get('game_id')
    
    if game_id not in games:
        emit('error', {'message': 'Game not found'})
        return
    
    game_session = games[game_id]
    if not game_session.action_allowed(request.sid, data):
        return
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
    game_session.advance_turn()
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
    game_session.schedule_ai()

def execute_ai_turn(game_session, ai_name):
    """Legacy entry point delegates to the same power-aware online AI executor."""
    with game_session.round_lock:
        if game_session.game.get_current_player() == ai_name:
            game_session.execute_ai_move()

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
    restore_rooms()
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
