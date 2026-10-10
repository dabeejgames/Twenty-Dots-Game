"""Socket.IO protocol regressions; run with unittest discover -s tests -v."""
import contextlib
import io
import unittest
from unittest.mock import patch

import flask_socketio
from socketio import packet

# Select threading only while importing the server, not in production configuration.
_socketio = flask_socketio.SocketIO
with patch('flask_socketio.SocketIO', side_effect=lambda *a, **kw: _socketio(
        *a, **dict(kw, async_mode='threading'))):
    import game_server as server

from twenty_dots import Card, Dot


class MultiplayerTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        server.games.clear()
        server.app.config['TESTING'] = True
        self.clients = []
        self.background = patch.object(server.socketio, 'start_background_task')
        self.schedule = self.background.start()
        # Flask-SocketIO 5.3.5's test client intercepts _send_packet only, but
        # python-socketio 5.10 emits JSON through _send_eio_packet. Bridge that
        # path back to the real test client's packet decoder/queue (no fake events).
        self.transport = patch.object(
            server.socketio.server, '_send_eio_packet',
            side_effect=lambda sid, pkt: server.socketio.server._send_packet(
                sid, packet.Packet(encoded_packet=pkt.data)))
        self.transport.start()

    def tearDown(self):
        for client in self.clients:
            if client.is_connected():
                client.disconnect()
        server.games.clear()
        self.transport.stop()
        self.background.stop()
        self.output.__exit__(None, None, None)

    def client(self):
        client = server.socketio.test_client(server.app)
        self.clients.append(client)
        client.get_received()
        return client

    def emit(self, client, event, **data):
        client.get_received()
        client.emit(event, data)
        return client.get_received()

    def payload(self, events, name):
        matches = [event['args'][0] for event in events if event['name'] == name]
        self.assertTrue(matches, f'Missing {name}: {events}')
        return matches[-1]

    def join(self, client, name, room='room', **options):
        return self.emit(client, 'join_game', game_id=room, player_name=name, **options)

    def started(self):
        first, second = self.client(), self.client()
        self.join(first, 'Alice')
        self.join(second, 'Bob')
        return first, second, server.games['room']

    def test_two_to_four_players_autostart_and_collision_safe_names(self):
        for count in (2, 3, 4):
            with self.subTest(count=count):
                room = f'room{count}'
                names = ['Player 2', 'Player 1', 'Player 4', 'Player 3'][:count]
                for index, name in enumerate(names):
                    events = self.join(self.client(), name, room, player_count=count)
                    session = server.games[room]
                    self.assertEqual(session.started, index == count - 1)
                    self.payload(events, 'lobby_updated')
                self.assertEqual(list(session.game.players), names)
                self.assertEqual(session.game.get_current_player(), names[0])
                self.assertEqual(len({id(p) for p in session.game.players.values()}), count)
                self.assertTrue(all(len(p['hand']) == 5 for p in session.game.players.values()))

    def test_explicit_invite_and_rejoin_do_not_create_missing_room(self):
        for intent in ('join', 'rejoin'):
            events = self.join(self.client(), 'Alice', intent=intent)
            self.payload(events, 'error')
            self.assertNotIn('room', server.games)

    def test_validation(self):
        invalid = [
            {'player_name': ''}, {'player_name': '  '}, {'player_name': 'x' * 25},
            {'player_name': 3}, {'game_id': ''}, {'game_id': 'x' * 65},
            {'game_id': []}, {'player_count': 1}, {'player_count': 5},
            {'player_count': 'bad'}, {'player_count': 2.5}, {'player_count': True},
            {'game_mode': 'bad'}, {'intent': 'bad'}, {'resume_token': []},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                data = dict(game_id='room', player_name='Alice')
                data.update(changes)
                self.payload(self.emit(self.client(), 'join_game', **data), 'error')
                self.assertFalse(server.games)

    def test_token_lobby_resume_and_private_token(self):
        host = self.client()
        events = self.join(host, 'Alice', intent='create', player_count=3)
        joined = self.payload(events, 'join_success')
        token = joined['resume_token']
        self.assertIsInstance(token, str)
        self.assertGreaterEqual(len(token), 32)
        self.assertNotIn(token, str(self.payload(events, 'lobby_updated')))
        peer = self.client()
        peer_events = self.join(peer, 'Bob', intent='join')
        self.assertNotIn(token, str(peer_events))
        host.disconnect()
        lobby = self.payload(peer.get_received(), 'lobby_updated')
        self.assertFalse(lobby['players'][0]['connected'])
        resumed = self.client()
        self.payload(self.join(resumed, 'Alice', intent='rejoin'), 'error')
        self.payload(self.join(resumed, 'Alice', intent='rejoin', resume_token='wrong'), 'error')
        events = self.join(resumed, 'Alice', intent='rejoin', resume_token=token)
        self.assertEqual(self.payload(events, 'join_success')['resume_token'], token)
        self.assertNotIn('game_started', [e['name'] for e in events])
        self.assertNotIn('your_hand', [e['name'] for e in events])
        session = server.games['room']
        self.assertEqual(session.get_player_name(session.host_sid), 'Alice')
        self.assertTrue(session.players[session.host_sid]['connected'])

    def test_connected_names_cannot_be_stolen_and_legacy_can_resume(self):
        host = self.client()
        self.join(host, 'Alice')
        sid = server.games['room'].host_sid
        attacker = self.client()
        self.payload(self.join(attacker, 'Alice'), 'error')
        self.assertEqual(server.games['room'].host_sid, sid)
        host.disconnect()
        events = self.join(attacker, 'Alice')
        self.payload(events, 'join_success')
        self.assertNotEqual(server.games['room'].host_sid, sid)

    def test_token_does_not_steal_connected_seat(self):
        host = self.client()
        token = self.payload(self.join(host, 'Alice', intent='create'), 'join_success')['resume_token']
        self.payload(self.join(self.client(), 'Alice', intent='rejoin', resume_token=token), 'error')

    def test_create_existing_rejoin_unknown_and_duplicate_sid_rejected(self):
        host = self.client()
        self.join(host, 'Alice', player_count=4)
        for client, name, intent in ((self.client(), 'Bob', 'create'),
                                     (self.client(), 'Bob', 'rejoin'),
                                     (host, 'Bob', 'join')):
            self.payload(self.join(client, name, intent=intent), 'error')
        self.assertEqual(server.games['room'].player_order, ['Alice'])

    def test_pregame_leave_transfers_host_and_last_leave_deletes_room(self):
        host, peer = self.client(), self.client()
        self.join(host, 'Alice', player_count=3)
        self.join(peer, 'Bob')
        self.emit(host, 'leave_game', game_id='room')
        session = server.games['room']
        self.assertEqual(session.player_order, ['Bob'])
        lobby = self.payload(peer.get_received(), 'lobby_updated')
        self.assertEqual(lobby['players'], [{'name': 'Bob', 'connected': True, 'is_host': True}])
        self.emit(peer, 'leave_game', game_id='room')
        self.assertNotIn('room', server.games)

    def test_in_game_leave_keeps_seat_and_can_rejoin(self):
        first, second, session = self.started()
        self.emit(first, 'leave_game', game_id='room')
        self.assertEqual(session.player_order, ['Alice', 'Bob'])
        self.assertFalse(session.get_game_state()['players']['Alice']['connected'])
        events = self.join(first, 'Alice')
        self.payload(events, 'game_started')
        self.assertEqual(len(self.payload(events, 'your_hand')['hand']), 5)

    def test_state_fields(self):
        first, second, session = self.started()
        state = session.get_game_state()
        self.assertEqual(state['required_players'], 2)
        self.assertIsNone(state['winner'])
        self.assertEqual(state['cards_played_this_turn'], 0)
        session.game.turn_cards_played['Alice'] = 1
        self.assertEqual(session.get_game_state()['cards_played_this_turn'], 1)
        second.disconnect()
        self.assertFalse(session.get_game_state()['players']['Bob']['connected'])

    def test_lobby_and_out_of_turn_actions_rejected(self):
        first = self.client()
        self.join(first, 'Alice')
        for event in ('roll_dice', 'play_cards', 'pass_turn', 'end_turn'):
            self.payload(self.emit(first, event, game_id='room', cards=[]), 'error')
        second = self.client()
        self.join(second, 'Bob')
        for event in ('roll_dice', 'play_cards', 'pass_turn', 'end_turn'):
            self.payload(self.emit(second, event, game_id='room', cards=[]), 'error')

    def test_required_roll_and_repeat_roll_guards(self):
        first, second, session = self.started()
        card = session.get_player_hand('Alice')[0]
        for event in ('play_cards', 'end_turn', 'pass_turn'):
            self.payload(self.emit(first, event, game_id='room', cards=[card]), 'error')
        with patch.object(session.game, 'roll_dice', return_value=('F', '6')):
            self.emit(first, 'roll_dice', game_id='room')
            state = session.get_game_state()
            self.payload(self.emit(first, 'roll_dice', game_id='room'), 'error')
            self.assertEqual(session.get_game_state(), state)

    def test_end_and_pass_reset_incoming_counter(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        session.game.turn_cards_played['Bob'] = 2
        self.emit(first, 'end_turn', game_id='room')
        self.assertEqual(session.game.turn_cards_played['Bob'], 0)
        session.game.turn_cards_played['Alice'] = 2
        self.emit(second, 'pass_turn', game_id='room')
        self.assertEqual(session.game.turn_cards_played['Alice'], 0)

    def test_card_limit_is_not_reset_by_play_request(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        session.game.turn_cards_played['Alice'] = 2
        before = list(session.game.players['Alice']['hand'])
        card = session.get_player_hand('Alice')[0]
        self.payload(self.emit(first, 'play_cards', game_id='room', cards=[card]), 'error')
        self.assertEqual(session.game.turn_cards_played['Alice'], 2)
        self.assertEqual(session.game.players['Alice']['hand'], before)

    def test_yellow_replacement_roll_advances_and_schedules_ai(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        session.game.players['Alice']['hand'] = [Card('A1', 'red'), Card('C3', 'blue')]
        session.game.grid[0][0] = Dot('yellow')
        cards = session.get_player_hand('Alice')
        self.emit(first, 'play_cards', game_id='room', cards=cards)
        self.assertEqual(session.game.turn_cards_played['Alice'], 2)
        self.assertTrue(session.game.can_roll_dice)
        self.assertEqual(session.game.get_current_player(), 'Alice')
        session.ai_players['Bob'] = object()
        session.game.turn_cards_played['Bob'] = 2
        with patch.object(session.game, 'roll_dice', return_value=('F', '6')):
            self.emit(first, 'roll_dice', game_id='room')
        self.assertEqual(session.game.get_current_player(), 'Bob')
        self.assertEqual(session.game.turn_cards_played['Bob'], 0)
        self.assertNotIn(None, session.game.turn_cards_played)
        self.schedule.assert_called_once_with(session.execute_ai_move)

    def test_terminal_winner_blocks_actions_restart_and_replays_on_resume(self):
        first, second, session = self.started()
        session.game.players['Alice']['total_dots'] = 20
        expected = {'winner': 'Alice', 'condition': 'twenty_dots'}
        self.assertEqual(session.get_game_state()['winner'], expected)
        before = session.get_game_state()
        for event in ('roll_dice', 'play_cards', 'pass_turn', 'end_turn', 'start_game'):
            self.payload(self.emit(first, event, game_id='room', cards=[]), 'error')
            self.assertEqual(session.get_game_state(), before)
        first.disconnect()
        events = self.join(self.client(), 'Alice')
        self.assertEqual(self.payload(events, 'game_over'), expected)
        self.assertEqual(self.payload(events, 'game_started')['winner'], expected)
        session.game.players['Alice']['total_dots'] = 0
        self.assertEqual(session.get_game_state()['winner'], expected)
        session.ai_players['Alice'] = object()
        session.execute_ai_move()
        self.assertFalse(session.ai_move_in_progress)

    def test_winning_play_emits_terminal_state(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        session.game.players['Alice']['total_dots'] = 19
        session.game.players['Alice']['hand'] = [Card('A1', 'red')]
        session.game.grid[0][0] = Dot('blue')
        events = self.emit(first, 'play_cards', game_id='room', cards=session.get_player_hand('Alice'))
        expected = {'winner': 'Alice', 'condition': 'twenty_dots'}
        self.assertEqual(self.payload(events, 'game_over'), expected)
        self.assertEqual(self.payload(events, 'game_updated')['winner'], expected)

    def test_manual_and_single_player_initialization_safe_names(self):
        host = self.client()
        self.emit(host, 'create_game', game_id='manual', player_name='Player 2')
        self.emit(host, 'add_ai_player', game_id='manual', ai_name='Player 1')
        self.emit(host, 'start_game', game_id='manual')
        session = server.games['manual']
        self.assertEqual(list(session.game.players), ['Player 2', 'Player 1'])
        self.assertTrue(all(len(p['hand']) == 5 for p in session.game.players.values()))
        events = self.emit(self.client(), 'start_single_player', player_name='Player 2', num_players=4)
        state = self.payload(events, 'game_started')
        self.assertEqual(list(state['players']), ['Player 2', 'AI 1', 'AI 2', 'AI 3'])
        self.assertEqual(state['required_players'], 4)

    def test_winner_modes_are_latched(self):
        first, second, session = self.started()
        alice = session.game.players['Alice']
        alice['score'] = dict.fromkeys(session.game.colors, 5)
        session.game_mode = 'five_with_yellow'
        self.assertIsNone(session.get_game_state()['winner'])
        alice['yellow_dots'] = 5
        self.assertEqual(session.get_game_state()['winner'], {
            'winner': 'Alice', 'condition': 'five_with_yellow'})
        session.winner = None
        session.game_mode = 'five_colors'
        self.assertEqual(session.get_game_state()['winner'], {
            'winner': 'Alice', 'condition': 'five_colors'})

    def test_roll_match_wins_and_emits_terminal_state(self):
        first, second, session = self.started()
        session.game.players['Alice']['total_dots'] = 18
        session.game.grid[0][0] = Dot('red')
        session.game.grid[0][1] = Dot('red')
        with patch.object(session.game, 'roll_dice', return_value=('A', '3')):
            events = self.emit(first, 'roll_dice', game_id='room')
        expected = {'winner': 'Alice', 'condition': 'twenty_dots'}
        self.assertEqual(self.payload(events, 'game_updated')['winner'], expected)
        self.assertEqual(self.payload(events, 'game_over'), expected)
        self.schedule.assert_not_called()

    def test_matching_post_card_roll_keeps_turn_until_nonmatching_roll(self):
        first, second, session = self.started()
        session.game.turn_cards_played['Alice'] = 2
        session.game.turn_cards_played['Bob'] = 2
        session.game.must_advance_after_roll['Alice'] = True
        session.game.grid[0][0] = Dot('red')
        session.game.grid[0][1] = Dot('red')
        with patch.object(session.game, 'roll_dice', side_effect=[('A', '3'), ('F', '6')]):
            self.emit(first, 'roll_dice', game_id='room')
            self.assertEqual(session.game.get_current_player(), 'Alice')
            self.assertEqual(session.game.turn_cards_played['Alice'], 2)
            self.assertTrue(session.game.can_roll_dice)
            self.emit(first, 'roll_dice', game_id='room')
        self.assertEqual(session.game.get_current_player(), 'Bob')
        self.assertEqual(session.game.turn_cards_played['Bob'], 0)

    def test_two_separate_card_plays_advance_and_reset_incoming_player(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        session.game.players['Alice']['hand'] = [Card('A1', 'red'), Card('C3', 'blue')]
        session.game.turn_cards_played['Bob'] = 2
        cards = session.get_player_hand('Alice')
        self.emit(first, 'play_cards', game_id='room', cards=cards[:1])
        self.assertEqual(session.get_game_state()['cards_played_this_turn'], 1)
        self.emit(first, 'play_cards', game_id='room', cards=cards[1:])
        self.assertEqual(session.game.get_current_player(), 'Bob')
        self.assertEqual(session.get_game_state()['cards_played_this_turn'], 0)
        self.assertEqual(len(session.game.players['Alice']['hand']), 5)

    def test_ai_winning_yellow_play_broadcasts_game_over_without_another_action(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        session.game.players['Alice']['total_dots'] = 19
        session.game.players['Alice']['hand'] = [Card('A1', 'red')]
        session.game.grid[0][0] = Dot('yellow')
        session.ai_players['Alice'] = server.AIPlayer('medium')
        with patch.object(session.ai_players['Alice'], 'choose_cards', return_value=[0]):
            session.execute_ai_move()
        expected = {'winner': 'Alice', 'condition': 'twenty_dots'}
        self.assertEqual(self.payload(first.get_received(), 'game_over'), expected)
        self.assertEqual(session.get_game_state()['winner'], expected)
        self.assertEqual(session.game.get_current_player(), 'Alice')
        self.assertFalse(session.ai_move_in_progress)
        self.schedule.assert_not_called()

    def test_ai_roll_completes_wild_match(self):
        first, second, session = self.started()
        session.game.grid[4][3] = Dot('blue')
        session.game.grid[4][4] = Dot('blue')
        session.ai_players['Alice'] = server.AIPlayer('medium')
        with patch.object(session.game, 'roll_dice', side_effect=[('E', '6'), ('A', '1')]), \
                patch.object(session.ai_players['Alice'], 'choose_cards', return_value=[]):
            session.execute_ai_move()
        alice = session.game.players['Alice']
        self.assertEqual(alice['score']['blue'], 2)
        self.assertEqual(alice['yellow_dots'], 1)
        self.assertIsNone(session.game.grid[4][3])
        self.assertIsNone(session.game.grid[4][4])
        self.assertEqual(session.game.grid[4][5], None)
        self.assertEqual(session.game.grid[0][0].color, 'yellow')

    def test_resume_token_field_alone_opts_in_and_started_resume_is_private(self):
        first, second = self.client(), self.client()
        events = self.join(first, 'Alice', resume_token=None)
        token = self.payload(events, 'join_success')['resume_token']
        self.assertIsInstance(token, str)
        self.join(second, 'Bob')
        first.disconnect()
        resumed = self.client()
        self.payload(self.join(resumed, 'Alice'), 'error')
        second.get_received()
        events = self.join(resumed, 'Alice', resume_token=token)
        state = self.payload(events, 'game_started')
        self.assertTrue(state['players']['Alice']['connected'])
        hand = self.payload(events, 'your_hand')['hand']
        self.assertEqual(len(hand), 5)
        self.assertTrue(all(isinstance(card['location'], list) for card in hand))
        self.assertNotIn(token, str(second.get_received()))

    def test_full_lobby_waits_for_disconnected_player_then_starts_on_resume(self):
        host, guest = self.client(), self.client()
        joined = self.payload(self.join(host, 'Alice', intent='create'), 'join_success')
        host.disconnect()
        events = self.join(guest, 'Bob', intent='join')
        session = server.games['room']
        self.assertFalse(session.started)
        self.assertNotIn('game_started', [event['name'] for event in events])
        resumed = self.client()
        guest.get_received()
        events = self.join(resumed, 'Alice', intent='rejoin', resume_token=joined['resume_token'])
        self.assertTrue(session.started)
        self.assertTrue(self.payload(events, 'join_success')['started'])
        self.payload(events, 'game_started')
        self.assertEqual(len(self.payload(events, 'your_hand')['hand']), 5)
        peer_events = guest.get_received()
        self.payload(peer_events, 'game_started')
        self.assertEqual(len(self.payload(peer_events, 'your_hand')['hand']), 5)

    def test_invalid_card_requests_do_not_mutate_state(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        before = session.get_game_state()
        for cards in (None, [], [None], [{}], [{'location': [], 'color': 'red'}]):
            self.payload(self.emit(first, 'play_cards', game_id='room', cards=cards), 'error')
            self.assertEqual(session.get_game_state(), before)

    def table(self, count=2, room='room', mode='twenty_dots'):
        clients = [self.client() for _ in range(count)]
        for index, client in enumerate(clients):
            self.join(client, f'P{index}', room, player_count=count, game_mode=mode,
                      intent='create' if index == 0 else 'join')
        return clients, server.games[room]

    def ready(self, client, session, ready=True, round_id=None):
        return self.emit(client, 'rematch_ready', game_id=session.game_id,
                         round_id=session.round_id if round_id is None else round_id, ready=ready)

    def win_round(self, session, name):
        session.game.players[name]['total_dots'] = 20
        return session.get_game_state()

    def assert_card_partition(self, session, originals):
        cards = list(session.game.deck) + list(session.recycle_pool)
        for player in session.game.players.values():
            cards.extend(player['hand'])
        self.assertEqual(len(cards), len(originals))
        self.assertEqual({id(card) for card in cards}, originals)
        self.assertEqual(len({id(card) for card in cards}), len(cards))

    def test_round_schema_and_first_terminal_snapshot_awards_once(self):
        clients, session = self.table()
        expected = {'number': 1, 'round': 1, 'wins': {'P0': 0, 'P1': 0},
                    'target_wins': 2, 'winner': None}
        for state in (session.get_game_state(), session.get_lobby_state()):
            self.assertEqual(state['round_id'], 1)
            self.assertEqual(state['series'], expected)
            self.assertEqual(state['rematch'], {'ready': [], 'next_game_mode': 'twenty_dots'})
        self.assertIsNone(session.get_game_state()['last_move'])
        self.assertEqual(session.get_game_state()['deck_reshuffles'], 0)
        state = self.win_round(session, 'P0')
        self.assertEqual(state['series']['wins'], {'P0': 1, 'P1': 0})
        self.assertEqual(state['winner'], {'winner': 'P0', 'condition': 'twenty_dots'})
        # Every public/read path, including terminal replays, must be idempotent.
        for _ in range(5):
            session.check_winner()
            session.winner_payload()
            session.get_lobby_state()
            session.get_game_state()
            self.emit(clients[0], 'roll_dice', game_id=session.game_id)
        self.assertEqual(session.series_wins, {'P0': 1, 'P1': 0})

    def test_rematch_consensus_reset_private_hands_and_rotation_two_to_four(self):
        for count in (2, 3, 4):
            with self.subTest(count=count):
                clients, session = self.table(count, f'consensus{count}')
                original_game = session.game
                seats = {sid: dict(player) for sid, player in session.players.items()}
                session.game.grid[0][0] = Dot('red')
                session.game.yellow_dot_position = (0, 0)
                session.game.landmines = [{'location': 'C3', 'color': 'blue', 'player': 'P0'}]
                session.game.turn_cards_played['P1'] = 2
                session.game.must_advance_after_roll['P1'] = True
                session.discard_piles['P0'] = [{'location': 'A1', 'color': 'red'}]
                session.recycle_pool = [session.game.deck.pop()]
                session.deck_reshuffles = 3
                session.last_move = {'id': 8}
                self.win_round(session, 'P0')
                events = self.ready(clients[0], session)
                self.assertEqual(self.payload(events, 'rematch_updated')['rematch']['ready'], ['P0'])
                self.ready(clients[0], session, False)
                self.assertEqual(session.ready_players, set())
                self.ready(clients[0], session)
                self.ready(clients[0], session)  # Idempotent, not a second vote.
                for client in clients[1:-1]:
                    self.ready(client, session)
                self.assertEqual(session.round_id, 1)
                for client in clients:
                    client.get_received()
                final_events = self.ready(clients[-1], session)
                self.assertEqual(session.round_id, 2)
                self.assertIsNot(session.game, original_game)
                self.assertEqual(session.players, seats)
                self.assertEqual(session.player_order, [f'P{i}' for i in range(count)])
                self.assertEqual(list(session.game.players), session.player_order)
                self.assertEqual(session.game.get_current_player(), 'P1')
                self.assertEqual(session.game.turn_cards_played, dict.fromkeys(session.player_order, 0))
                self.assertFalse(session.game.must_advance_after_roll)
                self.assertEqual(session.discard_piles, {name: [] for name in session.player_order})
                self.assertFalse(session.recycle_pool)
                self.assertFalse(session.game.landmines)
                self.assertIsNone(session.game.yellow_dot_position)
                self.assertTrue(all(dot is None for row in session.game.grid for dot in row))
                for client, events in [(client, client.get_received()) for client in clients[:-1]] + [
                        (clients[-1], final_events)]:
                    state = self.payload(events, 'game_started')
                    self.assertEqual(state['round_id'], 2)
                    self.assertIsNone(state['winner'])
                    self.assertIsNone(state['last_move'])
                    self.assertEqual(state['deck_reshuffles'], 0)
                    self.assertTrue(state['can_roll_dice'])
                    self.assertEqual(state['rematch']['ready'], [])
                    self.assertTrue(all(p['total_dots'] == p['yellow_dots'] == 0
                                        for p in state['players'].values()))
                    self.assertTrue(all('hand' not in p for p in state['players'].values()))
                    hands = [e for e in events if e['name'] == 'your_hand']
                    self.assertEqual(len(hands), 1)
                    name = f'P{clients.index(client)}'
                    self.assertEqual(hands[0]['args'][0]['hand'], session.get_player_hand(name))
                    self.assertNotIn('resume_token', str(events))

    def test_first_to_two_series_can_exceed_three_rounds_and_new_series_rotates(self):
        for count in (2, 3, 4):
            with self.subTest(count=count):
                clients, session = self.table(count, f'series{count}')
                wins = dict.fromkeys(session.player_order, 0)
                for round_number, name in enumerate(session.player_order + ['P0'], 1):
                    self.assertEqual(session.round_id, round_number)
                    self.assertEqual(session.game.get_current_player(), f'P{(round_number - 1) % count}')
                    wins[name] += 1
                    state = self.win_round(session, name)
                    expected = {'number': 1, 'round': round_number, 'wins': dict(wins),
                                'target_wins': 2, 'winner': 'P0' if wins['P0'] == 2 else None}
                    self.assertEqual(state['series'], expected)
                    self.assertEqual(session.get_lobby_state()['series'], expected)
                    self.assertEqual(session.get_game_state()['series'], expected)
                    for client in clients:
                        self.ready(client, session)
                state = session.get_game_state()
                self.assertEqual(state['round_id'], count + 2)
                self.assertEqual(state['series'], {
                    'number': 2, 'round': 1, 'wins': dict.fromkeys(session.player_order, 0),
                    'target_wins': 2, 'winner': None})
                self.assertEqual(state['current_turn'], 'P1')
                self.assertEqual(self.win_round(session, 'P1')['series']['wins']['P1'], 1)

    def test_rematch_mode_host_only_and_changed_options_clear_human_readiness(self):
        clients, session = self.table(3)
        self.win_round(session, 'P0')
        self.ready(clients[1], session)
        for client, mode in ((clients[1], 'five_colors'), (self.client(), 'five_colors'),
                             (clients[0], 'invalid'), (clients[0], [])):
            events = self.emit(client, 'rematch_options', game_id='room', round_id=1, game_mode=mode)
            self.payload(events, 'error')
            self.assertEqual(session.next_game_mode, 'twenty_dots')
            self.assertEqual(session.ready_players, {'P1'})
        unchanged = self.emit(clients[0], 'rematch_options', game_id='room', round_id=1,
                              game_mode='twenty_dots')
        self.assertEqual(self.payload(unchanged, 'rematch_updated')['rematch']['ready'], ['P1'])
        for mode in ('five_colors', 'five_with_yellow'):
            changed = self.emit(clients[0], 'rematch_options', game_id='room', round_id=1,
                                game_mode=mode)
            state = self.payload(changed, 'rematch_updated')
            self.assertEqual(state['rematch'], {'ready': [], 'next_game_mode': mode})
            self.assertEqual(session.game_mode, 'twenty_dots')
            self.assertEqual(state['series']['wins']['P0'], 1)
            self.ready(clients[1], session)
        self.ready(clients[0], session)
        self.assertEqual(session.round_id, 1)
        self.ready(clients[2], session)
        self.assertEqual(session.game_mode, 'five_with_yellow')
        self.assertEqual(session.get_game_state()['series']['round'], 2)
        winner = session.game.players['P2']
        winner['score'] = dict.fromkeys(session.game.colors, 5)
        winner['yellow_dots'] = 5
        state = session.get_game_state()
        self.assertEqual(state['winner'], {'winner': 'P2', 'condition': 'five_with_yellow'})
        self.assertEqual(state['series']['wins'], {'P0': 1, 'P1': 0, 'P2': 1})

    def test_rematch_ai_auto_ready_and_rotating_ai_start_is_scheduled(self):
        client = self.client()
        events = self.emit(client, 'start_single_player', player_name='Human', num_players=4)
        session = server.games[self.payload(events, 'game_started')['game_id']]
        self.win_round(session, 'AI 2')
        self.assertEqual(session.get_round_state()['rematch']['ready'], ['AI 1', 'AI 2', 'AI 3'])
        changed = self.emit(client, 'rematch_options', game_id=session.game_id, round_id=1,
                            game_mode='five_colors')
        self.assertEqual(self.payload(changed, 'rematch_updated')['rematch']['ready'],
                         ['AI 1', 'AI 2', 'AI 3'])
        events = self.ready(client, session)
        self.assertEqual(self.payload(events, 'game_started')['current_turn'], 'AI 1')
        self.assertEqual(session.series_wins['AI 2'], 1)
        self.schedule.assert_called_once_with(session.execute_ai_move)

    def test_disconnect_or_leave_clears_ready_and_resume_requires_explicit_vote(self):
        for action in ('disconnect', 'leave_game'):
            with self.subTest(action=action):
                clients, session = self.table(3, action)
                host, peer, third = clients
                token = session.players[session.host_sid]['resume_token']
                self.win_round(session, 'P0')
                self.ready(host, session)
                peer.get_received()
                if action == 'disconnect':
                    host.disconnect()
                else:
                    self.emit(host, action, game_id=session.game_id)
                updated = self.payload(peer.get_received(), 'rematch_updated')
                self.assertEqual(updated['rematch']['ready'], [])
                self.ready(peer, session)
                self.ready(third, session)
                self.assertEqual(session.round_id, 1)
                if action == 'leave_game':
                    self.payload(self.ready(host, session), 'error')
                resumed = self.client()
                events = self.join(resumed, 'P0', session.game_id, intent='rejoin', resume_token=token)
                self.assertEqual(self.payload(events, 'game_started')['round_id'], 1)
                self.assertEqual(session.get_player_name(session.host_sid), 'P0')
                self.assertEqual(session.ready_players, {'P1', 'P2'})
                self.assertEqual(session.players[session.host_sid]['resume_token'], token)
                self.ready(resumed, session)
                self.assertEqual(session.round_id, 2)

    def test_rematch_authorization_validation_and_required_round_id(self):
        host = self.client()
        self.join(host, 'Alice')
        for event, options in (('rematch_ready', {'ready': True}),
                               ('rematch_options', {'game_mode': 'five_colors'})):
            self.payload(self.emit(host, event, game_id='room', round_id=1, **options), 'error')
        peer = self.client()
        self.join(peer, 'Bob')
        session = server.games['room']
        for event, options in (('rematch_ready', {'ready': True}),
                               ('rematch_options', {'game_mode': 'five_colors'})):
            self.payload(self.emit(host, event, game_id='room', round_id=1, **options), 'error')
        self.win_round(session, 'Alice')
        self.payload(self.ready(self.client(), session), 'error')
        for value in ('true', 1, None, []):
            self.payload(self.emit(host, 'rematch_ready', game_id='room', round_id=1, ready=value), 'error')
        for event, options in (('rematch_ready', {'ready': True}),
                               ('rematch_options', {'game_mode': 'five_colors'})):
            for extra in ({}, {'round_id': 0}, {'round_id': 2}, {'round_id': True}, {'round_id': '1'}):
                self.payload(self.emit(host, event, game_id='room', **options, **extra), 'error')
        for event in ('rematch_ready', 'rematch_options', 'reaction'):
            for data in (None, [], {'game_id': []}, {'game_id': 'missing'}):
                host.get_received()
                host.emit(event, data)
                self.payload(host.get_received(), 'error')
        self.assertEqual(session.ready_players, set())
        self.assertEqual(session.round_id, 1)

    def test_stale_rematch_and_normal_actions_do_not_mutate_next_round(self):
        clients, session = self.table()
        self.win_round(session, 'P0')
        for client in clients:
            self.ready(client, session)
        before = session.get_game_state()
        for event, options in (
                ('rematch_ready', {'ready': True}),
                ('rematch_options', {'game_mode': 'five_colors'}),
                ('roll_dice', {}), ('play_cards', {'cards': session.get_player_hand('P1')[:1]}),
                ('end_turn', {}), ('pass_turn', {})):
            self.payload(self.emit(clients[1], event, game_id='room', round_id=1, **options), 'error')
            self.assertEqual(session.get_game_state(), before)
        with patch.object(session.game, 'roll_dice', return_value=('F', '6')):
            self.payload(self.emit(clients[1], 'roll_dice', game_id='room', round_id=2), 'game_updated')
        # Legacy normal actions still work without a round ID.
        self.payload(self.emit(clients[1], 'end_turn', game_id='room'), 'game_updated')
        self.assertEqual(session.game.get_current_player(), 'P0')
        # Even when a later round is also terminal, old ready/options packets are invalid.
        before = self.win_round(session, 'P1')
        for event, options in (('rematch_ready', {'ready': True}),
                               ('rematch_options', {'game_mode': 'five_colors'})):
            self.payload(self.emit(clients[0], event, game_id='room', round_id=1, **options), 'error')
            self.assertEqual(session.get_game_state(), before)
        self.ready(clients[0], session)
        self.assertEqual(session.ready_players, {'P0'})

    def test_reaction_whitelist_cooldown_room_isolation_and_reconnect(self):
        clients, session = self.table()
        outsider = self.client()
        other, other_session = self.table(room='other')
        with patch.object(server.time, 'monotonic', return_value=100) as clock:
            for key in ('hello there', '', 'NICE_MOVE', None, [], {'text': 'hi'}):
                self.payload(self.emit(clients[0], 'reaction', game_id='room', reaction=key), 'error')
            self.payload(self.emit(outsider, 'reaction', game_id='room', reaction='nice_move'), 'error')
            for client in clients[1:] + other:
                client.get_received()
            events = self.emit(clients[0], 'reaction', game_id='room', reaction='nice_move', text='not relayed')
            expected = {'game_id': 'room', 'player': 'P0', 'reaction': 'nice_move'}
            self.assertEqual(self.payload(events, 'reaction'), expected)
            self.assertEqual(self.payload(clients[1].get_received(), 'reaction'), expected)
            self.assertTrue(all(not c.get_received() for c in other))
            self.payload(self.emit(clients[1], 'reaction', game_id='room', reaction='well_played'), 'reaction')
            self.payload(self.emit(other[0], 'reaction', game_id=other_session.game_id,
                                   reaction='close_one'), 'reaction')
            clock.return_value = 102.999
            self.payload(self.emit(clients[0], 'reaction', game_id='room', reaction='close_one'), 'error')
            clock.return_value = 103
            self.payload(self.emit(clients[0], 'reaction', game_id='room', reaction='close_one'), 'reaction')
            token = session.players[session.host_sid]['resume_token']
            clients[0].disconnect()
            resumed = self.client()
            self.join(resumed, 'P0', intent='rejoin', resume_token=token)
            self.payload(self.emit(resumed, 'reaction', game_id='room', reaction='rematch'), 'error')
            clock.return_value = 106
            self.win_round(session, 'P0')
            events = self.emit(resumed, 'reaction', game_id='room', reaction='rematch')
            self.assertEqual(self.payload(events, 'reaction')['reaction'], 'rematch')
            self.ready(resumed, session)
            self.ready(clients[1], session)
            self.payload(self.emit(resumed, 'reaction', game_id='room', reaction='nice_move'), 'error')
            self.assertFalse(session.ready_players)

    def test_reactions_reject_lobby_and_disconnected_seats(self):
        host = self.client()
        self.join(host, 'Alice')
        self.payload(self.emit(host, 'reaction', game_id='room', reaction='nice_move'), 'error')
        peer = self.client()
        self.join(peer, 'Bob')
        self.emit(host, 'leave_game', game_id='room')
        self.payload(self.emit(host, 'reaction', game_id='room', reaction='nice_move'), 'error')
        self.assertFalse(server.games['room'].reaction_times)

    def test_real_deck_depletion_across_four_hands_preserves_every_card_identity(self):
        # A stable deck order and no yellow prevent a winner while exercising real scoring.
        with patch.object(server.TwentyDots, 'shuffle_deck'):
            clients, session = self.table(4, mode='five_with_yellow')
        originals = {id(c) for c in session.game.deck}
        for player in session.game.players.values():
            originals.update(id(c) for c in player['hand'])
        self.assertEqual(len(originals), 144)
        session.game.can_roll_dice = False
        played_by = set()
        with patch.object(session.game, 'shuffle_deck') as shuffle:
            for _ in range(140):
                name = session.game.get_current_player()
                hand = session.get_player_hand(name)
                selected = [hand[0], next(c for c in hand[1:] if c['location'] != hand[0]['location'])]
                events = self.emit(clients[int(name[1:])], 'play_cards', game_id='room', cards=selected)
                self.assertNotIn('error', [e['name'] for e in events])
                played_by.add(name)
                self.assert_card_partition(session, originals)
                self.assertTrue(all(len(p['hand']) == 5 for p in session.game.players.values()))
                self.assertEqual(shuffle.call_count, session.deck_reshuffles)
                self.assertIsNone(session.winner)
                if session.deck_reshuffles >= 2:
                    break
        self.assertEqual(played_by, set(session.player_order))
        self.assertEqual(session.deck_reshuffles, 2)
        self.assertTrue(all(session.discard_piles[name] for name in session.player_order))

    def test_refill_waits_for_empty_deck_shuffles_once_and_does_not_touch_board(self):
        clients, session = self.table(4)
        originals = {id(c) for c in session.game.deck}
        for player in session.game.players.values():
            originals.update(id(c) for c in player['hand'])
        session.game.can_roll_dice = False
        cards = list(session.game.players['P0']['hand'][:2])
        session.apply_cards('P0', cards)
        board = session.get_game_state()['board']
        held = {name: list(p['hand']) for name, p in session.game.players.items() if name != 'P0'}
        with patch.object(session.game, 'shuffle_deck') as shuffle:
            self.assertEqual(session.refill_hand('P0'), 2)
            shuffle.assert_not_called()
            self.assertEqual(session.recycle_pool, cards)
            # Move the remaining unplayed deck into hands, never into the recycle pool.
            session.game.players['P1']['hand'].extend(session.game.deck)
            session.game.deck.clear()
            held['P1'] = list(session.game.players['P1']['hand'])
            session.game.players['P2']['hand'].extend(session.game.players['P0']['hand'])
            session.game.players['P0']['hand'].clear()
            held['P2'] = list(session.game.players['P2']['hand'])
            self.assertEqual(session.refill_hand('P0'), 2)
            shuffle.assert_called_once()
            self.assertEqual(session.game.players['P0']['hand'], cards)
            self.assertEqual(session.refill_hand('P0'), 0)
            self.assertEqual(shuffle.call_count, 1)
        self.assertEqual(session.get_game_state()['board'], board)
        for name, hand in held.items():
            self.assertEqual(session.game.players[name]['hand'], hand)
        self.assert_card_partition(session, originals)

    def test_all_empty_hands_recover_on_their_turn_and_receive_private_updates(self):
        clients, session = self.table(4)
        session.game.can_roll_dice = False
        # Model a fully depleted table with four previously played cards available.
        originals = [Card(f'{row}1', color) for row, color in zip('ABCD', session.game.colors)]
        session.game.deck = []
        for player in session.game.players.values():
            player['hand'] = []
        session.recycle_pool = list(originals)
        with patch.object(session.game, 'shuffle_deck') as shuffle:
            for outgoing, incoming in ((0, 1), (1, 2), (2, 3), (3, 0)):
                clients[incoming].get_received()
                self.emit(clients[outgoing], 'pass_turn', game_id='room')
                events = clients[incoming].get_received()
                self.assertEqual(len(self.payload(events, 'your_hand')['hand']), 4)
                self.assertEqual(session.game.get_current_player(), f'P{incoming}')
                session.apply_cards(f'P{incoming}', list(session.game.players[f'P{incoming}']['hand']))
                self.assert_card_partition(session, {id(c) for c in originals})
            self.assertEqual(shuffle.call_count, 4)

    def test_human_end_turn_recycles_a_single_played_card(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        card = Card('A1', 'red')
        session.game.deck = []
        session.game.players['Alice']['hand'] = [card]
        self.emit(first, 'play_cards', game_id='room', cards=session.get_player_hand('Alice'))
        self.assertEqual(session.recycle_pool, [card])
        self.assertEqual(session.deck_reshuffles, 0)
        with patch.object(session.game, 'shuffle_deck') as shuffle:
            self.emit(first, 'end_turn', game_id='room')
            shuffle.assert_called_once()
        self.assertEqual(session.game.players['Alice']['hand'], [card])
        self.assertEqual(session.game.grid[0][0].color, 'red')

    def test_ai_records_and_recycles_played_cards_and_recovers_empty_hand(self):
        for empty in (False, True):
            with self.subTest(empty=empty):
                clients, session = self.table(room=f'ai{empty}')
                session.game.can_roll_dice = False
                cards = [Card('A1', 'red'), Card('C3', 'blue')]
                session.game.deck = []
                session.game.players['P0']['hand'] = [] if empty else list(cards)
                session.recycle_pool = list(cards) if empty else []
                held = list(session.game.players['P1']['hand'])
                session.ai_players['P0'] = server.AIPlayer('medium')
                with patch.object(session.ai_players['P0'], 'choose_cards', return_value=[0, 1]), \
                        patch.object(session.game, 'shuffle_deck') as shuffle, \
                        patch.object(server.time, 'sleep'):
                    session.execute_ai_move()
                self.assertEqual(session.game.get_current_player(), 'P1')
                self.assertEqual(session.game.players['P0']['hand'], cards)
                self.assertEqual(session.game.players['P1']['hand'], held)
                self.assertEqual(shuffle.call_count, 2 if empty else 1)
                self.assertEqual(session.deck_reshuffles, shuffle.call_count)
                self.assertFalse(session.recycle_pool)
                self.assertEqual(session.discard_piles['P0'], [
                    {'location': 'A1', 'color': 'red'}, {'location': 'C3', 'color': 'blue'}])
                state = self.payload(clients[0].get_received(), 'game_updated')
                self.assertEqual(state['last_move'], {
                    'id': 1, 'player': 'P0', 'kind': 'play',
                    'placements': session.discard_piles['P0'], 'collected': [], 'points': 0, 'lines': 0})

    def test_last_move_counts_intersecting_lines_replacements_and_actual_score(self):
        first, second, session = self.started()
        session.game.can_roll_dice = False
        session.game.players['Alice']['hand'] = [Card('B2', 'red')]
        for row, col in ((1, 0), (1, 2), (0, 1), (2, 1)):
            session.game.grid[row][col] = Dot('red')
        session.game.grid[1][1] = Dot('blue')
        events = self.emit(first, 'play_cards', game_id='room', cards=session.get_player_hand('Alice'))
        move = self.payload(events, 'game_updated')['last_move']
        self.assertEqual(move['placements'], [{'location': 'B2', 'color': 'red'}])
        self.assertEqual(move['collected'][0], {'location': 'B2', 'color': 'blue'})
        self.assertEqual({c['location'] for c in move['collected'][1:]}, {'A2', 'B1', 'B2', 'B3', 'C2'})
        self.assertTrue(all(c['color'] == 'red' for c in move['collected'][1:]))
        self.assertEqual(move['points'], 6)
        self.assertEqual(move['lines'], 2)
        self.assertEqual(move['player'], 'Alice')
        self.assertEqual(move['kind'], 'play')
        self.assertEqual(move['id'], 1)
        self.emit(first, 'end_turn', game_id='room')
        self.assertEqual(session.last_move, move)  # Passing is not a fabricated placement.
        self.payload(self.emit(first, 'play_cards', game_id='room', cards=[]), 'error')
        self.assertEqual(session.last_move, move)

    def test_roll_metadata_does_not_claim_unscored_replacement_and_ids_span_rematches(self):
        first, second, session = self.started()
        session.game.grid[0][0] = Dot('blue')
        with patch.object(session.game, 'roll_dice', return_value=('A', '1')):
            self.emit(first, 'roll_dice', game_id='room')
        self.assertEqual(session.last_move, {
            'id': 1, 'player': 'Alice', 'kind': 'roll',
            'placements': [{'location': 'A1', 'color': 'yellow'}],
            'collected': [], 'points': 0, 'lines': 0})
        self.win_round(session, 'Alice')
        self.ready(first, session)
        self.ready(second, session)
        self.assertIsNone(session.last_move)
        session.game.grid[0][0] = Dot('red')
        session.game.grid[0][1] = Dot('red')
        with patch.object(session.game, 'roll_dice', return_value=('A', '3')):
            self.emit(second, 'roll_dice', game_id='room')
        self.assertEqual(session.last_move, {
            'id': 2, 'player': 'Bob', 'kind': 'roll',
            'placements': [{'location': 'A3', 'color': 'yellow'}],
            'collected': [{'location': 'A1', 'color': 'red'}, {'location': 'A2', 'color': 'red'},
                          {'location': 'A3', 'color': 'yellow'}], 'points': 2, 'lines': 1})

    def test_ai_winning_roll_metadata_and_series_are_in_first_terminal_event(self):
        clients, session = self.table()
        session.ai_players['P0'] = server.AIPlayer('medium')
        session.game.players['P0']['total_dots'] = 18
        session.game.grid[0][0] = Dot('red')
        session.game.grid[0][1] = Dot('red')
        clients[0].get_received()
        with patch.object(session.game, 'roll_dice', return_value=('A', '3')):
            session.execute_ai_move()
        events = clients[0].get_received()
        state = self.payload(events, 'game_updated')
        self.assertEqual(state['series']['wins'], {'P0': 1, 'P1': 0})
        self.assertEqual(state['last_move']['kind'], 'roll')
        self.assertEqual(state['last_move']['points'], 2)
        self.assertEqual(state['last_move']['lines'], 1)
        self.assertEqual(len(state['last_move']['collected']), 3)
        self.assertEqual(self.payload(events, 'game_over'), {'winner': 'P0', 'condition': 'twenty_dots'})


if __name__ == '__main__':
    unittest.main()