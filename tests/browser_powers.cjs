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
        assert.match(await host.locator('#power-description').textContent(), /Move a blue dot/);
        assert.match(await host.locator('.power-card[data-power="shift"] .card-color').textContent(), /BLUE/);
        await host.locator('#cell-E6').click();
        assert.equal(await host.locator('.power-source').count(), 0, 'Wrong-color dot cannot shift');
        assert(!await host.locator('#cell-E6').evaluate(cell => cell.classList.contains('power-legal')));
        await host.locator('#cell-F1').click();
        assert.equal(await host.locator('.power-source').count(), 0, 'Yellow cannot shift');
        await host.locator('#cell-B3').click();
        assert.deepEqual(await host.locator('.power-legal').evaluateAll(cells => cells.map(cell => cell.id).sort()),
            ['cell-A3', 'cell-B2', 'cell-B4', 'cell-C3'], 'Only four empty orthogonal neighbors are highlighted');
        for (const destination of ['A1', 'D3', 'A2', 'A4', 'C4']) {
            await host.locator(`#cell-${destination}`).click();
            assert.equal(await host.locator('.cell.preview').count(), 0, 'Distant and diagonal targets cannot be selected');
            assert(await host.locator('#primary-action').isDisabled());
        }
        assert.equal(await host.evaluate(() => window.lastState.board[1][2]?.color), 'blue');
        assert.equal(await host.locator('.playing-card').count(), 5, 'Invalid targets cost nothing');
        await host.locator('#cell-C3').click();
        assert.equal(await host.evaluate(() => window.lastState.board[2][2]), null, 'Shift remains only a preview');
        assert.match(await host.locator('#power-target-status').textContent(), /B3 → C3/);
        await audit(host, 'Shift preview');
        await host.locator('#reset-power-targets').click();
        assert.equal(await host.locator('.power-source').count(), 0);
        await host.locator('#cell-B3').click();
        await host.locator('#cell-C3').click();
        await host.locator('#primary-action').click();
        await changed(id, 'shift');
        assert.equal(await host.evaluate(() => window.lastState.players['Power host'].score.blue), 3);
        assert.equal(await host.evaluate(() => window.lastState.board[1][2]), null);
        assert.match(await host.locator('#move-summary').textContent(), /B3 → C3/);

        await prepare('shift', { blocked: true });
        await choose('shift');
        assert.equal(await host.locator('.power-legal').count(), 0, 'Blocked dots are not selectable');
        await host.locator('#cell-A1').click();
        assert.equal(await host.locator('.power-source').count(), 0);
        assert(await host.locator('#primary-action').isDisabled());
        assert.match(await host.locator('#power-target-status').textContent(), /No blue dot has an empty neighboring square/);

        await prepare('shift', { wrong_color: true });
        await choose('shift');
        assert.equal(await host.locator('.power-legal').count(), 0);
        assert.match(await host.locator('#power-target-status').textContent(), /No blue dots to shift/);

        id = await prepare('swap', { exhaust: true });
        const before = await host.evaluate(() => window.lastState.board);
        const reshuffles = await host.evaluate(() => window.lastState.deck_reshuffles);
        const kept = await host.evaluate(() => window.privateHand.filter(card => card.power !== 'swap'));
        const guestHand = await pages[1].evaluate(() => window.privateHand);
        assert.equal(await host.locator('.power-card[data-power="refresh"]').count(), 0);
        await choose('swap');
        assert.equal(await host.locator('.power-legal').count(), 2);
        assert(await host.locator('#primary-action').isDisabled());
        for (const invalid of ['F1', 'B2']) {
            await host.locator(`#cell-${invalid}`).click();
            assert.equal(await host.locator('.power-source').count(), 0, 'Neither wild nor empty cells can swap');
        }
        await host.locator('#cell-A1').click();
        for (const invalid of ['A1', 'F1', 'B2']) {
            await host.locator(`#cell-${invalid}`).click();
            assert.equal(await host.locator('.cell.preview').count(), 0);
            assert(await host.locator('#primary-action').isDisabled());
        }
        await host.locator('#cell-F6').focus();
        await host.keyboard.press('Enter');
        assert.equal(await host.locator('.cell.preview').count(), 2);
        assert.match(await host.locator('#cell-A1').getAttribute('aria-label'), /preview green/);
        assert.match(await host.locator('#cell-F6').getAttribute('aria-label'), /preview blue/);
        assert.equal(await host.locator('#cell-A1').getAttribute('aria-pressed'), 'true');
        assert.equal(await host.locator('#cell-F6').getAttribute('aria-pressed'), 'true');
        assert.deepEqual(await host.evaluate(() => window.lastState.board), before, 'Swap preview does not mutate board');
        assert.match(await host.locator('#power-target-status').textContent(), /A1 ⇄ F6/);
        await audit(host, 'Swap both-dot preview at 320px');
        await host.locator('#reset-power-targets').click();
        assert.equal(await host.locator('.cell.preview').count(), 0);
        await host.locator('#cell-A1').click();
        await host.locator('#cell-F6').click();
        await host.locator('#cancel-power').click();
        assert.equal(await host.locator('.cell.preview').count(), 0);
        assert.deepEqual(await host.evaluate(() => window.lastState.board), before);
        await choose('swap');
        await host.locator('#cell-A1').click();
        await host.locator('#cell-F6').click();
        await host.locator('#primary-action').click();
        await changed(id, 'swap');
        for (const page of pages) {
            await page.waitForFunction(() => window.lastState.board[0][0]?.color === 'green'
                && window.lastState.board[5][5]?.color === 'blue');
        }
        assert.equal(await host.evaluate(() => window.lastState.board[5][0].color), 'yellow');
        assert.equal(await host.evaluate(() => window.lastState.last_move.points), 0);
        assert.equal(await host.evaluate(() => window.lastState.current_turn), 'Power guest');
        assert.match(await host.locator('#move-summary').textContent(), /used Swap · swapped A1 ⇄ F6/);
        assert.equal(await host.evaluate(() => window.lastState.deck_reshuffles), reshuffles + 1);
        assert.equal(await host.locator('.playing-card').count(), 5);
        assert.deepEqual(await host.evaluate(() => window.privateHand.slice(0, 4)), kept);
        assert.deepEqual(await pages[1].evaluate(() => window.privateHand), guestHand);

        id = await prepare('swap', { matching: true });
        await choose('swap');
        await host.locator('#cell-A1').click();
        await host.locator('#cell-F6').click();
        await host.locator('#primary-action').click();
        await changed(id, 'swap');
        assert.equal(await host.evaluate(() => window.lastState.last_move.lines), 2);
        assert.equal(await host.evaluate(() => window.lastState.last_move.points), 6);
        assert.equal(await host.evaluate(() => window.lastState.players['Power host'].score.blue), 3);
        assert.equal(await host.evaluate(() => window.lastState.players['Power host'].score.green), 3);

        await prepare('swap', { blocked: true });
        await choose('swap');
        assert.equal(await host.locator('.power-legal').count(), 0);
        assert(await host.locator('#primary-action').isDisabled());
        assert.match(await host.locator('#power-target-status').textContent(), /Swap needs two regular dots/);

        await prepare('swap', { full: true });
        await choose('swap');
        assert.equal(await host.locator('.power-legal').count(), 36, 'Swap works without empty squares');
        await host.locator('#cell-A1').click();
        await host.locator('#cell-F6').click();
        assert(!await host.locator('#primary-action').isDisabled());
        await host.locator('#cancel-power').click();

        const hasClass = (page, id, name) => page.locator(`#cell-${id}`).evaluate((cell, name) => cell.classList.contains(name), name);
        id = await prepare('block');
        await choose('block');
        assert.match(await host.locator('.power-card[data-power="block"] .card-color').textContent(), /FULL TURN/);
        assert.equal(await host.locator('.power-legal').count(), 34, 'Every empty square can be blocked');
        await host.locator('#cell-A1').click();
        assert(!await hasClass(host, 'A1', 'blocked'), 'Occupied squares cannot be blocked');
        await host.locator('#cell-A3').click();
        assert(await hasClass(host, 'A3', 'blocked'));
        assert.match(await host.locator('#power-target-status').textContent(), /Blocking A3/);
        assert.deepEqual(await host.evaluate(() => window.lastState.blocks), [], 'Block remains only a preview');
        await audit(host, 'Block preview at 320px');
        await host.locator('#primary-action').click();
        await changed(id, 'block');
        for (const page of pages) await page.waitForFunction(() => window.lastState.blocks?.[0]?.location === 'A3');
        assert(await hasClass(pages[1], 'A3', 'blocked'));
        assert.match(await pages[1].locator('#cell-A3').getAttribute('aria-label'), /blocked by Power host/);
        assert.match(await host.locator('#move-summary').textContent(), /used Block · blocked A3/);
        assert.equal(await host.evaluate(() => window.lastState.current_turn), 'Power guest');

        await prepare('tax');
        await choose('tax');
        assert(await host.locator('#power-players').isHidden());
        assert.match(await host.locator('#power-target-status').textContent(), /Nobody to tax/);
        assert(await host.locator('#primary-action').isDisabled());
        await host.locator('#cancel-power').click();

        id = await prepare('tax', { leaders: true });
        await choose('tax');
        assert.equal(await host.locator('.power-legal').count(), 0, 'Tax targets players, not squares');
        assert.deepEqual(await host.locator('#power-players button').allTextContents(), ['Power guest · 3 red'],
            'Only the leader can be taxed');
        assert(await host.locator('#primary-action').isDisabled());
        await host.locator('#power-players button').click();
        assert.match(await host.locator('#power-target-status').textContent(), /from Power guest/);
        await audit(host, 'Tax target at 320px');
        await host.locator('#primary-action').click();
        await changed(id, 'tax');
        assert.equal(await host.evaluate(() => window.lastState.players['Power guest'].score.red), 1);
        assert.equal(await host.evaluate(() => window.lastState.players['Power guest'].total_dots), 1);
        assert.equal(await host.evaluate(() => window.lastState.players['Power host'].total_dots), 0);
        assert.match(await host.locator('#move-summary').textContent(), /used Tax · took 2 red from Power guest/);
        await pages[1].waitForFunction(() => window.lastState.last_move?.power === 'tax');
        assert.match(await pages[1].locator('#activity-list').textContent(), /Power guest lost 2 dots to Tax/);

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
        console.log('PASS: Power Play create/join, all five powers, preview/cancel, keyboard targets, privacy, reconnect, full-turn restrictions, yellow roll, win/rematch toggle, recycling, mobile accessibility.');
    } finally {
        for (const context of contexts) await context.close();
    }
};