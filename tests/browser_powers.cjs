/* Invoked by the replay runner against its authenticated, loopback fixture server. */
const assert = require('node:assert/strict');

module.exports = async function testPowers(browser, base, request, audit, errors) {
    const contexts = [], pages = [];
    async function player(name, room) {
        const context = await browser.newContext({ viewport: { width: 320, height: 900 }, reducedMotion: 'reduce' });
        contexts.push(context);
        await context.addInitScript(() => {
            let exposed;
            Object.defineProperty(window, 'io', { configurable: true, get: () => exposed, set: original => {
                exposed = Object.assign((...args) => {
                    const socket = original(...args);
                    window.testSocket = socket;
                    window.snapshots = 0;
                    socket.onAny((event, data) => {
                        if (event === 'game_started' || event === 'game_updated') { window.lastState = data; window.snapshots++; }
                        if (event === 'your_hand') window.privateHand = data.hand;
                    });
                    return socket;
                }, original);
            } });
        });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/web_client.html${room ? `?room=${room}` : ''}`);
        await page.locator('#player-name').fill(name);
        if (!room) {
            await page.locator('input[name="player_count"][value="4"]').check();
            await page.locator('#power-cards').check();
            await page.locator('[data-power-help]').first().click();
            await audit(page, 'Power rules');
            await page.keyboard.press('Escape');
        }
        await page.locator('#start-button').click();
        return page;
    }
    try {
        const host = await player('Power host');
        pages.push(host);
        await host.locator('#lobby-screen').waitFor({ state: 'visible' });
        assert.match(await host.locator('#lobby-count').textContent(), /Power Play/);
        const code = await host.locator('#lobby-code').textContent();
        for (const name of ['Power guest', 'Third player', 'Fourth player']) pages.push(await player(name, code));
        for (const page of pages) await page.waitForFunction(() => window.lastState?.power_cards && window.privateHand?.length === 5);
        async function prepare(power, options = {}) {
            const snapshots = await host.evaluate(() => window.snapshots);
            const result = await request(`${base}/__test__/position`, { game_id: code, player: 'Power host', power, ...options });
            assert.equal(result.status, 200, result.text);
            await host.waitForFunction(n => window.snapshots > n && document.querySelectorAll('.power-card').length === 3, snapshots);
            return await host.evaluate(() => window.lastState.last_move?.id || 0);
        }
        async function changed(id, power) {
            await host.waitForFunction(({ id, power }) => window.lastState.last_move?.id > id && window.lastState.last_move.power === power, { id, power });
        }
        async function choose(power) { await host.locator(`.power-card[data-power="${power}"]`).click(); }

        let id = await prepare('paint');
        await choose('paint');
        await audit(host, 'Paint targeting at 320px');
        assert(await host.locator('#primary-action').isDisabled());
        await host.locator('#cell-A1').click();
        assert.equal(await host.locator('.cell.preview').count(), 0, 'Occupied destination cannot be selected');
        await host.locator('#cell-A3').focus();
        await host.keyboard.press('Enter');
        assert.equal(await host.locator('#cell-A3').getAttribute('aria-pressed'), 'true');
        assert.equal(await host.evaluate(() => window.lastState.board[0][2]), null, 'Target remains only a preview');
        await host.locator('#cancel-power').click();
        assert.equal(await host.locator('.cell.preview').count(), 0);
        assert.equal(await host.locator('.playing-card').count(), 5, 'Cancel costs nothing');
        await choose('paint');
        await host.locator('#cell-A3').click();
        await host.locator('#primary-action').click();
        await changed(id, 'paint');
        assert.equal(await host.evaluate(() => window.lastState.players['Power host'].total_dots), 3);
        assert.equal(await host.evaluate(() => window.lastState.current_turn), 'Power guest');
        assert.match(await host.locator('#move-summary').textContent(), /used Paint/);
        assert.equal(await host.locator('.playing-card').count(), 5);
        for (const page of pages) assert.equal(await page.evaluate(() => Object.values(window.lastState.players).some(player => 'hand' in player)), false);

        id = await prepare('shift');
        await choose('shift');
        await host.locator('#cell-F1').click();
        assert.equal(await host.locator('.power-source').count(), 0, 'Yellow cannot shift');
        await host.locator('#cell-A1').click();
        await host.locator('#cell-C3').click();
        assert.match(await host.locator('#power-target-status').textContent(), /A1 → C3/);
        await audit(host, 'Shift preview');
        await host.locator('#reset-power-targets').click();
        assert.equal(await host.locator('.power-source').count(), 0);
        await host.locator('#cell-A1').click();
        await host.locator('#cell-C3').click();
        await host.locator('#primary-action').click();
        await changed(id, 'shift');
        assert.equal(await host.evaluate(() => window.lastState.players['Power host'].score.blue), 3);
        assert.equal(await host.evaluate(() => window.lastState.board[0][0]), null);
        assert.match(await host.locator('#move-summary').textContent(), /A1 → C3/);

        id = await prepare('refresh', { exhaust: true });
        const before = await host.evaluate(() => window.lastState.board);
        const reshuffles = await host.evaluate(() => window.lastState.deck_reshuffles);
        await choose('refresh');
        assert.match(await host.locator('#power-target-status').textContent(), /discard your 4 remaining cards/);
        assert.equal(await host.locator('.power-legal').count(), 0);
        await host.locator('#primary-action').click();
        await changed(id, 'refresh');
        assert.deepEqual(await host.evaluate(() => window.lastState.board), before);
        assert.equal(await host.evaluate(() => window.lastState.deck_reshuffles), reshuffles + 1);
        assert.equal(await host.locator('.playing-card').count(), 5);

        await prepare('paint');
        await choose('paint');
        await host.locator('#cell-A3').click();
        await host.reload();
        await host.locator('#resume-button').click();
        await host.waitForFunction(() => document.querySelectorAll('.power-card').length === 3);
        assert.equal(await host.locator('.playing-card.selected').count(), 0, 'No targets replayed on resume');
        await host.locator('.playing-card:not(.power-card)').first().click();
        await host.locator('#primary-action').click();
        await host.waitForFunction(() => window.lastState.cards_played_this_turn === 1);
        await choose('paint');
        assert(await host.locator('#power-guide').isHidden(), 'Powers cannot follow a regular card');
        assert.match(await host.locator('#toast').textContent(), /whole turn/);

        id = await prepare('paint', { yellow: true });
        await choose('paint');
        await host.locator('#cell-A3').click();
        await host.locator('#primary-action').click();
        await changed(id, 'paint');
        assert.equal(await host.evaluate(() => window.lastState.current_turn), 'Power host');
        assert.equal(await host.evaluate(() => window.lastState.can_roll_dice), true);
        assert(await host.locator('#end-turn').isDisabled());
        await host.locator('#primary-action').click();
        await host.waitForFunction(() => window.lastState.current_turn === 'Power guest');

        id = await prepare('paint', { winning: true });
        await choose('paint');
        await host.locator('#cell-A3').click();
        await host.locator('#primary-action').click();
        await changed(id, 'paint');
        for (const page of pages) await page.locator('#winner-dialog').waitFor({ state: 'visible' });
        await audit(host, 'Power win results');
        await pages[1].locator('#rematch-button').click();
        await host.waitForFunction(() => document.querySelector('#rematch-status').textContent.includes('1/4'));
        await host.locator('#rematch-powers').uncheck();
        await host.waitForFunction(() => document.querySelector('#rematch-status').textContent.includes('0/4'));
        for (const page of pages) await page.locator('#rematch-button').click();
        for (const page of pages) {
            await page.waitForFunction(() => window.lastState.round_id === 2 && !window.lastState.power_cards && window.privateHand?.length === 5);
            assert.equal(await page.locator('.power-card').count(), 0);
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        }
        console.log('PASS: Power Play create/join, all three powers, preview/cancel, keyboard targets, privacy, reconnect, full-turn restrictions, yellow roll, win/rematch toggle, recycling, mobile accessibility.');
    } finally {
        for (const context of contexts) await context.close();
    }
};