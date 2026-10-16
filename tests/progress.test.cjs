const { test } = require('node:test');
const assert = require('node:assert/strict');
const DotsProgress = require('../static/progress.js');

function store(initial = null) {
    let saved = initial;
    return { get: () => saved, set: (_key, value) => { saved = value; } };
}
function state(overrides = {}) {
    return {
        game_id: 'ROOM', round_id: 1, game_mode: 'twenty_dots',
        players: { Alex: { total_dots: 21 }, Maya: { total_dots: 12 } },
        last_move: { player: 'Alex', points: 6, lines: 2 },
        winner: { winner: 'Alex' }, ...overrides,
    };
}

test('rounds count once across duplicate snapshots, reloads, and stale rounds', async () => {
    const storage = store();
    const progress = new DotsProgress(storage, null);
    const first = await progress.observe(state(), 'Alex');
    assert.equal(first.counted, true);
    assert.deepEqual(first.unlocked.map(b => b.title), ['A Win Well Earned', 'Line Artist', 'Big Move Energy']);
    assert.equal((await progress.observe(state(), 'Alex')).counted, false);
    const resumed = new DotsProgress(storage, null);
    assert.equal((await resumed.observe(state(), 'Alex')).counted, false);
    await resumed.observe(state({ round_id: 2 }), 'Alex');
    await resumed.observe(state(), 'Alex');
    assert.equal(resumed.read().rounds, 2);
    assert.equal(resumed.read().dots, 42);
    assert.equal(resumed.read().completed.length, 1);
});

test('records, mode badges and streaks use own results, not opponents', async () => {
    const progress = new DotsProgress(store(), null);
    await progress.observe(state({ winner: null }), 'Maya');
    assert.equal(progress.read().bestMove, 0);
    assert.equal(progress.read().rounds, 0);
    for (const [index, mode] of ['twenty_dots', 'five_colors', 'five_with_yellow'].entries()) {
        await progress.observe(state({ round_id: index + 1, game_mode: mode }), 'Alex');
    }
    assert.equal(progress.read().streak, 3);
    assert.equal(DotsProgress.BADGES.find(b => b.title === 'All-Rounder').test(progress.read()), true);
    await progress.observe(state({ round_id: 4, winner: { winner: 'Maya' } }), 'Alex');
    assert.equal(progress.read().streak, 0);
    assert.equal(progress.read().bestStreak, 3);
    assert.equal(progress.read().wins, 3);
});

test('lesson only unlocks its badge; malformed and unavailable storage are safe', async () => {
    for (const storage of [store('{bad json'), store('null'), { get() { throw Error('denied'); }, set() { throw Error('denied'); } }]) {
        const progress = new DotsProgress(storage, null);
        await progress.learn();
        assert.equal(progress.read().tutorial, true);
        assert.equal(progress.read().rounds, 0);
        await progress.observe(state(), 'Alex');
        await progress.observe(state(), 'Alex');
        assert.equal(progress.read().rounds, 1);
    }
    const corrupt = new DotsProgress(store(JSON.stringify({ version: 1, rounds: -1, wins: '20', bestMove: null, wonModes: {}, completed: [null, false, { round: -1 }] })), null);
    assert.equal(corrupt.read().wins, 0);
    assert.deepEqual(corrupt.read().completed, []);
});

test('shared locks prevent counting the same round twice across tabs', async () => {
    const storage = store();
    let queue = Promise.resolve();
    const locks = { request: (_key, work) => { queue = queue.then(work); return queue; } };
    const a = new DotsProgress(storage, locks);
    const b = new DotsProgress(storage, locks);
    await Promise.all([a.observe(state(), 'Alex'), b.observe(state(), 'Alex')]);
    assert.equal(a.read().rounds, 1);
    assert.equal(b.read().wins, 1);
});

test('unknown seats and unfinished rounds do not create results', async () => {
    const progress = new DotsProgress(store(), null);
    await progress.observe(state(), 'Nobody');
    await progress.observe(state({ winner: null }), 'Alex');
    assert.equal(progress.read().rounds, 0);
    assert.equal(progress.read().bestMove, 6);
    await progress.observe(state({ round_id: 0 }), 'Alex');
    assert.equal(progress.read().rounds, 0);
});

test('quota failure preserves newer session progress over stale storage', async () => {
    const storage = store();
    const progress = new DotsProgress(storage, null);
    await progress.learn();
    storage.set = () => { throw new Error('Quota exceeded'); };
    await progress.observe(state(), 'Alex');
    await progress.observe(state(), 'Alex');
    assert.equal(progress.read().rounds, 1);
    assert.equal(progress.read().tutorial, true);
    await progress.observe(state({ round_id: 2 }), 'Alex');
    assert.equal(progress.read().rounds, 2);
});