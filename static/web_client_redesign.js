(() => {
    const storageKeys = {
        currentGame: 'currentGame',
        stats: 'playerStats'
    };

    const rows = ['A', 'B', 'C', 'D', 'E', 'F'];
    const cols = ['1', '2', '3', '4', '5', '6'];
    const musicPlaylist = [
        '/static/music/track1.mp3',
        '/static/music/track2.mp3',
        '/static/music/track3.mp3'
    ];
    const powerIcons = {
        swap: '↔',
        remove: '✦',
        wild_place: '★',
        block: '⛔',
        card_swap: '⇄',
        landmine: '✹'
    };

    const state = {
        socket: null,
        socketHandlersBound: false,
        gameId: '',
        playerName: '',
        myHand: [],
        selectedCards: [],
        currentGameState: null,
        lobbyState: null,
        musicPlaying: false,
        currentTrackIndex: 0,
        swapMode: false,
        swapPositions: [],
        landmineMode: false,
        wildPlaceMode: false,
        blockMode: false,
        cardSwapMode: false,
        cardSwapStep: 'none',
        cardSwapOwnCards: [],
        cardSwapOpponent: null,
        cardSwapOpponentCards: [],
        connectionLabel: 'Offline'
    };

    const ui = {};

    window.addEventListener('load', bootstrap);

    function bootstrap() {
        document.title = 'Twenty Dots | Redesign';
        document.body.className = 'redesign-body';
        document.body.innerHTML = appTemplate();
        bindUi();
        restoreJoinState();
        bindAudio();
        showScreen('mode');
        showNotification('Redesigned client loaded. Create a room or rejoin an existing match.', 'info');
    }

    function appTemplate() {
        return `
            <div id="redesignApp">
                <section id="rdModeScreen" class="screen active">
                    <div class="hero-shell">
                        <div class="hero-panel">
                            <span class="eyebrow">Board Game Redesign</span>
                            <h1 class="brand-mark">Twenty Dots</h1>
                            <p class="hero-copy">A full web overhaul for clean 2 to 4 player sessions: better lobby flow, clearer turns, stronger board focus, and a responsive table layout that stays readable on desktop and mobile.</p>
                            <div class="feature-list">
                                <div class="metric-card">
                                    <h3>Seats That Scale</h3>
                                    <p class="muted">Dedicated lobby and in-game seating for 2, 3, or 4 players without duplicate layouts.</p>
                                </div>
                                <div class="metric-card">
                                    <h3>Cleaner Turn Flow</h3>
                                    <p class="muted">The active player, wild roll requirement, and power-card mode are always visible.</p>
                                </div>
                                <div class="metric-card">
                                    <h3>Board-First Play</h3>
                                    <p class="muted">The grid stays centered, readable, and touch-friendly even in 4-player matches.</p>
                                </div>
                                <div class="metric-card">
                                    <h3>Room Control</h3>
                                    <p class="muted">Shareable room links, reconnection support, and waiting-room visibility before the match starts.</p>
                                </div>
                            </div>
                        </div>
                        <div class="hero-panel">
                            <div class="mode-grid">
                                <button type="button" class="mode-tile" id="rdOpenMultiplayer">
                                    <div class="icon">⌘</div>
                                    <h3>Online Room</h3>
                                    <p>Host or join a live room, choose 2, 3, or 4 seats, then let the server auto-start once the table is full.</p>
                                </button>
                                <button type="button" class="mode-tile" id="rdOpenSolo">
                                    <div class="icon">◈</div>
                                    <h3>Solo Table</h3>
                                    <p>Launch a local web session against AI opponents with the same redesigned in-game layout.</p>
                                </button>
                            </div>
                            <div class="panel" style="margin-top: 18px;">
                                <h2 class="section-title">What Changed</h2>
                                <div class="meta-list">
                                    <div class="notice">The room now stays in a proper lobby until the configured player count is reached.</div>
                                    <div class="notice">Player info, discards, landmines, and objectives are condensed into clearer match panels.</div>
                                    <div class="notice">The action area no longer disappears between turns, which makes 3- and 4-player games easier to follow.</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section id="rdJoinScreen" class="screen">
                    <div class="join-shell">
                        <div class="form-panel">
                            <div class="header-row">
                                <div>
                                    <span class="eyebrow">Online Room</span>
                                    <h2>Create or Join</h2>
                                    <p class="muted">The first player defines seats and rules. Everyone else joins using the same room code.</p>
                                </div>
                                <button type="button" class="rd-btn-ghost" id="rdBackToMode">Back</button>
                            </div>
                            <div class="form-grid">
                                <div class="form-field full">
                                    <label for="rdGameId">Game ID</label>
                                    <div class="inline-row">
                                        <input id="rdGameId" type="text" placeholder="for example: friday-night" autocomplete="off" autocapitalize="off" spellcheck="false">
                                        <button type="button" class="rd-btn-secondary" id="rdShareRoomBtn" disabled>Share</button>
                                    </div>
                                </div>
                                <div class="form-field">
                                    <label for="rdPlayerName">Your Name</label>
                                    <input id="rdPlayerName" type="text" placeholder="Player name" autocomplete="name">
                                </div>
                                <div class="form-field">
                                    <label for="rdPlayerCount">Seats</label>
                                    <select id="rdPlayerCount">
                                        <option value="2">2 players</option>
                                        <option value="3">3 players</option>
                                        <option value="4">4 players</option>
                                    </select>
                                </div>
                                <div class="form-field">
                                    <label for="rdWinCondition">Win Condition</label>
                                    <select id="rdWinCondition">
                                        <option value="twenty_dots">First to 20 total dots</option>
                                        <option value="five_colors">First to 5 of each color</option>
                                        <option value="five_with_yellow">First to 5 of each color plus 5 yellow</option>
                                    </select>
                                </div>
                                <div class="form-field">
                                    <label for="rdPowerCards">Power Cards</label>
                                    <select id="rdPowerCards">
                                        <option value="on">Enabled</option>
                                        <option value="off">Disabled</option>
                                    </select>
                                </div>
                            </div>
                            <div class="actions-row" style="margin-top: 18px;">
                                <button type="button" class="rd-btn" id="rdJoinRoomBtn">Join Room</button>
                                <button type="button" class="rd-btn-ghost hidden" id="rdRejoinBtn">Rejoin Last Room</button>
                            </div>
                            <div id="rdJoinError" class="error-box hidden" style="margin-top: 18px;"></div>
                        </div>
                    </div>
                </section>

                <section id="rdSoloScreen" class="screen">
                    <div class="join-shell">
                        <div class="form-panel">
                            <div class="header-row">
                                <div>
                                    <span class="eyebrow">Solo Table</span>
                                    <h2>Start a Match</h2>
                                    <p class="muted">Choose total players, AI difficulty, and the same rules you use online.</p>
                                </div>
                                <button type="button" class="rd-btn-ghost" id="rdBackFromSolo">Back</button>
                            </div>
                            <div class="form-grid">
                                <div class="form-field">
                                    <label for="rdSoloName">Your Name</label>
                                    <input id="rdSoloName" type="text" placeholder="Player name" autocomplete="name">
                                </div>
                                <div class="form-field">
                                    <label for="rdSoloPlayers">Total Players</label>
                                    <select id="rdSoloPlayers">
                                        <option value="2">2 players</option>
                                        <option value="3">3 players</option>
                                        <option value="4">4 players</option>
                                    </select>
                                </div>
                                <div class="form-field">
                                    <label for="rdSoloDifficulty">AI Difficulty</label>
                                    <select id="rdSoloDifficulty">
                                        <option value="easy">Easy</option>
                                        <option value="medium" selected>Medium</option>
                                        <option value="hard">Hard</option>
                                    </select>
                                </div>
                                <div class="form-field">
                                    <label for="rdSoloWinCondition">Win Condition</label>
                                    <select id="rdSoloWinCondition">
                                        <option value="twenty_dots">First to 20 total dots</option>
                                        <option value="five_colors">First to 5 of each color</option>
                                        <option value="five_with_yellow">First to 5 of each color plus 5 yellow</option>
                                    </select>
                                </div>
                                <div class="form-field full">
                                    <label for="rdSoloPowerCards">Power Cards</label>
                                    <select id="rdSoloPowerCards">
                                        <option value="on">Enabled</option>
                                        <option value="off">Disabled</option>
                                    </select>
                                </div>
                            </div>
                            <div class="actions-row" style="margin-top: 18px;">
                                <button type="button" class="rd-btn" id="rdStartSoloBtn">Start Solo Match</button>
                            </div>
                            <div id="rdSoloError" class="error-box hidden" style="margin-top: 18px;"></div>
                        </div>
                    </div>
                </section>

                <section id="rdLobbyScreen" class="screen">
                    <div class="lobby-shell">
                        <div class="lobby-panel">
                            <span class="eyebrow">Lobby</span>
                            <h2 id="rdLobbyTitle">Waiting for players</h2>
                            <p id="rdLobbySubtitle" class="muted">The game starts automatically when every seat is filled.</p>
                            <div class="progress-ring" id="rdLobbyProgress"><span>0 / 0</span></div>
                            <div class="info-stack">
                                <div id="rdLobbyStatus" class="notice">No room loaded.</div>
                                <div class="lobby-meta" id="rdLobbyMeta"></div>
                            </div>
                            <div class="actions-row" style="margin-top: 18px;">
                                <button type="button" class="rd-btn-secondary" id="rdCopyInviteBtn">Copy Invite Link</button>
                                <button type="button" class="rd-btn-ghost" id="rdLeaveLobbyBtn">Leave Lobby</button>
                            </div>
                        </div>
                        <div class="lobby-panel">
                            <h2>Seats</h2>
                            <div id="rdLobbyRoster" class="roster-grid"></div>
                        </div>
                    </div>
                </section>

                <section id="rdGameScreen" class="screen">
                    <div class="game-screen">
                        <div class="game-header">
                            <div>
                                <span class="eyebrow">Live Match</span>
                                <h1>Twenty Dots</h1>
                                <div id="rdTurnBanner" class="turn-banner">Waiting for the match state...</div>
                            </div>
                            <div class="toolbar">
                                <div id="rdConnectionChip" class="status-chip"><strong>Connection</strong> <span>Offline</span></div>
                                <div id="rdGameMetaChips" class="board-meta"></div>
                                <div class="music-strip">
                                    <button type="button" class="rd-icon-btn" id="rdMusicToggle" title="Toggle music">♫</button>
                                    <button type="button" class="rd-icon-btn" id="rdMusicSkip" title="Next track">↷</button>
                                </div>
                            </div>
                        </div>

                        <div class="game-layout">
                            <aside class="sidebar-panel">
                                <h2>Table</h2>
                                <div id="rdObjectiveBanner" class="help-banner">Objective information will appear here.</div>
                                <div class="summary-grid" style="margin-top: 16px;">
                                    <div class="summary-card"><h3>Room</h3><strong id="rdSummaryRoom">-</strong></div>
                                    <div class="summary-card"><h3>Deck</h3><strong id="rdSummaryDeck">0</strong></div>
                                    <div class="summary-card"><h3>Turn</h3><strong id="rdSummaryTurn">1</strong></div>
                                    <div class="summary-card"><h3>Wild Dot</h3><strong id="rdSummaryWild">None</strong></div>
                                </div>
                                <div class="panel" style="margin-top: 18px; padding: 18px;">
                                    <h2>Players</h2>
                                    <div id="rdPlayersGrid" class="players-grid"></div>
                                </div>
                            </aside>

                            <main class="board-panel">
                                <div class="board-toolbar">
                                    <div>
                                        <h2 style="margin: 0 0 6px;">Board</h2>
                                        <p id="rdActionHint" class="muted" style="margin: 0;">Roll the wild dot when prompted, then play up to two cards.</p>
                                    </div>
                                    <div id="rdBoardAlerts" class="board-meta"></div>
                                </div>
                                <div class="board-frame">
                                    <div id="rdBoard" class="board"></div>
                                </div>
                            </main>

                            <aside class="controls-panel">
                                <h2>Your Actions</h2>
                                <div id="rdControlBanner" class="help-banner">Your hand and actions update based on turn state.</div>
                                <div class="control-list" style="margin-top: 16px;">
                                    <button type="button" class="rd-btn" id="rdPlayBtn">Play Selected Cards</button>
                                    <button type="button" class="rd-btn-secondary" id="rdRollBtn">Roll Wild Dot</button>
                                    <button type="button" class="rd-btn-ghost" id="rdClearBtn">Clear Selection</button>
                                    <button type="button" class="rd-btn-ghost hidden" id="rdCancelPowerBtn">Cancel Power</button>
                                </div>
                                <div class="panel" style="margin-top: 18px; padding: 18px;">
                                    <div class="section-row">
                                        <h2 style="margin: 0;">Your Hand</h2>
                                        <div class="status-chip"><strong>Selected</strong> <span id="rdSelectedCount">0 / 2</span></div>
                                    </div>
                                    <div id="rdHandGrid" class="hand-grid" style="margin-top: 16px;"></div>
                                </div>
                                <div id="rdLandminePanel" class="panel" style="margin-top: 18px; padding: 18px;">
                                    <h2>Landmines</h2>
                                    <div id="rdLandmineStack" class="landmine-stack"></div>
                                </div>
                            </aside>
                        </div>
                    </div>
                </section>

                <audio id="rdAudio" preload="auto"></audio>
                <div id="rdNotifications"></div>
                <div id="rdModalRoot"></div>
            </div>
        `;
    }

    function bindUi() {
        ui.screens = {
            mode: document.getElementById('rdModeScreen'),
            join: document.getElementById('rdJoinScreen'),
            solo: document.getElementById('rdSoloScreen'),
            lobby: document.getElementById('rdLobbyScreen'),
            game: document.getElementById('rdGameScreen')
        };

        ui.joinError = document.getElementById('rdJoinError');
        ui.soloError = document.getElementById('rdSoloError');
        ui.gameId = document.getElementById('rdGameId');
        ui.playerName = document.getElementById('rdPlayerName');
        ui.playerCount = document.getElementById('rdPlayerCount');
        ui.winCondition = document.getElementById('rdWinCondition');
        ui.powerCards = document.getElementById('rdPowerCards');
        ui.rejoinBtn = document.getElementById('rdRejoinBtn');
        ui.shareRoomBtn = document.getElementById('rdShareRoomBtn');
        ui.soloName = document.getElementById('rdSoloName');
        ui.soloPlayers = document.getElementById('rdSoloPlayers');
        ui.soloDifficulty = document.getElementById('rdSoloDifficulty');
        ui.soloWinCondition = document.getElementById('rdSoloWinCondition');
        ui.soloPowerCards = document.getElementById('rdSoloPowerCards');

        ui.lobbyTitle = document.getElementById('rdLobbyTitle');
        ui.lobbySubtitle = document.getElementById('rdLobbySubtitle');
        ui.lobbyProgress = document.getElementById('rdLobbyProgress');
        ui.lobbyStatus = document.getElementById('rdLobbyStatus');
        ui.lobbyMeta = document.getElementById('rdLobbyMeta');
        ui.lobbyRoster = document.getElementById('rdLobbyRoster');

        ui.turnBanner = document.getElementById('rdTurnBanner');
        ui.connectionChip = document.getElementById('rdConnectionChip');
        ui.gameMetaChips = document.getElementById('rdGameMetaChips');
        ui.objectiveBanner = document.getElementById('rdObjectiveBanner');
        ui.summaryRoom = document.getElementById('rdSummaryRoom');
        ui.summaryDeck = document.getElementById('rdSummaryDeck');
        ui.summaryTurn = document.getElementById('rdSummaryTurn');
        ui.summaryWild = document.getElementById('rdSummaryWild');
        ui.playersGrid = document.getElementById('rdPlayersGrid');
        ui.actionHint = document.getElementById('rdActionHint');
        ui.boardAlerts = document.getElementById('rdBoardAlerts');
        ui.board = document.getElementById('rdBoard');
        ui.controlBanner = document.getElementById('rdControlBanner');
        ui.playBtn = document.getElementById('rdPlayBtn');
        ui.rollBtn = document.getElementById('rdRollBtn');
        ui.clearBtn = document.getElementById('rdClearBtn');
        ui.cancelPowerBtn = document.getElementById('rdCancelPowerBtn');
        ui.selectedCount = document.getElementById('rdSelectedCount');
        ui.handGrid = document.getElementById('rdHandGrid');
        ui.landmineStack = document.getElementById('rdLandmineStack');
        ui.landminePanel = document.getElementById('rdLandminePanel');
        ui.audio = document.getElementById('rdAudio');
        ui.notificationStack = document.getElementById('rdNotifications');
        ui.modalRoot = document.getElementById('rdModalRoot');
        ui.musicToggle = document.getElementById('rdMusicToggle');

        document.getElementById('rdOpenMultiplayer').addEventListener('click', () => showScreen('join'));
        document.getElementById('rdOpenSolo').addEventListener('click', () => showScreen('solo'));
        document.getElementById('rdBackToMode').addEventListener('click', () => showScreen('mode'));
        document.getElementById('rdBackFromSolo').addEventListener('click', () => showScreen('mode'));
        document.getElementById('rdJoinRoomBtn').addEventListener('click', joinGame);
        document.getElementById('rdStartSoloBtn').addEventListener('click', startSinglePlayer);
        document.getElementById('rdCopyInviteBtn').addEventListener('click', shareGameRoom);
        document.getElementById('rdShareRoomBtn').addEventListener('click', shareGameRoom);
        document.getElementById('rdLeaveLobbyBtn').addEventListener('click', leaveLobby);
        ui.rejoinBtn.addEventListener('click', rejoinGame);
        ui.gameId.addEventListener('input', toggleShareButton);
        ui.playBtn.addEventListener('click', playCards);
        ui.rollBtn.addEventListener('click', rollDice);
        ui.clearBtn.addEventListener('click', clearSelection);
        ui.cancelPowerBtn.addEventListener('click', cancelPowerCard);
        document.getElementById('rdMusicToggle').addEventListener('click', toggleMusic);
        document.getElementById('rdMusicSkip').addEventListener('click', skipTrack);
    }

    function bindAudio() {
        ui.audio.addEventListener('ended', () => {
            state.currentTrackIndex = (state.currentTrackIndex + 1) % musicPlaylist.length;
            if (state.musicPlaying) {
                playTrack(state.currentTrackIndex);
            }
        });
    }

    function restoreJoinState() {
        const params = new URLSearchParams(window.location.search);
        const urlGameId = params.get('gameId');
        if (urlGameId) {
            ui.gameId.value = urlGameId;
        }

        const savedGame = safeParse(localStorage.getItem(storageKeys.currentGame));
        if (savedGame && savedGame.timestamp && Date.now() - savedGame.timestamp < 24 * 60 * 60 * 1000) {
            ui.rejoinBtn.classList.remove('hidden');
            if (!ui.gameId.value) {
                ui.gameId.value = savedGame.gameId || '';
            }
            if (!ui.playerName.value) {
                ui.playerName.value = savedGame.playerName || '';
            }
        } else {
            localStorage.removeItem(storageKeys.currentGame);
        }

        toggleShareButton();
    }

    function showScreen(name) {
        Object.entries(ui.screens).forEach(([key, screen]) => {
            screen.classList.toggle('active', key === name);
        });
    }

    function toggleShareButton() {
        ui.shareRoomBtn.disabled = !ui.gameId.value.trim();
    }

    function leaveLobby() {
        if (state.socket) {
            state.socket.disconnect();
            state.socket = null;
            state.socketHandlersBound = false;
        }
        localStorage.removeItem(storageKeys.currentGame);
        state.lobbyState = null;
        state.currentGameState = null;
        state.myHand = [];
        state.selectedCards = [];
        showScreen('join');
        updateConnectionChip('Offline');
    }

    function joinGame() {
        clearError(ui.joinError);
        state.gameId = ui.gameId.value.trim();
        state.playerName = ui.playerName.value.trim();

        if (!state.gameId || !state.playerName) {
            return showError(ui.joinError, 'Enter both a game ID and your name.');
        }

        connectSocket(() => {
            state.socket.emit('join_game', {
                game_id: state.gameId,
                player_name: state.playerName,
                game_mode: ui.winCondition.value,
                player_count: parseInt(ui.playerCount.value, 10),
                power_cards: ui.powerCards.value === 'on'
            });
        });
    }

    function rejoinGame() {
        const savedGame = safeParse(localStorage.getItem(storageKeys.currentGame));
        if (!savedGame || !savedGame.gameId || !savedGame.playerName) {
            return showError(ui.joinError, 'No saved room was found.');
        }

        ui.gameId.value = savedGame.gameId;
        ui.playerName.value = savedGame.playerName;
        state.gameId = savedGame.gameId;
        state.playerName = savedGame.playerName;
        clearError(ui.joinError);

        connectSocket(() => {
            state.socket.emit('join_game', {
                game_id: state.gameId,
                player_name: state.playerName,
                game_mode: 'twenty_dots',
                player_count: 4,
                power_cards: true
            });
        });
    }

    function startSinglePlayer() {
        clearError(ui.soloError);
        state.playerName = ui.soloName.value.trim() || 'Player';
        connectSocket(() => {
            state.socket.emit('start_single_player', {
                player_name: state.playerName,
                num_players: parseInt(ui.soloPlayers.value, 10),
                difficulty: ui.soloDifficulty.value,
                game_mode: ui.soloWinCondition.value,
                power_cards: ui.soloPowerCards.value === 'on'
            });
        });
    }

    function connectSocket(onConnectAction) {
        if (typeof io !== 'function') {
            showNotification('Socket.IO is not available on this page.', 'error');
            return;
        }

        if (state.socket) {
            state.socket.disconnect();
        }

        state.socket = io(window.location.origin, { transports: ['websocket', 'polling'] });
        state.socketHandlersBound = false;
        bindSocketHandlers(onConnectAction);
    }

    function bindSocketHandlers(onConnectAction) {
        if (!state.socket || state.socketHandlersBound) {
            return;
        }

        state.socketHandlersBound = true;

        state.socket.on('connect', () => {
            updateConnectionChip('Live');
            if (typeof onConnectAction === 'function') {
                onConnectAction();
            }
        });

        state.socket.on('disconnect', () => {
            updateConnectionChip('Offline');
            showNotification('Disconnected from server.', 'warning');
        });

        state.socket.on('join_success', (payload) => {
            state.gameId = payload.game_id || state.gameId;
            state.lobbyState = payload;
            saveCurrentGame();
            updateLobby(payload);
            showScreen('lobby');
            showNotification(`Joined room ${state.gameId}.`, 'info');
        });

        state.socket.on('lobby_updated', (payload) => {
            state.lobbyState = payload;
            if (!payload.started) {
                updateLobby(payload);
            }
        });

        state.socket.on('player_joined', (payload) => {
            if (payload.lobby) {
                state.lobbyState = payload.lobby;
                updateLobby(payload.lobby);
            }
            if (payload.player_name && payload.player_name !== state.playerName) {
                showNotification(`${payload.player_name} joined the room.`, 'info');
            }
        });

        state.socket.on('player_disconnected', (payload) => {
            if (payload.lobby) {
                state.lobbyState = payload.lobby;
                updateLobby(payload.lobby);
            }
            if (payload.player) {
                showNotification(`${payload.player} disconnected.`, 'warning');
            }
        });

        state.socket.on('game_started', (gameState) => {
            state.gameId = gameState.game_id || state.gameId;
            state.currentGameState = gameState;
            saveCurrentGame();
            showScreen('game');
            updateGameState(gameState);
            showNotification('Match started.', 'info');
        });

        state.socket.on('game_updated', (gameState) => {
            state.currentGameState = gameState;
            updateGameState(gameState);
        });

        state.socket.on('your_hand', (data) => {
            state.myHand = Array.isArray(data.hand) ? data.hand : [];
            if (state.cardSwapMode && state.cardSwapStep === 'select_own') {
                state.cardSwapOwnCards = [];
            }
            updateHand();
            syncActionState();
        });

        state.socket.on('error', (data) => {
            showNotification(data.message || 'Unknown error.', 'error');
        });

        state.socket.on('game_over', (data) => {
            handleGameOver(data);
        });

        state.socket.on('select_swap_dots', () => {
            state.swapMode = true;
            state.swapPositions = [];
            showCancelButton();
            updateBoard();
            updateHints();
            showNotification('Swap power active: pick two non-yellow dots on the board.', 'info');
        });

        state.socket.on('select_landmine_sacrifice', () => {
            state.landmineMode = true;
            showCancelButton();
            updateHints();
            updateHand();
            showNotification('Landmine power active: choose a regular card whose board space is empty.', 'warning');
        });

        state.socket.on('landmine_placed', (data) => {
            hideCancelButton();
            showNotification(`${data.player} placed a landmine.`, 'warning');
        });

        state.socket.on('landmine_detonated', (data) => {
            showNotification(`Landmine at ${data.location} detonated. ${data.removed_count} dots were removed.`, 'error');
        });

        state.socket.on('dot_removed', (data) => {
            showNotification(`${data.player} removed a ${data.color} dot at ${data.position}.`, 'warning');
        });

        state.socket.on('select_wild_position', () => {
            state.wildPlaceMode = true;
            showCancelButton();
            updateBoard();
            updateHints();
            showNotification('Wild placement active: click any board cell.', 'info');
        });

        state.socket.on('select_block_position', () => {
            state.blockMode = true;
            showCancelButton();
            updateBoard();
            updateHints();
            showNotification('Block power active: choose an empty, unblocked cell.', 'info');
        });

        state.socket.on('block_placed', (data) => {
            hideCancelButton();
            showNotification(`${data.player} blocked ${data.position} for ${data.rounds_remaining} rounds.`, 'warning');
        });

        state.socket.on('select_card_swap', () => {
            state.cardSwapMode = true;
            state.cardSwapStep = 'select_own';
            state.cardSwapOwnCards = [];
            state.cardSwapOpponent = null;
            showCancelButton();
            updateHand();
            updateHints();
            showNotification('Card swap active: choose 2 cards from your hand.', 'info');
        });

        state.socket.on('select_card_swap_opponent', (data) => {
            state.cardSwapStep = 'select_opponent';
            showOpponentSelectModal(data.opponents || []);
        });

        state.socket.on('select_opponent_cards_for_swap', (data) => {
            state.cardSwapStep = 'select_opponent_cards';
            showOpponentCardsModal(data.opponent, data.hand_size || 0);
        });

        state.socket.on('card_swap_complete', (data) => {
            resetPowerModes();
            closeModal();
            hideCancelButton();
            showNotification(`Card swap complete. You received ${data.received.join(', ')}.`, 'info');
        });
    }

    function updateLobby(lobby) {
        if (!lobby) {
            return;
        }

        const joined = lobby.joined_players || 0;
        const required = lobby.required_players || 0;
        const openSlots = Math.max(required - joined, 0);
        const percentage = required ? Math.round((joined / required) * 100) : 0;

        ui.lobbyTitle.textContent = openSlots > 0 ? `Waiting for ${openSlots} more player${openSlots === 1 ? '' : 's'}` : 'Room is full';
        ui.lobbySubtitle.textContent = openSlots > 0 ? 'Share the room link or room code. The game starts automatically when every seat is filled.' : 'All seats are filled. Starting the match...';
        ui.lobbyProgress.style.setProperty('--progress', `${percentage}%`);
        ui.lobbyProgress.innerHTML = `<span>${joined} / ${required}<br><small>seats filled</small></span>`;
        ui.lobbyStatus.textContent = `${friendlyModeName(lobby.game_mode)} · ${lobby.power_cards ? 'Power cards on' : 'Power cards off'}`;
        ui.lobbyMeta.innerHTML = '';
        ui.lobbyMeta.appendChild(makeChip('Room', lobby.game_id || '-'));
        ui.lobbyMeta.appendChild(makeChip('Host', lobby.host_name || 'Waiting'));
        ui.lobbyMeta.appendChild(makeChip('Seats', `${joined}/${required}`));

        ui.lobbyRoster.innerHTML = '';
        const players = Array.isArray(lobby.players) ? lobby.players : [];
        for (let index = 0; index < required; index += 1) {
            const player = players[index];
            const card = document.createElement('div');
            card.className = `roster-card${player ? '' : ' empty'}`;

            const title = document.createElement('div');
            title.className = 'title';
            title.textContent = player ? `Seat ${index + 1}: ${player.name}` : `Seat ${index + 1}: Open`;
            card.appendChild(title);

            const meta = document.createElement('div');
            meta.className = 'muted';
            if (player) {
                const tags = [player.is_ai ? 'AI' : 'Human', player.connected ? 'Connected' : 'Offline'];
                meta.textContent = tags.join(' · ');
            } else {
                meta.textContent = 'Invite another player to claim this seat.';
            }
            card.appendChild(meta);
            ui.lobbyRoster.appendChild(card);
        }
    }

    function updateGameState(gameState) {
        if (!gameState) {
            return;
        }

        state.currentGameState = gameState;
        updateConnectionChip('Live');
        ui.summaryRoom.textContent = gameState.game_id || state.gameId || '-';
        ui.summaryDeck.textContent = String(gameState.deck_size ?? 0);
        ui.summaryTurn.textContent = String(gameState.turn_number ?? 1);
        ui.summaryWild.textContent = formatWildPosition(gameState.yellow_dot_position);

        ui.gameMetaChips.innerHTML = '';
        ui.gameMetaChips.appendChild(makeChip('Mode', friendlyModeName(gameState.game_mode)));
        ui.gameMetaChips.appendChild(makeChip('Players', `${Object.keys(gameState.players || {}).length}/${gameState.required_players || Object.keys(gameState.players || {}).length}`));
        ui.gameMetaChips.appendChild(makeChip('Power', gameState.power_cards ? 'On' : 'Off'));

        updateTurnBanner(gameState.current_turn);
        updatePlayers(gameState.players || {}, gameState.current_turn, gameState.player_order || Object.keys(gameState.players || {}));
        updateBoard();
        updateLandmines(gameState.landmines || []);
        updateHints();
        updateHand();
        syncActionState();
    }

    function updateTurnBanner(currentTurn) {
        const isMyTurn = currentTurn === state.playerName;
        ui.turnBanner.classList.toggle('yours', isMyTurn);
        ui.turnBanner.textContent = isMyTurn ? 'Your turn is live.' : `${currentTurn || 'Unknown'} is taking the turn.`;
    }

    function updatePlayers(players, currentTurn, order) {
        ui.playersGrid.innerHTML = '';
        const connectedLookup = new Map();
        const lobbyPlayers = state.currentGameState && state.currentGameState.lobby && Array.isArray(state.currentGameState.lobby.players)
            ? state.currentGameState.lobby.players
            : [];

        lobbyPlayers.forEach((player) => {
            connectedLookup.set(player.name, player.connected);
        });

        order.forEach((name, index) => {
            const data = players[name] || {};
            const card = document.createElement('div');
            card.className = 'seat-card';
            if (name === currentTurn) {
                card.classList.add('active');
            }
            if (name === state.playerName) {
                card.classList.add('self');
            }

            const top = document.createElement('div');
            top.className = 'seat-top';
            const seatName = document.createElement('div');
            seatName.className = 'seat-name';
            seatName.textContent = `${index + 1}. ${name}${name === state.playerName ? ' (You)' : ''}`;
            top.appendChild(seatName);

            const badges = document.createElement('div');
            badges.className = 'seat-badges';
            if (state.currentGameState.lobby && state.currentGameState.lobby.host_name === name) {
                badges.appendChild(makeBadge('Host', 'host'));
            }
            if (name === currentTurn) {
                badges.appendChild(makeBadge('Turn', 'turn'));
            }
            if (connectedLookup.get(name) === false) {
                badges.appendChild(makeBadge('Offline', 'offline'));
            }
            top.appendChild(badges);
            card.appendChild(top);

            const metaRow = document.createElement('div');
            metaRow.className = 'seat-meta-line';
            metaRow.appendChild(makeInlinePill('Dots', String(data.total_dots || 0)));
            metaRow.appendChild(makeInlinePill('Hand', String(data.hand_size || 0)));
            card.appendChild(metaRow);

            const scoreRow = document.createElement('div');
            scoreRow.className = 'score-row';
            ['red', 'blue', 'green', 'purple'].forEach((color) => {
                scoreRow.appendChild(makeScorePill(color, data.score ? data.score[color] || 0 : 0));
            });
            if (state.currentGameState.game_mode === 'five_with_yellow') {
                scoreRow.appendChild(makeScorePill('yellow', data.yellow_dots || 0));
            }
            card.appendChild(scoreRow);

            const discardRow = document.createElement('div');
            discardRow.className = 'discard-row';
            const discard = Array.isArray(data.discard_pile) ? data.discard_pile.slice(-1) : [];
            if (discard.length === 0) {
                discardRow.appendChild(makeInlinePill('Discard', '-'));
            } else {
                discard.forEach((cardData) => {
                    const pill = document.createElement('div');
                    pill.className = 'discard-pill';
                    pill.textContent = cardData.power ? `${powerIcons[cardData.power] || '⚡'} ${humanizePower(cardData.power)}` : `${cardData.location} ${cardData.color}`;
                    discardRow.appendChild(pill);
                });
            }
            card.appendChild(discardRow);

            const stats = getPlayerStats(name);
            const recordRow = document.createElement('div');
            recordRow.className = 'seat-meta-line compact-record';
            recordRow.appendChild(makeInlinePill('W', String(stats.wins)));
            recordRow.appendChild(makeInlinePill('L', String(stats.losses)));
            card.appendChild(recordRow);

            ui.playersGrid.appendChild(card);
        });
    }

    function updateBoard() {
        const gameState = state.currentGameState;
        if (!gameState) {
            return;
        }

        const board = gameState.board || [];
        ui.board.innerHTML = '';

        ui.board.appendChild(document.createElement('div'));
        cols.forEach((col) => ui.board.appendChild(makeBoardLabel(col)));
        ui.board.appendChild(document.createElement('div'));

        for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
            ui.board.appendChild(makeBoardLabel(rows[rowIndex]));

            for (let colIndex = 0; colIndex < cols.length; colIndex += 1) {
                const cell = document.createElement('button');
                cell.type = 'button';
                cell.className = 'board-cell';
                cell.dataset.row = String(rowIndex);
                cell.dataset.col = String(colIndex);
                cell.addEventListener('click', () => handleCellClick(rowIndex, colIndex));

                const block = Array.isArray(gameState.blocks)
                    ? gameState.blocks.find((item) => item.row === rowIndex && item.col === colIndex)
                    : null;
                if (block) {
                    cell.classList.add('blocked');
                    const indicator = document.createElement('span');
                    indicator.className = 'block-indicator';
                    indicator.textContent = '⛔';
                    indicator.title = `Blocked for ${block.rounds_remaining || 1} round(s)`;
                    cell.appendChild(indicator);
                }

                if (isBoardTarget(rowIndex, colIndex)) {
                    cell.classList.add('mode-target');
                }
                if (state.swapPositions.some((pos) => pos.row === rowIndex && pos.col === colIndex)) {
                    cell.classList.add('swap-selected');
                }

                const dotData = board[rowIndex] ? board[rowIndex][colIndex] : null;
                if (dotData) {
                    const dot = document.createElement('div');
                    dot.className = `dot ${dotData.color}`;
                    cell.appendChild(dot);
                    if (state.swapMode && dotData.color !== 'yellow') {
                        cell.classList.add('swap-target');
                    }
                }

                ui.board.appendChild(cell);
            }

            ui.board.appendChild(makeBoardLabel(rows[rowIndex]));
        }

        ui.board.appendChild(document.createElement('div'));
        cols.forEach((col) => ui.board.appendChild(makeBoardLabel(col)));
        ui.board.appendChild(document.createElement('div'));

        updateBoardAlerts();
    }

    function updateBoardAlerts() {
        ui.boardAlerts.innerHTML = '';
        const gameState = state.currentGameState;
        if (!gameState) {
            return;
        }

        if (gameState.yellow_dot_position) {
            ui.boardAlerts.appendChild(makeChip('Wild', formatWildPosition(gameState.yellow_dot_position)));
        }
        if (Array.isArray(gameState.blocks) && gameState.blocks.length) {
            ui.boardAlerts.appendChild(makeChip('Blocks', String(gameState.blocks.length)));
        }
        if (Array.isArray(gameState.landmines) && gameState.landmines.length) {
            ui.boardAlerts.appendChild(makeChip('Mines', String(gameState.landmines.length)));
        }
    }

    function updateLandmines(landmines) {
        ui.landmineStack.innerHTML = '';
        if (!Array.isArray(landmines) || landmines.length === 0) {
            ui.landminePanel.classList.add('collapsed');
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = 'No landmines on the board.';
            ui.landmineStack.appendChild(empty);
            return;
        }

        ui.landminePanel.classList.remove('collapsed');

        landmines.forEach((mine) => {
            const token = document.createElement('div');
            token.className = 'landmine-token';
            if (mine.player === state.playerName) {
                token.classList.add('mine');
            }
            const label = mine.player === state.playerName ? mine.location : 'Hidden';
            token.innerHTML = `<strong>Mine</strong><div class="muted">${label}</div>`;
            ui.landmineStack.appendChild(token);
        });
    }

    function updateHints() {
        const gameState = state.currentGameState;
        if (!gameState) {
            return;
        }

        const isMyTurn = gameState.current_turn === state.playerName;
        const canRoll = !!gameState.can_roll_dice;
        const objective = objectiveText(gameState.game_mode);
        ui.objectiveBanner.textContent = objective;
        ui.objectiveBanner.className = 'help-banner';

        if (state.swapMode) {
            ui.actionHint.textContent = 'Swap power: pick two non-yellow dots.';
            ui.controlBanner.textContent = 'Swap power is active. The selected power card will resolve after your second dot choice.';
            ui.controlBanner.className = 'help-banner warning';
            return;
        }
        if (state.wildPlaceMode) {
            ui.actionHint.textContent = 'Wild power: choose any board space.';
            ui.controlBanner.textContent = 'Place the wild dot on the board to finish the power-card action.';
            ui.controlBanner.className = 'help-banner warning';
            return;
        }
        if (state.blockMode) {
            ui.actionHint.textContent = 'Block power: choose an empty, open cell.';
            ui.controlBanner.textContent = 'The selected cell will be blocked for three rounds.';
            ui.controlBanner.className = 'help-banner warning';
            return;
        }
        if (state.landmineMode) {
            ui.actionHint.textContent = 'Landmine power: choose a regular card with an empty target square.';
            ui.controlBanner.textContent = 'The sacrifice card defines the landmine location.';
            ui.controlBanner.className = 'help-banner warning';
            return;
        }
        if (state.cardSwapMode) {
            ui.actionHint.textContent = 'Card swap power: follow the prompts to choose cards and an opponent.';
            ui.controlBanner.textContent = 'Card swap is active.';
            ui.controlBanner.className = 'help-banner warning';
            return;
        }

        if (!isMyTurn) {
            ui.actionHint.textContent = `${gameState.current_turn} is playing. Watch the table and plan your move.`;
            ui.controlBanner.textContent = 'Your cards stay visible, but actions unlock only on your turn.';
            ui.controlBanner.className = 'help-banner';
            return;
        }

        if (canRoll) {
            ui.actionHint.textContent = 'Roll the wild dot before playing more cards.';
            ui.controlBanner.textContent = 'A yellow match can give you another wild roll. Normal play resumes after the roll resolves.';
            ui.controlBanner.className = 'help-banner warning';
            return;
        }

        ui.actionHint.textContent = 'Play one or two cards. Power cards must be played alone.';
        ui.controlBanner.textContent = 'Select up to two regular cards, or one power card.';
        ui.controlBanner.className = 'help-banner';
    }

    function updateHand() {
        ui.handGrid.innerHTML = '';
        if (!state.myHand.length) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = 'Your hand will appear here after the match starts.';
            ui.handGrid.appendChild(empty);
            ui.selectedCount.textContent = '0 / 2';
            return;
        }

        state.myHand.forEach((card, index) => {
            const cardEl = document.createElement('button');
            cardEl.type = 'button';
            cardEl.className = `hand-card ${card.color}${card.power ? ' power' : ''}`;
            if (state.selectedCards.includes(index)) {
                cardEl.classList.add('selected');
            }
            if (state.cardSwapOwnCards.includes(index)) {
                cardEl.classList.add('swap-picked');
            }
            if (isHandCardDisabled()) {
                cardEl.classList.add('disabled');
            }

            if (card.power) {
                cardEl.innerHTML = `
                    <div class="power-label">Power Card</div>
                    <div class="loc">${powerIcons[card.power] || '⚡'}</div>
                    <div>${humanizePower(card.power)}</div>
                    <div class="meta">${card.power_description || ''}</div>
                `;
            } else {
                cardEl.innerHTML = `
                    <div class="power-label">${card.color}</div>
                    <div class="loc">${card.location[0]}${card.location[1]}</div>
                    <div class="meta">Tap to ${state.landmineMode ? 'sacrifice' : 'select'} this card.</div>
                `;
            }

            cardEl.addEventListener('click', () => toggleCardSelection(index));
            ui.handGrid.appendChild(cardEl);
        });

        ui.selectedCount.textContent = `${state.selectedCards.length} / 2`;
    }

    function toggleCardSelection(index) {
        const card = state.myHand[index];
        const gameState = state.currentGameState;
        if (!card || !gameState) {
            return;
        }

        if (state.landmineMode) {
            return handleLandmineSelection(index, card);
        }

        if (state.cardSwapMode && state.cardSwapStep === 'select_own') {
            return handleCardSwapOwnSelection(index, card);
        }

        if (isHandCardDisabled()) {
            return;
        }

        if (state.selectedCards.includes(index)) {
            state.selectedCards = state.selectedCards.filter((item) => item !== index);
            updateHand();
            syncActionState();
            return;
        }

        if (state.selectedCards.length >= 2) {
            return;
        }

        if (card.power && state.selectedCards.length > 0) {
            showNotification('Power cards must be played alone.', 'warning');
            return;
        }

        if (state.selectedCards.length > 0 && state.myHand[state.selectedCards[0]].power) {
            showNotification('Power cards must be played alone.', 'warning');
            return;
        }

        state.selectedCards.push(index);
        updateHand();
        syncActionState();
    }

    function handleLandmineSelection(index, card) {
        if (card.power) {
            showNotification('Landmine sacrifice must be a regular card.', 'warning');
            return;
        }

        const rowIndex = rows.indexOf(card.location[0]);
        const colIndex = cols.indexOf(String(card.location[1]));
        const occupied = state.currentGameState.board[rowIndex] && state.currentGameState.board[rowIndex][colIndex];
        if (occupied) {
            showNotification(`Location ${card.location[0]}${card.location[1]} is occupied.`, 'warning');
            return;
        }

        if (!window.confirm(`Sacrifice ${card.color} at ${card.location[0]}${card.location[1]} to place a landmine there?`)) {
            return;
        }

        state.socket.emit('place_landmine', {
            game_id: state.gameId,
            sacrifice_card: {
                color: card.color,
                location: card.location
            }
        });
        state.landmineMode = false;
        updateHints();
    }

    function handleCardSwapOwnSelection(index, card) {
        if (card.power) {
            showNotification('Power cards cannot be exchanged in card swap.', 'warning');
            return;
        }

        if (state.cardSwapOwnCards.includes(index)) {
            state.cardSwapOwnCards = state.cardSwapOwnCards.filter((item) => item !== index);
        } else if (state.cardSwapOwnCards.length < 2) {
            state.cardSwapOwnCards.push(index);
        }

        updateHand();

        if (state.cardSwapOwnCards.length === 2) {
            const cards = state.cardSwapOwnCards.map((selectedIndex) => state.myHand[selectedIndex]);
            state.cardSwapStep = 'waiting_for_opponent_list';
            state.socket.emit('card_swap_action', {
                game_id: state.gameId,
                step: 'select_own_cards',
                cards: cards.map((item) => ({
                    color: item.color,
                    location: item.location,
                    power: item.power || null
                }))
            });
        }
    }

    function playCards() {
        if (!state.selectedCards.length || !state.socket) {
            return;
        }

        const cards = state.selectedCards.map((index) => state.myHand[index]);
        const hasPower = cards.some((card) => card.power);
        if (hasPower && cards.length > 1) {
            showNotification('Power cards must be played alone.', 'warning');
            return;
        }

        state.socket.emit('play_cards', {
            game_id: state.gameId,
            cards
        });

        state.selectedCards = [];
        updateHand();
        syncActionState();
    }

    function rollDice() {
        if (state.socket) {
            state.socket.emit('roll_dice', { game_id: state.gameId });
        }
    }

    function clearSelection() {
        state.selectedCards = [];
        updateHand();
        syncActionState();
    }

    function cancelPowerCard() {
        if (!state.socket) {
            return;
        }
        state.socket.emit('cancel_power_card', { game_id: state.gameId });
        resetPowerModes();
        closeModal();
        hideCancelButton();
        updateBoard();
        updateHand();
        updateHints();
        syncActionState();
        showNotification('Power card canceled and returned to hand.', 'info');
    }

    function handleCellClick(rowIndex, colIndex) {
        if (!state.currentGameState) {
            return;
        }

        if (state.wildPlaceMode) {
            if (!window.confirm(`Place the wild dot at ${rows[rowIndex]}${cols[colIndex]}?`)) {
                return;
            }
            state.socket.emit('place_wild', {
                game_id: state.gameId,
                position: { row: rowIndex, col: colIndex }
            });
            state.wildPlaceMode = false;
            hideCancelButton();
            updateBoard();
            updateHints();
            return;
        }

        if (state.blockMode) {
            const occupied = state.currentGameState.board[rowIndex] && state.currentGameState.board[rowIndex][colIndex];
            const blocked = Array.isArray(state.currentGameState.blocks)
                && state.currentGameState.blocks.some((block) => block.row === rowIndex && block.col === colIndex);
            if (occupied || blocked) {
                showNotification('Blocks can only be placed on empty, open cells.', 'warning');
                return;
            }
            if (!window.confirm(`Block ${rows[rowIndex]}${cols[colIndex]} for 3 rounds?`)) {
                return;
            }
            state.socket.emit('place_block', {
                game_id: state.gameId,
                position: { row: rowIndex, col: colIndex }
            });
            state.blockMode = false;
            hideCancelButton();
            updateBoard();
            updateHints();
            return;
        }

        if (!state.swapMode) {
            return;
        }

        const dot = state.currentGameState.board[rowIndex] && state.currentGameState.board[rowIndex][colIndex];
        if (!dot) {
            showNotification('Swap power requires selecting two occupied cells.', 'warning');
            return;
        }
        if (dot.color === 'yellow') {
            showNotification('The wild yellow dot cannot be swapped.', 'warning');
            return;
        }

        const existing = state.swapPositions.findIndex((item) => item.row === rowIndex && item.col === colIndex);
        if (existing >= 0) {
            state.swapPositions.splice(existing, 1);
        } else if (state.swapPositions.length < 2) {
            state.swapPositions.push({ row: rowIndex, col: colIndex });
        }

        updateBoard();
        if (state.swapPositions.length === 2) {
            state.socket.emit('swap_dots', {
                game_id: state.gameId,
                pos1: state.swapPositions[0],
                pos2: state.swapPositions[1]
            });
            state.swapMode = false;
            state.swapPositions = [];
            hideCancelButton();
            updateBoard();
            updateHints();
        }
    }

    function syncActionState() {
        const gameState = state.currentGameState;
        const isMyTurn = !!gameState && gameState.current_turn === state.playerName;
        const canRoll = !!gameState && !!gameState.can_roll_dice;
        const activePowerMode = state.swapMode || state.landmineMode || state.wildPlaceMode || state.blockMode || state.cardSwapMode;
        const canPlaySelection = isMyTurn && !canRoll && !activePowerMode && state.selectedCards.length > 0;

        ui.playBtn.disabled = !canPlaySelection;
        ui.rollBtn.disabled = !(isMyTurn && canRoll && !activePowerMode);
        ui.clearBtn.disabled = state.selectedCards.length === 0;
        ui.cancelPowerBtn.disabled = !activePowerMode;
        ui.selectedCount.textContent = `${state.selectedCards.length} / 2`;
    }

    function isHandCardDisabled() {
        const gameState = state.currentGameState;
        if (!gameState) {
            return true;
        }
        const isMyTurn = gameState.current_turn === state.playerName;
        const activeOverride = state.landmineMode || (state.cardSwapMode && state.cardSwapStep === 'select_own');
        if (activeOverride) {
            return false;
        }
        return !isMyTurn || !!gameState.can_roll_dice || state.swapMode || state.wildPlaceMode || state.blockMode || (state.cardSwapMode && state.cardSwapStep !== 'select_own');
    }

    function isBoardTarget(rowIndex, colIndex) {
        if (state.swapMode) {
            return true;
        }
        if (state.wildPlaceMode) {
            return true;
        }
        if (state.blockMode) {
            return true;
        }
        return false;
    }

    function showCancelButton() {
        ui.cancelPowerBtn.classList.remove('hidden');
    }

    function hideCancelButton() {
        ui.cancelPowerBtn.classList.add('hidden');
    }

    function resetPowerModes() {
        state.swapMode = false;
        state.swapPositions = [];
        state.landmineMode = false;
        state.wildPlaceMode = false;
        state.blockMode = false;
        state.cardSwapMode = false;
        state.cardSwapStep = 'none';
        state.cardSwapOwnCards = [];
        state.cardSwapOpponent = null;
        state.cardSwapOpponentCards = [];
    }

    function showOpponentSelectModal(opponents) {
        closeModal();
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        const card = document.createElement('div');
        card.className = 'modal-card';
        const title = document.createElement('h2');
        title.textContent = 'Choose an Opponent';
        card.appendChild(title);
        const copy = document.createElement('p');
        copy.className = 'muted';
        copy.textContent = 'Select which player you want to swap cards with.';
        card.appendChild(copy);

        const list = document.createElement('div');
        list.className = 'modal-list';
        opponents.forEach((opponent) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'rd-btn-secondary';
            button.textContent = `${opponent.name} · ${opponent.hand_size} cards`;
            button.addEventListener('click', () => {
                closeModal();
                state.cardSwapOpponent = opponent.name;
                state.socket.emit('card_swap_action', {
                    game_id: state.gameId,
                    step: 'select_opponent',
                    opponent: opponent.name
                });
            });
            list.appendChild(button);
        });
        card.appendChild(list);

        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'rd-btn-ghost';
        cancel.textContent = 'Cancel';
        cancel.addEventListener('click', cancelPowerCard);
        card.appendChild(cancel);

        overlay.appendChild(card);
        ui.modalRoot.appendChild(overlay);
    }

    function showOpponentCardsModal(opponentName, handSize) {
        closeModal();
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        const card = document.createElement('div');
        card.className = 'modal-card';
        card.innerHTML = `<h2>Take 2 cards from ${opponentName}</h2><p class="muted">Pick two face-down cards to complete the swap.</p>`;

        const grid = document.createElement('div');
        grid.className = 'face-down-grid';
        const selected = [];

        for (let index = 0; index < handSize; index += 1) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'face-down-card';
            button.textContent = '?';
            button.addEventListener('click', () => {
                const existing = selected.indexOf(index);
                if (existing >= 0) {
                    selected.splice(existing, 1);
                    button.classList.remove('selected');
                } else if (selected.length < 2) {
                    selected.push(index);
                    button.classList.add('selected');
                }
                confirm.disabled = selected.length !== 2;
            });
            grid.appendChild(button);
        }

        card.appendChild(grid);

        const actions = document.createElement('div');
        actions.className = 'modal-actions';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.className = 'rd-btn';
        confirm.textContent = 'Confirm Swap';
        confirm.disabled = true;
        confirm.addEventListener('click', () => {
            state.socket.emit('card_swap_action', {
                game_id: state.gameId,
                step: 'select_opponent_cards',
                card_indices: selected
            });
            closeModal();
        });
        actions.appendChild(confirm);

        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'rd-btn-ghost';
        cancel.textContent = 'Cancel';
        cancel.addEventListener('click', cancelPowerCard);
        actions.appendChild(cancel);
        card.appendChild(actions);

        overlay.appendChild(card);
        ui.modalRoot.appendChild(overlay);
    }

    function closeModal() {
        ui.modalRoot.innerHTML = '';
    }

    function shareGameRoom() {
        const roomId = state.gameId || ui.gameId.value.trim();
        if (!roomId) {
            showNotification('Enter a game ID before sharing.', 'warning');
            return;
        }

        const shareUrl = `${window.location.origin}${window.location.pathname}?gameId=${encodeURIComponent(roomId)}`;
        if (navigator.share) {
            navigator.share({
                title: 'Twenty Dots room',
                text: `Join my Twenty Dots room: ${roomId}`,
                url: shareUrl
            }).catch(() => {
                copyText(shareUrl);
            });
            return;
        }
        copyText(shareUrl);
    }

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => showNotification('Invite link copied to clipboard.', 'info'))
                .catch(() => fallbackCopy(text));
            return;
        }
        fallbackCopy(text);
    }

    function fallbackCopy(text) {
        const input = document.createElement('textarea');
        input.value = text;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        input.remove();
        showNotification('Invite link copied to clipboard.', 'info');
    }

    function toggleMusic() {
        if (state.musicPlaying) {
            ui.audio.pause();
            state.musicPlaying = false;
            ui.musicToggle.textContent = '♫';
            return;
        }

        playTrack(state.currentTrackIndex);
    }

    function playTrack(index) {
        ui.audio.src = musicPlaylist[index];
        ui.audio.play().then(() => {
            state.musicPlaying = true;
            ui.musicToggle.textContent = '▮▮';
        }).catch(() => {
            state.musicPlaying = false;
            ui.musicToggle.textContent = '♫';
            showNotification('Music playback is blocked until the browser allows audio.', 'warning');
        });
    }

    function skipTrack() {
        state.currentTrackIndex = (state.currentTrackIndex + 1) % musicPlaylist.length;
        if (state.musicPlaying) {
            playTrack(state.currentTrackIndex);
        } else {
            showNotification(`Next track queued: ${state.currentTrackIndex + 1}.`, 'info');
        }
    }

    function handleGameOver(data) {
        const winner = data.winner;
        const condition = data.condition;
        const stats = safeParse(localStorage.getItem(storageKeys.stats)) || {};
        if (!stats[state.playerName]) {
            stats[state.playerName] = { wins: 0, losses: 0 };
        }
        if (winner === state.playerName) {
            stats[state.playerName].wins += 1;
        } else {
            stats[state.playerName].losses += 1;
        }
        localStorage.setItem(storageKeys.stats, JSON.stringify(stats));
        localStorage.removeItem(storageKeys.currentGame);

        const replay = window.confirm(`${winner} wins. ${objectiveText(condition)}\n\nPress OK to reload for another game.`);
        if (replay) {
            window.location.reload();
        } else {
            showScreen('mode');
        }
    }

    function saveCurrentGame() {
        localStorage.setItem(storageKeys.currentGame, JSON.stringify({
            gameId: state.gameId,
            playerName: state.playerName,
            timestamp: Date.now()
        }));
    }

    function updateConnectionChip(label) {
        state.connectionLabel = label;
        ui.connectionChip.innerHTML = `<strong>Connection</strong> <span>${label}</span>`;
    }

    function showNotification(message, tone = 'info') {
        const note = document.createElement('div');
        note.className = `notification ${tone}`;
        note.textContent = message;
        ui.notificationStack.appendChild(note);
        window.setTimeout(() => {
            note.remove();
        }, 4200);
    }

    function showError(element, message) {
        element.textContent = message;
        element.classList.remove('hidden');
    }

    function clearError(element) {
        element.textContent = '';
        element.classList.add('hidden');
    }

    function friendlyModeName(mode) {
        if (mode === 'five_colors') {
            return '5 of each color';
        }
        if (mode === 'five_with_yellow') {
            return '5 colors + 5 yellow';
        }
        if (mode === 'deck_empty') {
            return 'Most dots after deck';
        }
        return 'First to 20 dots';
    }

    function objectiveText(mode) {
        if (mode === 'five_colors') {
            return 'Objective: be the first player to collect 5 red, 5 blue, 5 green, and 5 purple dots.';
        }
        if (mode === 'five_with_yellow') {
            return 'Objective: collect 5 of every base color and 5 yellow wild dots.';
        }
        if (mode === 'deck_empty') {
            return 'Objective: finish with the most dots when the deck runs out.';
        }
        return 'Objective: reach 20 total dots first. Yellow wild dots can complete any line.';
    }

    function humanizePower(power) {
        return String(power || '').replace(/_/g, ' ');
    }

    function formatWildPosition(position) {
        if (!position || !Array.isArray(position) || position.length < 2) {
            return 'None';
        }
        return `${position[0]}${position[1]}`;
    }

    function makeChip(label, value) {
        const chip = document.createElement('div');
        chip.className = 'status-chip';
        chip.innerHTML = `<strong>${label}</strong> <span>${value}</span>`;
        return chip;
    }

    function makeBadge(label, className) {
        const badge = document.createElement('span');
        badge.className = `badge ${className}`;
        badge.textContent = label;
        return badge;
    }

    function makeBoardLabel(text) {
        const label = document.createElement('div');
        label.className = 'board-label';
        label.textContent = text;
        return label;
    }

    function makeScorePill(color, count) {
        const pill = document.createElement('div');
        pill.className = 'score-dot';
        const dot = document.createElement('span');
        dot.className = `mini-dot ${color}`;
        const value = document.createElement('span');
        value.textContent = String(count);
        pill.appendChild(dot);
        pill.appendChild(value);
        return pill;
    }

    function makeInlinePill(label, value) {
        const pill = document.createElement('div');
        pill.className = 'hand-pill';
        pill.innerHTML = `<strong>${label}</strong> <span>${value}</span>`;
        return pill;
    }

    function getPlayerStats(name) {
        const stats = safeParse(localStorage.getItem(storageKeys.stats)) || {};
        return stats[name] || { wins: 0, losses: 0 };
    }

    function safeParse(value) {
        try {
            return value ? JSON.parse(value) : null;
        } catch {
            return null;
        }
    }
})();
