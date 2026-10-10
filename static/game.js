/* Twenty Dots browser client. The server owns all cards, scores and turn changes. */
(() => {
    'use strict';

    const $ = id => document.getElementById(id);
    const COLORS = ['red', 'blue', 'green', 'purple'];
    const SYMBOLS = { red: 'R', blue: 'B', green: 'G', purple: 'P', yellow: '✳' };
    const MODES = {
        twenty_dots: { title: 'The classic', goal: 'First to 20 dots.', short: 'First to 20 dots' },
        five_colors: { title: 'Color collector', goal: 'Five of every color.', short: '5 of each regular color' },
        five_with_yellow: { title: 'Wild ambition', goal: 'Every color. Even wild.', short: '5 of each color + 5 yellow' },
    };
    const SAVE_KEY = 'twenty-dots.seat.v1';
    const NAME_KEY = 'twenty-dots.name';
    const app = {
        mode: 'create', socket: null, seat: null, lobby: null, game: null,
        hand: [], selected: [], joined: false, handReady: false,
        pending: null, pendingTimer: null, connecting: false,
        screen: 'home', winnerShown: null, activity: [],
    };
    let toastTimer;

    function node(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = String(text);
        return element;
    }

    function storageGet(key) {
        try { return localStorage.getItem(key); } catch { return null; }
    }

    function storageSet(key, value) {
        try {
            if (value === null) localStorage.removeItem(key);
            else localStorage.setItem(key, value);
        } catch { /* Private browsing still supports play for this page's lifetime. */ }
    }

    function savedSeat() {
        try {
            const saved = JSON.parse(storageGet(SAVE_KEY));
            if (!saved || typeof saved.game_id !== 'string' || typeof saved.player_name !== 'string'
                || typeof saved.resume_token !== 'string' || !saved.updated
                || Date.now() - saved.updated > 24 * 60 * 60 * 1000) return null;
            return saved;
        } catch { return null; }
    }

    function persistSeat() {
        if (app.seat && !app.game?.winner) {
            storageSet(SAVE_KEY, JSON.stringify({ ...app.seat, updated: Date.now() }));
        }
    }

    function refreshResume() {
        const saved = savedSeat();
        $('resume-card').hidden = !saved;
        if (saved) $('resume-description').textContent = `${saved.player_name} · Room ${saved.game_id}`;
    }

    function toast(message) {
        clearTimeout(toastTimer);
        $('toast').textContent = message;
        $('toast').hidden = false;
        toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4500);
    }

    function showScreen(name) {
        const changed = app.screen !== name;
        app.screen = name;
        for (const screen of ['home', 'lobby', 'game']) $(`${screen}-screen`).hidden = screen !== name;
        if (changed) {
            window.scrollTo({ top: 0, behavior: 'instant' });
            $('main').focus({ preventScroll: true });
        }
    }

    function setMode(mode) {
        if (app.connecting) return;
        app.mode = mode;
        document.querySelectorAll('[data-mode]').forEach(tab => {
            const active = tab.dataset.mode === mode;
            tab.setAttribute('aria-selected', String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        $('setup-form').setAttribute('aria-labelledby', `tab-${mode}`);
        $('join-options').hidden = mode !== 'join';
        $('room-code').required = mode === 'join';
        $('create-options').hidden = mode === 'join';
        $('solo-options').hidden = mode !== 'solo';
        $('start-label').textContent = { create: 'Create a room', join: 'Take your seat', solo: 'Let’s practice' }[mode];
        $('form-footnote').textContent = mode === 'solo'
            ? 'Get to know the board. The computer will keep you company.'
            : 'No account. Just a room code and good company.';
        $('form-error').hidden = true;
    }

    function formBusy(busy) {
        app.connecting = busy;
        $('setup-form').setAttribute('aria-busy', String(busy));
        $('setup-form').querySelectorAll('input, select, button[type="submit"]').forEach(control => { control.disabled = busy; });
        document.querySelectorAll('[data-mode]').forEach(tab => { tab.disabled = busy; });
        $('resume-button').disabled = busy;
        $('cancel-connect').hidden = !busy;
        if (busy) $('start-label').textContent = 'Finding your table…';
        else setMode(app.mode);
    }

    function connectionStatus(status, text) {
        $('connection').dataset.state = status;
        $('connection').lastElementChild.textContent = text;
    }

    function banner(message) {
        $('connection-banner').hidden = !message;
        if (message) $('connection-message').textContent = message;
    }

    function setPending(action) {
        clearTimeout(app.pendingTimer);
        app.pending = action;
        if (action) {
            app.pendingTimer = setTimeout(() => {
                // Never re-send a move after an uncertain response. Resync from the server instead.
                app.pending = null;
                app.handReady = false;
                banner('That took a little too long. Reconnecting to check your last move.');
                reconnect();
            }, 15000);
        }
        renderControls();
    }

    function disposeSocket() {
        if (app.socket) {
            app.socket.removeAllListeners();
            app.socket.disconnect();
            app.socket = null;
        }
        app.joined = false;
    }

    function serverURL() {
        const url = new URL(window.location.origin);
        // Support the repository's optional separate static server for local development.
        if (url.port === '8000') url.port = '5000';
        return url.origin;
    }

    function connect(request, eventName = 'join_game') {
        if (typeof window.io !== 'function') {
            formBusy(false);
            $('form-error').textContent = 'The connection library couldn’t load. Check your connection and reload this page.';
            $('form-error').hidden = false;
            return;
        }
        disposeSocket();
        app.handReady = false;
        connectionStatus('connecting', 'Connecting');
        const socket = window.io(serverURL(), {
            autoConnect: false, reconnection: true, reconnectionDelay: 800,
            reconnectionDelayMax: 4000, timeout: 20000,
        });
        app.socket = socket;
        socket.on('connect', () => {
            connectionStatus('connecting', 'Taking a seat');
            const resume = app.seat;
            socket.emit(resume ? 'join_game' : eventName,
                resume ? { ...resume, intent: 'rejoin' } : request);
        });
        socket.on('connect_error', () => {
            connectionStatus('connecting', 'Trying again');
            banner(app.seat ? 'Connection interrupted. Reconnecting to your saved seat.'
                : 'The table is waking up. This can take a minute. We’ll keep trying.');
        });
        socket.on('disconnect', () => {
            app.joined = false;
            app.handReady = false;
            clearTimeout(app.pendingTimer);
            app.pending = null;
            connectionStatus('connecting', 'Reconnecting');
            banner('Connection interrupted. Your seat is saved; moves are paused on this device.');
            renderHand();
            renderControls();
        });
        socket.on('join_success', data => {
            app.seat = {
                game_id: data.game_id, player_name: data.player_name,
                resume_token: data.resume_token,
            };
            app.joined = true;
            app.lobby = data;
            persistSeat();
            formBusy(false);
            banner(null);
            connectionStatus('connected', 'Connected');
            renderLobby();
            if (!data.started) showScreen('lobby');
        });
        socket.on('lobby_updated', data => {
            if (!app.seat || data.game_id !== app.seat.game_id) return;
            const previous = app.lobby;
            app.lobby = data;
            if (app.game) {
                for (const player of data.players) {
                    if (app.game.players[player.name]) app.game.players[player.name].connected = player.connected;
                    const old = previous?.players?.find(p => p.name === player.name);
                    if (old && old.connected !== player.connected) {
                        log(`${player.name} ${player.connected ? 'is back at the table.' : 'lost connection. Their seat is saved.'}`);
                    }
                }
                renderScores();
                renderControls();
            } else renderLobby();
        });
        socket.on('game_started', data => {
            app.handReady = false;
            app.selected = [];
            receiveState(data);
            showScreen('game');
        });
        socket.on('game_updated', receiveState);
        socket.on('your_hand', data => {
            if (!app.seat) return;
            app.hand = (data.hand || []).filter(card => COLORS.includes(card.color) && /^[A-F][1-6]$/.test(locationOf(card)));
            app.handReady = true;
            app.selected = [];
            setPending(null);
            renderHand();
            renderBoard();
            renderControls();
        });
        socket.on('game_over', data => {
            if (!app.game) return;
            app.game.winner = data;
            setPending(null);
            renderControls();
            showWinner(data);
        });
        socket.on('error', data => {
            const message = data?.message || 'That move couldn’t be completed. Please try again.';
            setPending(null);
            if (!app.joined) {
                disposeSocket();
                formBusy(false);
                banner(null);
                connectionStatus('offline', 'Not connected');
                if (message === 'Game not found' || message === 'Player not found') {
                    storageSet(SAVE_KEY, null);
                }
                if (app.screen === 'home') {
                    app.seat = null;
                    $('form-error').textContent = message;
                    $('form-error').hidden = false;
                    refreshResume();
                } else banner(`${message}. Leave this table to create or join another room.`);
            } else toast(message);
            renderHand();
            renderControls();
        });
        renderHand();
        renderControls();
        socket.connect();
    }

    function reconnect() {
        if (app.seat) connect({ ...app.seat, intent: 'rejoin' });
        else if (app.socket) app.socket.connect();
        else toast('Choose a room to get connected.');
    }

    function makeRoomCode() {
        const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        const bytes = new Uint8Array(6);
        crypto.getRandomValues(bytes);
        return Array.from(bytes, n => alphabet[n % alphabet.length]).join('');
    }

    function submitSetup(event) {
        event.preventDefault();
        if (app.connecting) return;
        const name = $('player-name').value.trim();
        const room = $('room-code').value.trim();
        if (!name || (app.mode === 'join' && !room)) {
            $('form-error').textContent = !name ? 'Add your name to take a seat.' : 'Enter your friend’s room code.';
            $('form-error').hidden = false;
            return;
        }
        storageSet(NAME_KEY, name);
        const count = Number(document.querySelector('input[name="player_count"]:checked').value);
        const request = {
            player_name: name, player_count: count,
            game_mode: $('game-mode').value, intent: app.mode === 'join' ? 'join' : 'create',
        };
        app.seat = null;
        app.game = null;
        app.lobby = null;
        app.hand = [];
        app.activity = [];
        app.winnerShown = null;
        $('form-error').hidden = true;
        formBusy(true);
        if (app.mode === 'solo') {
            connect({ ...request, num_players: count, difficulty: $('difficulty').value }, 'start_single_player');
        } else {
            request.game_id = app.mode === 'join' ? room : makeRoomCode();
            connect(request);
        }
    }

    function renderLobby() {
        if (!app.lobby || !app.seat) return;
        const lobby = app.lobby;
        const mode = MODES[lobby.game_mode] || MODES.twenty_dots;
        $('lobby-code').textContent = lobby.game_id;
        $('lobby-goal').textContent = mode.short;
        $('lobby-count').textContent = `${lobby.required_players} players · Private room`;
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < lobby.required_players; i++) {
            const player = lobby.players[i];
            const seat = node('div', `seat${player ? '' : ' seat-empty'}`);
            const avatar = node('span', 'avatar', player ? initials(player.name) : '+');
            avatar.dataset.index = String(i);
            avatar.setAttribute('aria-hidden', 'true');
            const content = node('div');
            content.append(node('strong', '', player ? `${player.name}${player.name === app.seat.player_name ? ' (you)' : ''}` : 'A seat for a friend'));
            content.append(node('small', '', player ? (!player.connected ? 'Reconnecting…' : player.is_host ? 'Host · Ready to play' : 'Ready to play') : 'Send them an invite'));
            seat.append(avatar, content);
            fragment.append(seat);
        }
        $('lobby-seats').replaceChildren(fragment);
        const missing = lobby.required_players - lobby.players.length;
        const offline = lobby.players.filter(p => !p.connected).length;
        $('lobby-status').textContent = missing
            ? `Waiting for ${missing} more ${missing === 1 ? 'friend' : 'friends'} · ${lobby.players.length}/${lobby.required_players} seats taken`
            : offline ? 'Waiting for everyone to reconnect.' : 'Everyone’s here. Let’s play!';
    }

    function initials(name) {
        return Array.from(name.trim()).slice(0, 2).join('').toUpperCase();
    }

    function locationOf(card) {
        return Array.isArray(card.location) ? card.location.join('') : String(card.location || '');
    }

    function coloredDot(color) {
        const dot = node('i', `dot ${Object.hasOwn(SYMBOLS, color) ? color : ''}`, SYMBOLS[color] || '');
        dot.setAttribute('aria-hidden', 'true');
        return dot;
    }

    function myTurn() {
        return app.game && app.seat && app.game.current_turn === app.seat.player_name && !app.game.winner;
    }

    function canSelect() {
        return Boolean(app.joined && app.socket?.connected && app.handReady && app.game && !app.game.winner && !app.pending);
    }

    function receiveState(state) {
        if (!app.seat || state.game_id !== app.seat.game_id) return;
        const previous = app.game;
        if (!previous) log('The table is ready. Let the good moves begin.');
        if (previous) {
            for (const [name, player] of Object.entries(state.players)) {
                const difference = player.total_dots - (previous.players[name]?.total_dots || 0);
                if (difference > 0) log(`${name} collected ${difference} ${difference === 1 ? 'dot' : 'dots'}.`);
            }
            if (state.yellow_dot_position && JSON.stringify(state.yellow_dot_position) !== JSON.stringify(previous.yellow_dot_position)) {
                log(`Wild dot landed on ${state.yellow_dot_position.join('')}.`);
            }
        }
        if (!previous || previous.current_turn !== state.current_turn) {
            log(`${state.current_turn === app.seat.player_name ? 'Your' : `${state.current_turn}’s`} turn.`);
            app.selected = [];
        }
        app.game = state;
        // A pass does not change the hand. Other actions unlock on the private hand event.
        if (app.pending === 'pass_turn' || state.winner) setPending(null);
        const mode = MODES[state.game_mode] || MODES.twenty_dots;
        $('game-title').textContent = mode.title.toUpperCase();
        $('game-goal').textContent = mode.goal;
        $('game-room-code').textContent = app.seat.game_id;
        $('deck-count').textContent = `${state.deck_size} in deck`;
        renderScores();
        renderBoard(previous?.board);
        renderHand();
        renderControls();
        persistSeat();
        if (state.winner) showWinner(state.winner);
    }

    function renderScores() {
        if (!app.game) return;
        const entries = Object.entries(app.game.players);
        $('player-total').textContent = `${entries.length} players`;
        $('score-list').dataset.count = String(entries.length);
        const fragment = document.createDocumentFragment();
        entries.forEach(([name, player], index) => {
            const active = name === app.game.current_turn && !app.game.winner;
            const scoreCard = node('div', `score-card${active ? ' active' : ''}${player.connected ? '' : ' disconnected'}`);
            const person = node('div', 'score-person');
            const avatar = node('span', 'avatar', initials(name));
            avatar.dataset.index = String(index);
            avatar.setAttribute('aria-hidden', 'true');
            const label = node('div');
            label.append(node('strong', '', name === app.seat.player_name ? `${name} (you)` : name));
            label.append(node('small', '', !player.connected ? 'Reconnecting' : active ? 'Making a move' : `${player.hand_size} cards in hand`));
            person.append(avatar, label);
            const main = node('div', 'score-main');
            main.append(node('b', '', player.total_dots), node('span', '', 'dots'));
            const progress = node('div', 'score-progress');
            const progressBar = node('i');
            let fraction = player.total_dots / 20;
            if (app.game.game_mode !== 'twenty_dots') {
                let total = COLORS.reduce((sum, color) => sum + Math.min(5, player.score[color] || 0), 0);
                if (app.game.game_mode === 'five_with_yellow') total += Math.min(5, player.yellow_dots || 0);
                fraction = total / (app.game.game_mode === 'five_with_yellow' ? 25 : 20);
            }
            progressBar.style.width = `${Math.min(100, Math.max(0, fraction * 100))}%`;
            progress.setAttribute('role', 'progressbar');
            progress.setAttribute('aria-label', `${name}’s progress toward the goal`);
            progress.setAttribute('aria-valuemin', '0');
            progress.setAttribute('aria-valuemax', '100');
            progress.setAttribute('aria-valuenow', String(Math.min(100, Math.max(0, Math.round(fraction * 100)))));
            progress.append(progressBar);
            const colors = node('div', 'color-scores');
            [...COLORS, 'yellow'].forEach(color => {
                const value = color === 'yellow' ? player.yellow_dots : player.score[color];
                const count = node('span', 'color-score');
                count.setAttribute('aria-label', `${color}: ${value || 0}`);
                count.append(coloredDot(color), node('span', '', value || 0));
                colors.append(count);
            });
            scoreCard.append(person, main, progress, colors);
            fragment.append(scoreCard);
        });
        $('score-list').replaceChildren(fragment);
    }

    function renderBoard(previousBoard) {
        if (!app.game) return;
        // Keep the 36 interactive cells stable, including keyboard focus, between updates.
        if (!$('board').children.length) {
            $('board').append(node('span', 'board-label'));
            for (let column = 1; column <= 6; column++) $('board').append(node('span', 'board-label', column));
            for (let row = 0; row < 6; row++) {
                const letter = String.fromCharCode(65 + row);
                $('board').append(node('span', 'board-label', letter));
                for (let column = 0; column < 6; column++) {
                    const cell = node('button', 'cell');
                    cell.type = 'button';
                    cell.id = `cell-${letter}${column + 1}`;
                    cell.dataset.row = String(row);
                    cell.dataset.column = String(column);
                    cell.addEventListener('click', () => selectAt(`${letter}${column + 1}`));
                    cell.addEventListener('keydown', boardKeyboard);
                    $('board').append(cell);
                }
            }
        }
        for (let row = 0; row < 6; row++) {
            for (let column = 0; column < 6; column++) {
                const location = `${String.fromCharCode(65 + row)}${column + 1}`;
                const cell = $(`cell-${location}`);
                const color = app.game.board[row]?.[column]?.color;
                const selectedIndex = app.selected.findIndex(index => locationOf(app.hand[index]) === location);
                const previewCard = selectedIndex >= 0 ? app.hand[app.selected[selectedIndex]] : null;
                cell.classList.toggle('preview', Boolean(previewCard));
                cell.classList.toggle('changed', Boolean(previousBoard && previousBoard[row]?.[column]?.color !== color));
                const content = [node('span', 'cell-coordinate', location)];
                if (previewCard || color) content.push(coloredDot(previewCard ? previewCard.color : color));
                if (previewCard) content.push(node('span', 'selection-number', selectedIndex + 1));
                cell.replaceChildren(...content);
                cell.setAttribute('aria-label', `${location}: ${color || 'empty'}${previewCard ? `; preview ${previewCard.color}, card ${selectedIndex + 1}` : ''}`);
                cell.setAttribute('aria-pressed', String(Boolean(previewCard)));
            }
        }
        $('board-hint').textContent = app.selected.length ? 'Outlined dots preview your selected cards.' : 'Tap a card to preview its position.';
    }

    function boardKeyboard(event) {
        const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
        if (!moves[event.key]) return;
        event.preventDefault();
        const row = Math.min(5, Math.max(0, Number(event.currentTarget.dataset.row) + moves[event.key][0]));
        const column = Math.min(5, Math.max(0, Number(event.currentTarget.dataset.column) + moves[event.key][1]));
        $(`cell-${String.fromCharCode(65 + row)}${column + 1}`).focus();
    }

    function renderHand() {
        $('hand-count').textContent = `${app.hand.length} cards`;
        const focusIndex = document.activeElement?.dataset.cardIndex;
        const fragment = document.createDocumentFragment();
        app.hand.forEach((card, index) => {
            const selected = app.selected.includes(index);
            const button = node('button', `playing-card${selected ? ' selected' : ''}`);
            button.type = 'button';
            button.dataset.cardIndex = String(index);
            button.disabled = !canSelect();
            button.setAttribute('aria-pressed', String(selected));
            button.setAttribute('aria-label', `${card.color}, ${locationOf(card)}${selected ? ', selected' : ''}`);
            button.append(node('span', 'card-coordinate', locationOf(card)), coloredDot(card.color), node('span', 'card-color', card.color.toUpperCase()));
            if (selected) button.append(node('span', 'card-check', '✓'));
            button.addEventListener('click', () => toggleCard(index));
            fragment.append(button);
        });
        if (!app.hand.length) fragment.append(node('div', 'hand-empty', app.handReady ? 'No cards left. You can pass your turn.' : 'Dealing your next possibilities…'));
        $('hand').replaceChildren(fragment);
        if (focusIndex !== undefined) $('hand').querySelector(`[data-card-index="${focusIndex}"]`)?.focus({ preventScroll: true });
    }

    function toggleCard(index) {
        if (!canSelect()) return;
        if (app.selected.includes(index)) app.selected = app.selected.filter(i => i !== index);
        else {
            const max = myTurn() ? Math.max(0, 2 - app.game.cards_played_this_turn) : 2;
            if (app.selected.length >= max) {
                toast(max ? `Choose up to ${max} ${max === 1 ? 'card' : 'cards'}. Clear a selection to choose another.` : 'Your cards are played. Roll the wild dice to finish your turn.');
                return;
            }
            if (app.selected.some(i => locationOf(app.hand[i]) === locationOf(app.hand[index]))) {
                toast('Choose two different positions when playing cards together.');
                return;
            }
            app.selected.push(index);
        }
        renderHand();
        renderBoard();
        renderControls();
    }

    function selectAt(location) {
        if (!canSelect()) return;
        const selected = app.selected.find(index => locationOf(app.hand[index]) === location);
        if (selected !== undefined) return toggleCard(selected);
        const indices = app.hand.map((card, index) => locationOf(card) === location ? index : -1).filter(index => index >= 0);
        if (indices.length === 1) toggleCard(indices[0]);
        else if (indices.length > 1) toast(`${location} has more than one color in your hand. Tap the card you want.`);
        else toast(`${location} · ${app.game.board[location.charCodeAt(0) - 65][Number(location[1]) - 1]?.color || 'empty'}. No card for this spot in your hand.`);
    }

    function renderControls() {
        if (!app.game || !app.seat) return;
        const state = app.game;
        const mine = myTurn();
        const available = Boolean(app.joined && app.socket?.connected && app.handReady && !app.pending && !state.winner);
        const remaining = Math.max(0, 2 - state.cards_played_this_turn);
        const selected = app.selected.length;
        $('turn-banner').classList.toggle('is-mine', Boolean(mine));
        $('clear-selection').disabled = selected === 0 || Boolean(app.pending);
        $('end-turn').disabled = !available || !mine || state.can_roll_dice;
        $('end-turn').textContent = state.cards_played_this_turn > 0 && mine ? 'End turn' : 'Pass turn';
        $('primary-action').disabled = !available || !mine || (!state.can_roll_dice && !selected);
        let title, subtitle, action, note;
        if (state.winner) {
            title = `${state.winner.winner} wins. Well played!`;
            subtitle = 'A table full of good moves. Ready for another round?';
            action = 'View results';
            note = 'The final board. A good game deserves another.';
            $('primary-action').disabled = false;
        } else if (!app.joined || !app.socket?.connected) {
            title = 'Getting you back to the table'; subtitle = 'Your moves are paused while we reconnect.';
            action = 'Reconnecting…'; note = 'Your hand stays private. Your seat stays yours.';
        } else if (!app.handReady) {
            title = 'Getting your cards ready'; subtitle = 'Just a moment. We’re syncing with the table.';
            action = 'Dealing…'; note = 'Only you can see these cards.';
        } else if (app.pending) {
            title = app.pending === 'roll_dice' ? 'A little luck is on its way…' : 'Making your move…';
            subtitle = 'Waiting for the table to catch up.'; action = 'One moment…'; note = 'Your move is on its way.';
        } else if (mine) {
            title = state.can_roll_dice ? 'Your turn. Let it roll.' : 'Your turn. Make it count.';
            subtitle = state.can_roll_dice ? 'Roll the wild dice to find yellow’s next spot.'
                : `Play up to ${remaining} ${remaining === 1 ? 'more card' : 'cards'}. Look for a line of three.`;
            action = state.can_roll_dice ? 'Roll the wild dice  ⚄' : selected ? `Play ${selected} ${selected === 1 ? 'card' : 'cards'}  ↗` : 'Choose your cards';
            note = state.can_roll_dice ? 'Yellow matches every color.' : selected ? 'Check the preview, then make your move.' : 'Tap a card or a matching board position to select it.';
        } else {
            const connected = state.players[state.current_turn]?.connected;
            title = connected ? `${state.current_turn}’s turn` : `Waiting for ${state.current_turn}`;
            subtitle = connected ? 'Look over your hand. Your next move is coming.' : 'They’re reconnecting. Their seat is saved.';
            action = 'Waiting for your turn'; note = selected ? 'Just a preview. Choose again when your turn begins.' : 'Your hand stays visible. Plan a little something.';
        }
        $('turn-title').textContent = title;
        $('turn-subtitle').textContent = subtitle;
        $('primary-action').textContent = action;
        $('action-note').textContent = note;
        $('turn-badge').textContent = state.winner ? 'FINISHED' : mine ? 'YOUR TURN' : 'LIVE';
        document.title = `${state.winner ? 'Well played' : mine ? 'Your turn' : `${state.current_turn}’s turn`} — Twenty Dots`;
    }

    function sendAction(event, data = {}) {
        if (!app.joined || !app.socket?.connected || !app.handReady || app.pending || !myTurn()) return;
        setPending(event);
        renderHand();
        app.socket.emit(event, { game_id: app.seat.game_id, ...data });
    }

    function primaryAction() {
        if (app.game?.winner) return $('winner-dialog').showModal();
        if (!myTurn()) return;
        if (app.game.can_roll_dice) sendAction('roll_dice');
        else if (app.selected.length) sendAction('play_cards', { cards: app.selected.map(index => app.hand[index]) });
    }

    function log(message) {
        app.activity.unshift(message);
        app.activity = app.activity.slice(0, 12);
        $('activity-list').replaceChildren(...app.activity.map(item => node('li', '', item)));
    }

    function showWinner(result) {
        if (app.winnerShown === app.seat.game_id) return;
        app.winnerShown = app.seat.game_id;
        storageSet(SAVE_KEY, null);
        $('winner-title').textContent = result.winner === app.seat.player_name ? 'A win well earned.' : `${result.winner} takes the win.`;
        $('winner-description').textContent = `${MODES[result.condition]?.short || 'The goal is reached'}. Good company, great game.`;
        const entries = Object.entries(app.game.players).sort((a, b) => {
            if (a[0] === result.winner) return -1;
            if (b[0] === result.winner) return 1;
            return b[1].total_dots - a[1].total_dots;
        });
        $('final-scores').replaceChildren(...entries.map(([name, player], index) => {
            const row = node('div', 'final-score');
            row.append(node('span', '', `${index === 0 ? '✳ ' : ''}${name}`), node('strong', '', `${player.total_dots} dots`));
            return row;
        }));
        for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
        $('winner-dialog').showModal();
        renderHand();
    }

    function inviteURL() {
        const url = new URL(window.location.href);
        url.search = '';
        url.hash = '';
        url.searchParams.set('room', app.seat.game_id);
        return url.toString();
    }

    async function shareRoom() {
        if (!app.seat) return;
        const url = inviteURL();
        if (navigator.share) {
            try {
                await navigator.share({ title: 'Your seat at Twenty Dots', text: `A little friendly competition? Join my room: ${app.seat.game_id}`, url });
                return;
            } catch (error) { if (error.name === 'AbortError') return; }
        }
        try {
            await navigator.clipboard.writeText(url);
            toast('Invite link copied. Send it to your friends.');
        } catch {
            $('invite-url').value = url;
            $('share-dialog').showModal();
            $('invite-url').select();
        }
    }

    function requestLeave(event) {
        event?.preventDefault();
        if (!app.seat) return;
        $('leave-message').textContent = app.game && !app.game.winner
            ? 'Your seat will be saved on this device. The table waits on your turn, so come back soon.'
            : 'You can always start another game or join your friends again.';
        $('leave-dialog').showModal();
    }

    function goHome() {
        if (app.seat && app.socket?.connected && app.joined) app.socket.emit('leave_game', { game_id: app.seat.game_id });
        if (!app.game || app.game.winner) storageSet(SAVE_KEY, null);
        else persistSeat();
        disposeSocket();
        clearTimeout(app.pendingTimer);
        Object.assign(app, { seat: null, lobby: null, game: null, hand: [], selected: [], pending: null, handReady: false, winnerShown: null, activity: [] });
        for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
        $('board').replaceChildren();
        formBusy(false);
        refreshResume();
        banner(null);
        connectionStatus('offline', 'Let’s play');
        document.title = 'Twenty Dots — Make your move.';
        const url = new URL(window.location.href);
        url.search = '';
        history.replaceState(null, '', url);
        showScreen('home');
    }

    document.querySelectorAll('[data-mode]').forEach(tab => {
        tab.addEventListener('click', () => setMode(tab.dataset.mode));
        tab.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const modes = ['create', 'join', 'solo'];
            let index = modes.indexOf(app.mode);
            index = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (index + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
            setMode(modes[index]);
            $(`tab-${modes[index]}`).focus();
        });
    });
    $('setup-form').addEventListener('submit', submitSetup);
    $('primary-action').addEventListener('click', primaryAction);
    $('end-turn').addEventListener('click', () => sendAction(app.game.cards_played_this_turn ? 'end_turn' : 'pass_turn'));
    $('clear-selection').addEventListener('click', () => { app.selected = []; renderHand(); renderBoard(); renderControls(); });
    $('rules-button').addEventListener('click', () => $('rules-dialog').showModal());
    $('table-rules').addEventListener('click', () => $('rules-dialog').showModal());
    document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => $(button.dataset.close).close()));
    document.querySelectorAll('.leave-button').forEach(button => button.addEventListener('click', requestLeave));
    $('brand-link').addEventListener('click', event => { if (app.seat) requestLeave(event); });
    $('confirm-leave').addEventListener('click', goHome);
    $('new-game').addEventListener('click', () => {
        const previous = app.game;
        goHome();
        setMode('create');
        if (previous) {
            $('game-mode').value = previous.game_mode;
            const count = document.querySelector(`input[name="player_count"][value="${previous.required_players}"]`);
            if (count) count.checked = true;
        }
    });
    $('share-lobby').addEventListener('click', shareRoom);
    $('share-game').addEventListener('click', shareRoom);
    $('copy-code').addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(app.seat.game_id); toast('Room code copied.'); }
        catch { $('invite-url').value = app.seat.game_id; $('share-dialog').showModal(); $('invite-url').select(); }
    });
    $('retry-button').addEventListener('click', reconnect);
    $('cancel-connect').addEventListener('click', () => { disposeSocket(); formBusy(false); banner(null); connectionStatus('offline', 'Let’s play'); });
    $('resume-button').addEventListener('click', () => {
        const saved = savedSeat();
        if (!saved) return refreshResume();
        app.seat = saved;
        $('player-name').value = saved.player_name;
        formBusy(true);
        connect({ ...saved, intent: 'rejoin' });
    });
    window.addEventListener('online', () => { if (app.seat && !app.socket?.connected) reconnect(); });
    window.addEventListener('offline', () => {
        if (app.seat || app.connecting) banner('You’re offline. We’ll reconnect when your connection returns.');
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && app.seat && !app.socket?.connected) reconnect();
    });

    const demo = { 2: 'yellow', 7: 'blue', 9: 'purple', 13: 'green', 14: 'red', 15: 'red', 16: 'red', 21: 'purple', 25: 'blue', 28: 'green', 32: 'purple' };
    for (let i = 0; i < 36; i++) {
        const cell = node('span', 'demo-cell');
        if (demo[i]) cell.append(coloredDot(demo[i]));
        $('demo-board').append(cell);
    }
    $('player-name').value = storageGet(NAME_KEY) || '';
    refreshResume();
    const params = new URLSearchParams(window.location.search);
    const invite = params.get('room') || params.get('game_id') || params.get('game');
    if (invite) {
        setMode('join');
        $('room-code').value = invite.slice(0, 64);
    }
})();