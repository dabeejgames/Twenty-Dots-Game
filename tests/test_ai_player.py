"""Board-aware AI: simulator parity with the server rules, and decision regressions."""
import os
os.environ.setdefault('ROOM_STORE', 'off')  # Tests never touch the saved-room store.
import contextlib
import io
import random
import unittest
from unittest.mock import patch

import flask_socketio

_socketio = flask_socketio.SocketIO
with patch('flask_socketio.SocketIO', side_effect=lambda *a, **kw: _socketio(
        *a, **dict(kw, async_mode='threading'))):
    import game_server as server

import ai_player
from ai_player import AIPlayer, simulate_cards, simulate_power
from twenty_dots import Card, Dot

COLORS = ('red', 'blue', 'purple', 'green')


def colors(session):
    return [[dot.color if dot else None for dot in row] for row in session.game.grid]


class AITestCase(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        background = patch.object(server.socketio, 'start_background_task')
        background.start()
        self.addCleanup(background.stop)

    def session(self, players=2, mode='twenty_dots', power_cards=False, board=None):
        session = server.GameSession('ai', 'sid0', mode, players, power_cards)
        for i in range(players):
            session.add_player(f'sid{i}', f'P{i}', is_ai=True)
        session.initialize_game()
        session.game.can_roll_dice = False
        if board is not None:
            session.game.grid = [[Dot(c) if c else None for c in row] for row in board]
        return session

    def random_board(self, rng, fill=0.6):
        board = [[rng.choice(COLORS) if rng.random() < fill else None for _ in range(6)]
                 for _ in range(6)]
        if rng.random() < 0.7:
            board[rng.randrange(6)][rng.randrange(6)] = 'yellow'
        return board


class SimulatorParityTests(AITestCase):
    def gains_of(self, session, name):
        p = session.game.players[name]
        return {'total': p['total_dots'], 'yellow': p['yellow_dots'], **p['score']}

    def test_card_simulation_matches_server(self):
        rng = random.Random(7)
        for trial in range(300):
            board = self.random_board(rng, rng.choice((0.3, 0.6, 0.85)))
            session = self.session(board=board)
            cards = [Card(rng.choice('ABCDEF') + rng.choice('123456'), rng.choice(COLORS))
                     for _ in range(2)]
            if cards[0].location == cards[1].location:
                cards.pop()
            session.game.players['P0']['hand'] = list(cards)
            new_board, gains, wild = simulate_cards(
                board, [(c.location, c.color) for c in cards])
            replaced, collected = session.apply_cards('P0', cards)
            with self.subTest(trial=trial, board=board, cards=cards):
                self.assertEqual(new_board, colors(session))
                self.assertEqual(gains, self.gains_of(session, 'P0'))
                self.assertEqual(wild, replaced or collected)

    def test_power_simulation_matches_server(self):
        rng = random.Random(11)
        checked = 0
        for trial in range(300):
            board = self.random_board(rng, rng.choice((0.3, 0.6, 0.85)))
            session = self.session(power_cards=True, board=board)
            power, color = rng.choice(server.ONLINE_POWERS), rng.choice(COLORS)
            session.game.players['P0']['hand'] = [Card('PWR', color, power)]
            rival = session.game.players['P1']
            rival['score'] = {c: rng.randrange(3) for c in COLORS}
            rival['total_dots'] = sum(rival['score'].values())
            options = session.ai_power_options('P0')
            if not options:
                continue
            card, targets, cells = rng.choice(options)
            new_board, gains, _ = simulate_power(board, power, color, cells)
            _, players = AIPlayer('hard')._tax_harm('P1', color, session.ai_context('P0'))
            session.apply_power('P0', card, targets)
            checked += 1
            with self.subTest(trial=trial, board=board, power=power, targets=targets):
                # The AI's board marks blocked squares, exactly like the server's AI context.
                self.assertEqual(new_board, session.ai_context('P0')['board'])
                self.assertEqual(gains, self.gains_of(session, 'P0'))
                if power == 'tax':
                    self.assertEqual(players['P1']['score'], rival['score'])
                    self.assertEqual(players['P1']['total_dots'], rival['total_dots'])
        self.assertGreater(checked, 200)

    def test_power_options_are_all_legal_and_cover_every_target(self):
        board = [[None] * 6 for _ in range(6)]
        board[2][2], board[0][0], board[5][5] = 'red', 'blue', 'red'
        session = self.session(power_cards=True, board=board)
        session.game.players['P0']['hand'] = [Card('PWR', 'red', 'shift'),
                                             Card('PWR', 'red', 'swap')]
        options = session.ai_power_options('P0')
        shifts = sorted(t for c, t, _ in options if c['power'] == 'shift')
        swaps = sorted(t for c, t, _ in options if c['power'] == 'swap')
        self.assertEqual(shifts, [['C3', 'B3'], ['C3', 'C2'], ['C3', 'C4'], ['C3', 'D3'],
                                  ['F6', 'E6'], ['F6', 'F5']])
        self.assertEqual(swaps, [['A1', 'C3'], ['A1', 'F6']])  # Never red with red.


class DecisionTests(AITestCase):
    def context(self, session, name='P0'):
        return session.ai_context(name)

    def hand(self, session, *cards):
        session.game.players['P0']['hand'] = [Card(loc, color) for loc, color in cards]
        return session.game.players['P0']['hand']

    def test_medium_and_hard_complete_an_open_line(self):
        board = [[None] * 6 for _ in range(6)]
        board[0][0] = board[0][1] = 'blue'
        for difficulty in ('medium', 'hard'):
            with self.subTest(difficulty=difficulty):
                session = self.session(board=board)
                hand = self.hand(session, ('D4', 'red'), ('A3', 'blue'), ('F1', 'green'))
                picks = AIPlayer(difficulty).choose_cards(hand, self.context(session))
                self.assertIn(1, picks)

    def test_hard_does_not_hand_the_next_player_a_line(self):
        # Red A1 beside red A2 leaves A3 open for anyone holding red A3.
        board = [[None] * 6 for _ in range(6)]
        board[0][1] = 'red'
        session = self.session(board=board)
        hand = self.hand(session, ('A1', 'red'), ('F6', 'blue'))
        picks = AIPlayer('hard').choose_cards(hand, self.context(session))
        self.assertEqual(picks, [1])

    def test_hard_ends_the_turn_rather_than_feed_opponents(self):
        board = [[None] * 6 for _ in range(6)]
        board[3][3] = board[3][4] = 'purple'
        session = self.session(board=board)
        session.game.turn_cards_played['P0'] = 1
        hand = self.hand(session, ('E5', 'purple'))  # Two new purple pairs, no line.
        self.assertEqual(AIPlayer('hard').choose_cards(hand, self.context(session)), [])
        self.assertEqual(AIPlayer('medium').choose_cards(hand, self.context(session)), [0])

    def test_color_goals_prefer_the_color_still_needed(self):
        board = [[None] * 6 for _ in range(6)]
        board[0][0] = board[0][1] = 'red'
        board[5][0] = board[5][1] = 'blue'
        session = self.session(mode='five_colors', board=board)
        session.game.players['P0']['score'].update(red=5, blue=1)
        session.game.turn_cards_played['P0'] = 1  # One card: which line is worth more?
        hand = self.hand(session, ('A3', 'red'), ('F3', 'blue'))
        for difficulty in ('medium', 'hard'):
            picks = AIPlayer(difficulty).choose_cards(hand, self.context(session))
            self.assertEqual(picks, [1], difficulty)

    def test_hard_takes_the_winning_line(self):
        board = [[None] * 6 for _ in range(6)]
        board[2][0] = board[2][1] = 'purple'
        session = self.session(board=board)
        session.game.players['P0']['total_dots'] = 17
        hand = self.hand(session, ('F6', 'red'), ('C3', 'purple'))
        picks = AIPlayer('hard').choose_cards(hand, self.context(session))
        self.assertEqual(picks[0], 1)

    def test_power_beats_a_dead_hand(self):
        board = [[None] * 6 for _ in range(6)]
        board[1][0], board[1][2] = 'green', 'green'
        session = self.session(power_cards=True, board=board)
        hand = self.hand(session, ('F6', 'red'), ('F5', 'blue'))
        session.game.players['P0']['hand'] = hand + [Card('PWR', 'green', 'paint')]
        for difficulty in ('medium', 'hard'):
            with self.subTest(difficulty=difficulty):
                session.ai_players['P0'] = AIPlayer(difficulty)
                options = session.ai_power_options('P0')
                self.assertEqual(AIPlayer(difficulty).choose_cards(
                    hand, session.ai_context('P0', options)), [])
                card, targets = session.choose_ai_power('P0')
                self.assertEqual((card['power'], targets), ('paint', ['B2']))

    def test_dead_hand_blocks_an_opponents_open_line(self):
        # Red A1-A2 leaves A3 open for anyone holding red A3.
        for power, expected in (('block', [['A3']]),):
            for difficulty in ('medium', 'hard'):
                with self.subTest(power=power, difficulty=difficulty):
                    board = [[None] * 6 for _ in range(6)]
                    board[0][0] = board[0][1] = 'red'
                    session = self.session(power_cards=True, board=board)
                    hand = self.hand(session, ('F6', 'blue'), ('E5', 'green'))
                    session.game.players['P0']['hand'] = hand + [Card('PWR', 'red', power)]
                    session.ai_players['P0'] = AIPlayer(difficulty)
                    options = session.ai_power_options('P0')
                    self.assertEqual(AIPlayer(difficulty).choose_cards(
                        hand, session.ai_context('P0', options)), [])
                    card, targets = session.choose_ai_power('P0')
                    self.assertEqual(card['power'], power)
                    self.assertIn(targets, expected)

    def test_dead_hand_taxes_the_leader(self):
        session = self.session(3, power_cards=True)
        session.game.players['P1']['score']['purple'] = 6
        session.game.players['P1']['total_dots'] = 6
        session.game.players['P2']['score']['purple'] = 3
        session.game.players['P2']['total_dots'] = 3
        hand = self.hand(session, ('F6', 'blue'), ('E5', 'green'))
        session.game.players['P0']['hand'] = hand + [Card('PWR', 'purple', 'tax')]
        options = session.ai_power_options('P0')
        self.assertEqual([targets for _, targets, _ in options], [['P1']])  # Never the trailer.
        for difficulty in ('medium', 'hard'):
            with self.subTest(difficulty=difficulty):
                session.ai_players['P0'] = AIPlayer(difficulty)
                self.assertEqual(AIPlayer(difficulty).choose_cards(
                    hand, session.ai_context('P0', options)), [])
                card, targets = session.choose_ai_power('P0')
                self.assertEqual((card['power'], targets), ('tax', ['P1']))

    def test_ai_never_plans_on_a_blocked_square(self):
        board = [[None] * 6 for _ in range(6)]
        board[0][0] = board[0][1] = 'red'
        session = self.session(board=board)
        session.blocks = [{'location': 'A3', 'player': 'P1'}]
        hand = self.hand(session, ('A3', 'red'), ('F6', 'blue'))
        context = session.ai_context('P0')
        self.assertEqual(context['board'][0][2], ai_player.BLOCK)
        self.assertEqual([''.join(c.location) for c in context['regular_hand']], ['F6'])
        for difficulty in ('medium', 'hard'):
            with self.subTest(difficulty=difficulty):
                picks = AIPlayer(difficulty).choose_cards(context['regular_hand'], context)
                self.assertIn(picks, ([0], []))
        session.ai_players['P0'] = AIPlayer('hard')
        session.execute_ai_move()
        self.assertIsNotNone(session.game.grid[0][0])  # The red pair was never collected.
        self.assertIn(hand[0], session.game.players['P0']['hand'])

    def strategy_session(self, board, market):
        session = self.session(board=board)
        session.strategy_rules = True
        session.market = [Card(loc, color) for loc, color in market]
        return session

    def test_strategy_ai_takes_a_market_line_with_a_dead_hand(self):
        board = [[None] * 6 for _ in range(6)]
        board[0][0] = board[0][1] = 'red'
        session = self.strategy_session(board, [('F6', 'blue'), ('A3', 'red'), ('E1', 'green')])
        hand = self.hand(session, ('F1', 'blue'), ('D6', 'purple'))
        for difficulty in ('medium', 'hard'):
            with self.subTest(difficulty=difficulty):
                picks = AIPlayer(difficulty).choose_cards(hand, self.context(session))
                self.assertIn(3, picks)  # Hand indices 0-1, then market 2-4: A3 is 3.
                self.assertLessEqual(sum(i >= 2 for i in picks), 1)
        session.market_played = True
        context = self.context(session)
        self.assertEqual(len(context['market']), 3)  # Still visible to weigh threats,
        self.assertFalse(context['market_playable'])  # but not playable again this turn.
        for difficulty in ('medium', 'hard'):
            self.assertTrue(all(i < 2 for i in AIPlayer(difficulty).choose_cards(hand, context)))
        self.assertEqual(AIPlayer('hard').choose_cards([], context), [])

    def test_hard_counts_a_finishing_market_card_as_a_sure_threat(self):
        # Red A1-B1 with red C1 face up: the next player is certain to finish the line.
        board = [[None] * 6 for _ in range(6)]
        board[0][0] = board[1][0] = 'red'
        session = self.strategy_session(board, [])
        ai, context = AIPlayer('hard'), self.context(session)
        plan = {'board': board, 'gains': ai_player.empty_gains(), 'wild': False,
                'played': 0, 'hand': [], 'market': [('F6', 'blue')]}
        safe = ai._lookahead(plan, context)
        exposed = ai._lookahead({**plan, 'market': [('C1', 'red')]}, context)
        self.assertGreaterEqual(safe - exposed, 3 - 0.5)  # About the three dots handed over.

    def test_strategy_ai_chooses_the_wild_square_that_scores(self):
        board = [[None] * 6 for _ in range(6)]
        board[2][0] = board[2][1] = 'blue'
        session = self.strategy_session(board, [])
        for difficulty in ('medium', 'hard'):
            with self.subTest(difficulty=difficulty):
                options = ['F6', 'C3']
                self.assertEqual(AIPlayer(difficulty).choose_wild(options, self.context(session)), 1)
        self.assertIn(AIPlayer('easy').choose_wild(['F6', 'C3'], self.context(session)), (0, 1))

    def test_full_strategy_games_finish_for_every_difficulty(self):
        for difficulty in ('easy', 'medium', 'hard'):
            with self.subTest(difficulty=difficulty):
                random.seed(4)
                session = server.GameSession('ai', 'sid0', 'twenty_dots', 3, True, True)
                for i in range(3):
                    session.add_player(f'sid{i}', f'P{i}', is_ai=True)
                session.initialize_game()
                for ai in session.ai_players.values():
                    ai.difficulty = difficulty
                    ai.rng.seed(6)
                for _ in range(600):
                    if session.check_winner():
                        break
                    session.execute_ai_move()
                self.assertTrue(session.check_winner())
                self.assertEqual(session.wild_options, [])

    def test_full_ai_games_finish_for_every_difficulty_and_mode(self):
        for mode in ('twenty_dots', 'five_colors', 'five_with_yellow'):
            for difficulty in ('easy', 'medium', 'hard'):
                with self.subTest(mode=mode, difficulty=difficulty):
                    random.seed(3)
                    session = self.session(3, mode, power_cards=True)
                    session.game.can_roll_dice = True
                    for ai in session.ai_players.values():
                        ai.difficulty = difficulty
                        ai.rng.seed(5)
                    for _ in range(600):
                        if session.check_winner():
                            break
                        session.execute_ai_move()
                    self.assertTrue(session.check_winner())


if __name__ == '__main__':
    unittest.main()
