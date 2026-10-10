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


if __name__ == '__main__':
    unittest.main()