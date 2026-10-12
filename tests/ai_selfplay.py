"""Head-to-head AI strength check: py -3 tests/ai_selfplay.py [games] [mode] [--powers].

Plays two-seat games through the real GameSession turn loop, swapping seats each game,
and reports win rates plus the slowest single AI decision.
"""
import contextlib
import io
import os
import random
import sys
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import flask_socketio

_socketio = flask_socketio.SocketIO
with patch('flask_socketio.SocketIO', side_effect=lambda *a, **kw: _socketio(
        *a, **dict(kw, async_mode='threading'))):
    import game_server as server
from ai_player import AIPlayer


def play(first, second, mode, powers, seed):
    random.seed(seed)
    session = server.GameSession(f'g{seed}', 's0', mode, 2, powers)
    for i, difficulty in enumerate((first, second)):
        session.add_player(f's{i}', f'P{i}', is_ai=True)
        session.ai_players[f'P{i}'].difficulty = difficulty
        session.ai_players[f'P{i}'].rng.seed(seed * 2 + i)
    session.initialize_game()
    slowest, turns = 0.0, 0
    while not session.check_winner() and turns < 1000:
        start = time.perf_counter()
        session.execute_ai_move()
        slowest = max(slowest, time.perf_counter() - start)
        turns += 1
    result = session.check_winner()
    return (result['winner'] if result else None), slowest, turns


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    games = int(args[0]) if args else 40
    mode = args[1] if len(args) > 1 else 'twenty_dots'
    powers = '--powers' in sys.argv
    pairings = [('hard', 'medium'), ('medium', 'easy'), ('hard', 'easy')]
    with patch.object(server.socketio, 'start_background_task'):
        for a, b in pairings:
            wins = {a: 0, b: 0, None: 0}
            slowest = 0.0
            for g in range(games):
                seats = (a, b) if g % 2 == 0 else (b, a)
                with contextlib.redirect_stdout(io.StringIO()):
                    winner, slow, _ = play(*seats, mode, powers, seed=g)
                slowest = max(slowest, slow)
                wins[seats[int(winner[1:])] if winner else None] += 1
            print(f'{mode}{" +powers" if powers else ""}: {a} {wins[a]} - {wins[b]} {b}'
                  f' ({wins[None]} unfinished), slowest turn {slowest:.2f}s', flush=True)


if __name__ == '__main__':
    main()
