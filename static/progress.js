/* Device-local milestones, independent of the game engine. Also testable in Node. */
(() => {
    'use strict';
    const KEY = 'twenty-dots.progress.v1';
    const MODES = ['twenty_dots', 'five_colors', 'five_with_yellow'];
    const BADGES = [
        { title: 'First Connection', description: 'Finish the three-move lesson.', test: s => s.tutorial },
        { title: 'A Win Well Earned', description: 'Win your first round.', test: s => s.wins >= 1 },
        { title: 'Line Artist', description: 'Collect two or more lines in a single move.', test: s => s.bestLines >= 2 },
        { title: 'Big Move Energy', description: 'Collect at least six dots in one move.', test: s => s.bestMove >= 6 },
        { title: 'Hat Trick', description: 'Win three recorded rounds in a row.', test: s => s.bestStreak >= 3 },
        { title: 'A Seat at the Table', description: 'Finish ten rounds.', test: s => s.rounds >= 10 },
        { title: 'All-Rounder', description: 'Win in all three game modes.', test: s => MODES.every(mode => s.wonModes.includes(mode)) },
    ];
    const count = value => Number.isSafeInteger(value) && value >= 0 ? value : 0;
    const empty = () => ({
        version: 1, rounds: 0, wins: 0, streak: 0, bestStreak: 0, dots: 0,
        bestMove: 0, bestRound: 0, bestLines: 0, tutorial: false, wonModes: [], completed: [],
    });

    function normalize(value) {
        const clean = empty();
        if (!value || value.version !== 1) return clean;
        for (const key of ['rounds', 'wins', 'streak', 'bestStreak', 'dots', 'bestMove', 'bestRound', 'bestLines']) clean[key] = count(value[key]);
        clean.wins = Math.min(clean.wins, clean.rounds);
        clean.streak = Math.min(clean.streak, clean.wins);
        clean.bestStreak = Math.max(clean.streak, Math.min(clean.bestStreak, clean.wins));
        clean.tutorial = value.tutorial === true;
        clean.wonModes = MODES.filter(mode => Array.isArray(value.wonModes) && value.wonModes.includes(mode));
        if (Array.isArray(value.completed)) {
            clean.completed = value.completed.filter(entry => entry && typeof entry.room === 'string'
                && typeof entry.player === 'string' && count(entry.round) > 0)
                .map(({ room, player, round }) => ({ room, player, round }));
        }
        return clean;
    }

    class DotsProgress {
        static KEY = KEY;
        static BADGES = BADGES;

        constructor(storage, locks = globalThis.navigator?.locks) {
            this.storage = storage;
            this.locks = locks;
            this.memory = empty();
            this.lastRaw = undefined;
        }

        invalidate() { this.memory = empty(); this.lastRaw = undefined; }

        read() {
            try {
                const saved = this.storage.get(KEY);
                // If a write failed (e.g. quota exceeded), an unchanged old value
                // must not replace newer in-memory progress on every read.
                if (saved !== this.lastRaw) {
                    this.lastRaw = saved;
                    this.memory = saved === null ? empty() : normalize(JSON.parse(saved));
                }
            } catch { /* Invalid or unavailable storage must never interrupt play. */ }
            return normalize(this.memory);
        }

        async change(update) {
            const work = () => {
                // Re-read inside the lock: two tabs seeing the same win count it once.
                const stats = this.read();
                const before = JSON.stringify(stats);
                const earned = BADGES.filter(badge => badge.test(stats));
                const counted = Boolean(update(stats));
                const unlocked = BADGES.filter(badge => badge.test(stats) && !earned.includes(badge));
                const after = JSON.stringify(stats);
                if (after !== before) {
                    this.memory = stats;
                    try { this.storage.set(KEY, after); } catch { /* Keep session-only progress. */ }
                }
                return { counted, unlocked };
            };
            if (this.locks) {
                try { return await this.locks.request(KEY, work); }
                catch { /* Restricted browsers can still keep local progress. */ }
            }
            return work();
        }

        learn() { return this.change(stats => { stats.tutorial = true; }); }

        observe(state, player) {
            return this.change(stats => {
                const own = state?.players?.[player];
                if (!own || typeof state.game_id !== 'string' || !count(state.round_id)) return false;
                const move = state.last_move;
                if (move?.player === player) {
                    stats.bestMove = Math.max(stats.bestMove, count(move.points));
                    stats.bestLines = Math.max(stats.bestLines, count(move.lines));
                }
                if (!state.winner || typeof state.winner.winner !== 'string') return false;
                const prior = stats.completed.find(entry => entry.room === state.game_id && entry.player === player);
                if (prior && prior.round >= state.round_id) return false;
                // One high-water mark per seat, rather than an ever-growing move history.
                if (prior) prior.round = state.round_id;
                else stats.completed.push({ room: state.game_id, player, round: state.round_id });
                stats.rounds++;
                stats.dots += count(own.total_dots);
                stats.bestRound = Math.max(stats.bestRound, count(own.total_dots));
                if (state.winner.winner === player) {
                    stats.wins++;
                    stats.streak++;
                    stats.bestStreak = Math.max(stats.bestStreak, stats.streak);
                    if (MODES.includes(state.game_mode) && !stats.wonModes.includes(state.game_mode)) stats.wonModes.push(state.game_mode);
                } else stats.streak = 0;
                return true;
            });
        }
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = DotsProgress;
    else globalThis.DotsProgress = DotsProgress;
})();