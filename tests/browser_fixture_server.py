"""Loopback-only browser fixture server. Never import this from production.

The test runner supplies an ephemeral secret. Fixtures arrange real cards and
boards, then browser clicks use the unmodified Socket.IO gameplay handlers.
"""
import os
from pathlib import Path
import secrets
import sys
from unittest.mock import patch

import flask_socketio
from flask import abort, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_socketio = flask_socketio.SocketIO
with patch('flask_socketio.SocketIO', side_effect=lambda *args, **kwargs: _socketio(
        *args, **dict(kwargs, async_mode='threading'))):
    import game_server as server

from twenty_dots import Dot


def prepare_position():
    """Arrange a double-line move; optionally approach a win or exhaust the deck."""
    key = os.environ.get('BROWSER_FIXTURE_KEY', '')
    if (not key or request.remote_addr != '127.0.0.1'
            or not secrets.compare_digest(request.headers.get('X-Fixture-Key', ''), key)):
        abort(403)
    data = request.get_json()
    session = server.games[data['game_id']]
    with session.round_lock:
        if session.check_winner():
            abort(409)
        if data.get('power'):
            return prepare_power(session, data)
        name = data['player']
        game = session.game
        player = game.players[name]
        # Swap existing physical cards, preserving the 144-card partition.
        card = next((c for c in player['hand'] if c.location[0] in 'BCDE'
                     and c.location[1] in '2345'), None)
        if card is None:
            source = next(pool for pool in (game.deck, session.recycle_pool)
                          if any(c.location[0] in 'BCDE' and c.location[1] in '2345'
                                 for c in pool))
            card = next(c for c in source if c.location[0] in 'BCDE'
                        and c.location[1] in '2345')
            source.remove(card)
            source.append(player['hand'].pop())
            player['hand'].append(card)
        row = game.rows.index(card.location[0])
        col = game.columns.index(card.location[1])
        game.grid = [[None for _ in range(6)] for _ in range(6)]
        game.grid[row][col] = Dot('yellow')
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            game.grid[row + dy][col + dx] = Dot(card.color)
        game.yellow_dot_position = (row, col)
        game.current_player_idx = session.player_order.index(name)
        game.can_roll_dice = False
        game.turn_cards_played = dict.fromkeys(session.player_order, 0)
        game.must_advance_after_roll = {}
        for participant in game.players.values():
            participant['score'] = dict.fromkeys(game.colors, 0)
            participant['yellow_dots'] = participant['total_dots'] = 0
        if data.get('winning'):
            player['score'] = dict.fromkeys(game.colors, 5)
            player['score'][card.color] = 4
            player['yellow_dots'] = 4
            player['total_dots'] = 23
            if session.game_mode == 'twenty_dots':
                player['score'] = dict.fromkeys(game.colors, 0)
                player['score'][card.color] = 19
                player['yellow_dots'] = 0
                player['total_dots'] = 19
        if data.get('exhaust'):
            session.recycle_pool.extend(game.deck)
            game.deck = []
        spare = next(c for c in player['hand'] if c.location != card.location)
        session.send_started_game()
        return {'location': ''.join(card.location), 'color': card.color,
            'round_id': session.round_id,
            'spare': {'location': ''.join(spare.location), 'color': spare.color}}


def prepare_power(session, data):
    """Arrange physical power cards without changing the production rules or handlers."""
    if not session.power_cards or data['power'] not in server.ONLINE_POWERS:
        abort(400)
    game = session.game
    name = data['player']
    player = game.players[name]
    game.deck.extend(player['hand'])
    player['hand'].clear()
    pools = [game.deck, session.recycle_pool] + [p['hand'] for p in game.players.values()]

    def take(predicate):
        for pool in pools:
            for card in pool:
                if predicate(card):
                    pool.remove(card)
                    return card
        raise AssertionError('Fixture card not found')

    for power in server.ONLINE_POWERS:
        player['hand'].append(take(lambda card: card.power == power and card.color == 'red'))
    for location in ('F5', 'F6'):
        player['hand'].append(take(lambda card: card.power is None
                                   and ''.join(card.location) == location and card.color == 'green'))
    game.current_player_idx = session.player_order.index(name)
    game.can_roll_dice = bool(data.get('roll'))
    game.turn_cards_played = dict.fromkeys(session.player_order, 0)
    game.must_advance_after_roll = {}
    game.grid = [[None for _ in range(6)] for _ in range(6)]
    game.yellow_dot_position = None
    if data['power'] == 'shift':
        game.grid[1][2] = Dot('blue')
        game.grid[2][0] = Dot('blue')
        game.grid[2][1] = Dot('blue')
        game.grid[5][0] = Dot('yellow')
        game.yellow_dot_position = (5, 0)
        if data.get('blocked'):
            game.grid = [[None for _ in range(6)] for _ in range(6)]
            game.grid[0][0] = Dot('blue')
            game.grid[0][1] = Dot('yellow')
            game.grid[1][0] = Dot('yellow')
            game.yellow_dot_position = None
    else:
        game.grid[0][0] = Dot('red')
        game.grid[0][1] = Dot('yellow' if data.get('yellow') else 'red')
        if data.get('yellow'):
            game.yellow_dot_position = (0, 1)
    for participant in game.players.values():
        participant['score'] = dict.fromkeys(game.colors, 0)
        participant['yellow_dots'] = participant['total_dots'] = 0
    if data.get('winning'):
        player['score']['red'] = 19
        player['total_dots'] = 19
    if data.get('exhaust'):
        session.recycle_pool.extend(game.deck)
        game.deck = []
    session.send_started_game()
    return {'round_id': session.round_id, 'power': data['power']}


if __name__ == '__main__':
    if not os.environ.get('BROWSER_FIXTURE_KEY'):
        raise SystemExit('Use the browser replay test runner; a fixture key is required.')
    server.app.add_url_rule('/__test__/position', view_func=prepare_position, methods=['POST'])
    server.socketio.run(server.app, host='127.0.0.1',
                        port=int(os.environ.get('BROWSER_FIXTURE_PORT', '5001')),
                        debug=False, allow_unsafe_werkzeug=True)