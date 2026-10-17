/* Invoked by the replay runner against its authenticated, loopback fixture server. */
const assert = require('node:assert/strict');

module.exports = async function testStrategy(browser, base, request, audit, errors) {
    const contexts = [];
    async function player(name, room) {
        const context = await browser.newContext({ viewport: { width: 320, height: 900 }, reducedMotion: 'reduce' });
        contexts.push(context);
        await context.addInitScript(() => {
            let exposed;
            Object.defineProperty(window, 'io', { configurable: true, get: () => exposed, set: original => {
                exposed = Object.assign((...args) => {
                    const socket = original(...args);
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
        if (!room) await page.locator('#strategy-rules').check();
        await page.locator('#start-button').click();
        return page;
    }
    try {
        const host = await player('Planner');
        await host.locator('#lobby-screen').waitFor({ state: 'visible' });
        assert.match(await host.locator('#lobby-count').textContent(), /Strategy rules/);
        const code = await host.locator('#lobby-code').textContent();
        const guest = await player('Rival', code);
        for (const page of [host, guest]) await page.waitForFunction(() => window.lastState?.strategy_rules && window.privateHand?.length === 5);
        async function prepare(options = {}) {
            const snapshots = await host.evaluate(() => window.snapshots);
            const result = await request(`${base}/__test__/position`, { game_id: code, player: 'Planner', strategy: true, ...options });
            assert.equal(result.status, 200, result.text);
            await host.waitForFunction(n => window.snapshots > n, snapshots);
        }

        // Wild choice: roll two squares, then choose one of them.
        await prepare({ roll: true });
        assert.match(await host.locator('#primary-action').textContent(), /Roll the wild dice/);
        await host.locator('#primary-action').click();
        await host.waitForFunction(() => window.lastState.wild_options?.length === 2);
        const options = await host.evaluate(() => window.lastState.wild_options);
        assert.equal(await host.locator('.cell.wild-option').count(), 2);
        await guest.waitForFunction(() => document.querySelectorAll('.cell.wild-option').length === 2);
        assert(await host.locator('#primary-action').isDisabled(), 'A square must be chosen first');
        assert.match(await host.locator('#turn-title').textContent(), /Choose the wild/);
        assert(await host.evaluate(() => window.lastState.board.flat().every(cell => !cell)), 'Rolling places nothing yet');
        const other = ['A1', 'B1', 'C1', 'D1'].find(cell => !options.includes(cell));
        await host.locator(`#cell-${other}`).click();
        assert.match(await host.locator('#toast').textContent(), /for the wild/);
        await host.locator(`#cell-${options[1]}`).click();
        assert.equal(await host.locator(`#cell-${options[1]}`).getAttribute('aria-pressed'), 'true');
        assert.match(await host.locator('#primary-action').textContent(), new RegExp(`Place wild at ${options[1]}`));
        await audit(host, 'Wild choice at 320px');
        await host.locator('#primary-action').click();
        await host.waitForFunction(() => !window.lastState.wild_options?.length && window.lastState.yellow_dot_position);
        assert.equal(await host.evaluate(() => window.lastState.yellow_dot_position.join('')), options[1]);
        assert.equal(await host.evaluate(() => window.lastState.can_roll_dice), false);

        // Market: play the face-up red A3 to finish red A1-A2.
        await prepare();
        for (const page of [host, guest]) {
            await page.locator('#market-panel').waitFor({ state: 'visible' });
            assert.equal(await page.locator('.market-card').count(), 3);
        }
        const a3 = host.locator('.market-card[aria-label*="A3"]');
        await a3.click();
        assert.equal(await a3.getAttribute('aria-pressed'), 'true');
        assert(await host.locator('#cell-A3').evaluate(cell => cell.classList.contains('preview')));
        assert.match(await host.locator('#cell-A3').getAttribute('aria-label'), /market card/);
        assert.match(await host.locator('#primary-action').textContent(), /Play 1 card/);
        await audit(host, 'Market selection at 320px');
        await host.locator('#primary-action').click();
        await host.waitForFunction(() => window.lastState.market_played);
        assert.equal(await host.evaluate(() => window.lastState.players.Planner.score.red), 3);
        assert.equal(await host.evaluate(() => window.lastState.market.length), 3);
        assert.equal(await host.evaluate(() => window.privateHand.length), 5, 'Market play keeps the hand');
        assert.match(await host.locator('#market-note').textContent(), /used the market/);
        assert.equal(await host.locator('.market-card:not([disabled])').count(), 0, 'One market card per turn');
        assert.equal(await host.locator('.market-card[aria-label*="red, A3"]').count(), 0);
        // The second play comes from the hand and ends the turn.
        await host.locator('.playing-card:not(.power-card):not(.market-card)').first().click();
        await host.locator('#primary-action').click();
        await host.waitForFunction(() => window.lastState.current_turn === 'Rival');
        await guest.waitForFunction(() => window.lastState.current_turn === 'Rival' && !window.lastState.market_played);
        assert.equal(await guest.locator('.market-card:not([disabled])').count(), 3, 'The next player can use the market');
        for (const page of [host, guest]) assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        console.log('PASS: Strategy rules lobby option, two-square wild choice, face-up market play once per turn, hand kept, market refill, mobile accessibility.');
    } finally {
        for (const context of contexts) await context.close();
    }
};
