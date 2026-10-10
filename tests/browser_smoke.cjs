/* Run against a local game_server.py: npm test --prefix tests. */
const engines = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

const baseURL = process.env.GAME_URL || 'http://127.0.0.1:5000/web_client.html';
const artifacts = path.join(__dirname, '..', 'test-results');
const errors = [];
fs.mkdirSync(artifacts, { recursive: true });

async function fits(page, label) {
    const geometry = await page.evaluate(() => ({
        viewport: innerWidth, document: document.documentElement.scrollWidth,
        cells: Array.from(document.querySelectorAll('#board .cell')).map(cell => {
            const rect = cell.getBoundingClientRect();
            return { x: rect.x, right: rect.right, width: rect.width, height: rect.height };
        }),
    }));
    assert(geometry.document <= geometry.viewport + 1, `${label}: horizontal page overflow (${JSON.stringify(geometry)})`);
    for (const cell of geometry.cells) {
        assert(cell.x >= 0 && cell.right <= geometry.viewport, `${label}: board cropped`);
        assert(cell.width >= 24 && cell.height >= 24, `${label}: board target below 24px`);
    }
}

async function accessible(page, label) {
    // Audit the settled interface, not a translucent frame of its entry animation.
    await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(document.getAnimations()
            .filter(animation => animation.effect.getTiming().iterations !== Infinity)
            .map(animation => animation.finished.catch(() => {})));
    });
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    const violations = result.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) }));
    assert.deepEqual(violations, [], `${label}: accessibility violations\n${JSON.stringify(violations, null, 2)}`);
}

async function rollIfRequired(page) {
    for (let i = 0; i < 20; i++) {
        const button = page.locator('#primary-action');
        if (!(await button.textContent()).includes('Roll the wild')) return;
        await button.click();
        await page.waitForFunction(() => !document.querySelector('#primary-action').textContent.includes('One moment'));
    }
    throw new Error('Wild dice never settled');
}

(async () => {
    const browser = await engines[process.env.PLAYWRIGHT_BROWSER || 'chromium'].launch({ headless: true });
    const contexts = [];
    async function player(width, height) {
        const context = await browser.newContext({ viewport: { width, height }, isMobile: width < 600, hasTouch: width < 600 });
        contexts.push(context);
        await context.addInitScript(() => {
            // Observe actual transport for disconnect and rejected-request regressions.
            let exposed;
            Object.defineProperty(window, 'io', {
                configurable: true,
                get: () => exposed,
                set: original => {
                    exposed = Object.assign((...args) => {
                        const socket = original(...args);
                        window.testSocket = socket;
                        return socket;
                    }, original);
                },
            });
        });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(baseURL);
        await page.waitForFunction(() => typeof window.io === 'function');
        return page;
    }

    try {
        const host = await player(390, 844);
        await fits(host, '390px home');
        await accessible(host, 'Home');
        await host.screenshot({ path: path.join(artifacts, 'home-mobile.png'), fullPage: true });
        await host.locator('#rules-button').click();
        assert(await host.locator('#rules-dialog').isVisible());
        await accessible(host, 'Rules dialog');
        await host.keyboard.press('Escape');
        await host.locator('#player-name').fill('Alex');
        await host.locator('input[name="player_count"][value="4"]').check();
        await host.locator('#start-button').click();
        await host.locator('#lobby-screen').waitFor({ state: 'visible' });
        const code = (await host.locator('#lobby-code').textContent()).trim();
        assert.match(code, /^[A-Z2-9]{6}$/);
        assert.equal(await host.locator('.seat-empty').count(), 3);
        await fits(host, '390px lobby');
        await accessible(host, 'Lobby');
        await host.screenshot({ path: path.join(artifacts, 'lobby-mobile.png'), fullPage: true });

        const guests = [];
        for (const [name, width] of [['Maya', 375], ['Jules', 320], ['<img onerror=alert(1)>', 1440]]) {
            const guest = await player(width, width < 600 ? 812 : 1000);
            await guest.goto(`${baseURL}?room=${code}`);
            await guest.locator('#player-name').fill(name);
            assert.equal(await guest.locator('#room-code').inputValue(), code);
            assert.equal(await guest.locator('#tab-join').getAttribute('aria-selected'), 'true');
            await guest.locator('#start-button').click();
            guests.push(guest);
        }
        for (const page of [host, ...guests]) {
            await page.locator('#game-screen').waitFor({ state: 'visible' });
            await page.waitForFunction(() => document.querySelectorAll('#hand .playing-card').length === 5);
            assert.equal(await page.locator('#board .cell').count(), 36);
            assert.equal(await page.locator('#score-list .score-card').count(), 4);
            assert.equal(await page.locator('#score-list img').count(), 0, 'Names must never become HTML');
            await fits(page, `${page.viewportSize().width}px four-player table`);
        }
        await accessible(host, 'Four-player mobile table');
        await accessible(guests[2], 'Desktop table');
        await host.screenshot({ path: path.join(artifacts, 'game-mobile.png'), fullPage: true });
        await guests[2].screenshot({ path: path.join(artifacts, 'game-desktop.png'), fullPage: true });

        // Waiting players can plan, but never submit a move.
        await guests[0].locator('.playing-card').first().click();
        assert.equal(await guests[0].locator('.cell.preview').count(), 1);
        assert(await guests[0].locator('#primary-action').isDisabled());
        await rollIfRequired(host);
        const cards = await host.locator('.card-coordinate').allTextContents();
        const second = cards.findIndex((location, index) => index > 0 && location !== cards[0]);
        assert(second > 0, 'Dealt hand should have distinct positions');
        await host.locator('.playing-card').first().click();
        await host.locator('.playing-card').nth(second).click();
        assert.equal(await host.locator('.cell.preview').count(), 2);
        await host.locator('#primary-action').click();
        await host.waitForFunction(() => !document.querySelector('#primary-action').textContent.includes('One moment'));
        await rollIfRequired(host);
        await guests[0].waitForFunction(() => document.querySelector('#turn-badge').textContent === 'YOUR TURN');
        assert.equal(await guests[0].locator('.playing-card.selected').count(), 0, 'Planning selections reset on a new turn');
        assert.equal(await host.locator('.playing-card').count(), 5, 'Hand stays visible between turns');
        await guests[0].locator('#end-turn').click();
        await guests[1].waitForFunction(() => document.querySelector('#turn-badge').textContent === 'YOUR TURN');

        // Refresh requires a token-backed rejoin and restores the private hand.
        const refreshing = guests[1];
        await refreshing.reload();
        await refreshing.locator('#resume-button').click();
        await refreshing.locator('#game-screen').waitFor({ state: 'visible' });
        await refreshing.waitForFunction(() => document.querySelectorAll('.playing-card').length === 5);
        assert.equal(await refreshing.locator('#turn-badge').textContent(), 'YOUR TURN');
        await fits(refreshing, '320px rejoined table');

        // An invalid move must restore buttons rather than leave the hand locked.
        await refreshing.evaluate(() => window.testSocket.emit('play_cards', {
            game_id: JSON.parse(localStorage.getItem('twenty-dots.seat.v1')).game_id,
            cards: [],
        }));
        await refreshing.locator('#toast').waitFor({ state: 'visible' });
        assert(await refreshing.locator('.playing-card').first().isEnabled());

        // Offline/online recovery (no optimistic resends).
        await host.context().setOffline(true);
        await host.waitForFunction(() => !window.testSocket.connected, null, { timeout: 40000 });
        assert(await host.locator('#primary-action').isDisabled());
        await host.context().setOffline(false);
        await host.waitForFunction(() => document.querySelector('#connection').dataset.state === 'connected');
        assert.equal(await host.locator('.playing-card').count(), 5);

        // Leave/rejoin preserves started seats. Desktop remains usable at narrower widths.
        await host.locator('#game-screen .leave-button').click();
        await host.locator('#confirm-leave').click();
        await host.locator('#home-screen').waitFor({ state: 'visible' });
        await host.locator('#resume-button').click();
        await host.locator('#game-screen').waitFor({ state: 'visible' });
        for (const width of [320, 360, 390, 768, 1024, 1440]) {
            await guests[2].setViewportSize({ width, height: 900 });
            await fits(guests[2], `${width}px responsive table`);
        }
        await guests[2].setViewportSize({ width: 844, height: 390 });
        await fits(guests[2], 'Phone landscape');

        // Solo mode uses the same game interface and real AI turns.
        const solo = await player(390, 844);
        await solo.locator('#tab-solo').click();
        await solo.locator('#player-name').fill('Practice');
        await solo.locator('#game-mode').selectOption('five_with_yellow');
        await solo.locator('#start-button').click();
        await solo.locator('#game-screen').waitFor({ state: 'visible' });
        await solo.waitForFunction(() => document.querySelectorAll('.playing-card').length === 5);
        assert.equal(await solo.locator('#game-title').textContent(), 'WILD AMBITION');
        await rollIfRequired(solo);
        await solo.locator('#end-turn').click();
        await solo.waitForFunction(() => document.querySelector('#turn-badge').textContent === 'YOUR TURN', null, { timeout: 30000 });
        // Presentation-only winner fixture; scoring and terminal state are verified in Python tests.
        await solo.evaluate(() => window.testSocket.onevent({ data: ['game_over', { winner: 'Practice', condition: 'five_with_yellow' }] }));
        await solo.locator('#winner-dialog').waitFor({ state: 'visible' });
        await accessible(solo, 'Winner dialog');
        await solo.screenshot({ path: path.join(artifacts, 'winner-mobile.png'), fullPage: true });
        await solo.locator('#new-game').click();
        assert.equal(await solo.locator('#tab-create').getAttribute('aria-selected'), 'true');
        assert.equal(await solo.locator('#game-mode').inputValue(), 'five_with_yellow');

        // Full rooms wait for disconnected players and start for everyone on resume.
        const lobbyHost = await player(390, 844);
        await lobbyHost.locator('#player-name').fill('Returning host');
        await lobbyHost.locator('#start-button').click();
        await lobbyHost.locator('#lobby-screen').waitFor({ state: 'visible' });
        const waitingCode = await lobbyHost.locator('#lobby-code').textContent();
        await lobbyHost.evaluate(() => window.testSocket.disconnect());
        const lobbyGuest = await player(390, 844);
        await lobbyGuest.goto(`${baseURL}?room=${waitingCode}`);
        await lobbyGuest.locator('#player-name').fill('Waiting friend');
        await lobbyGuest.locator('#start-button').click();
        await lobbyGuest.locator('#lobby-screen').waitFor({ state: 'visible' });
        assert.match(await lobbyGuest.locator('#lobby-status').textContent(), /reconnect/);
        await lobbyHost.locator('#retry-button').click();
        for (const page of [lobbyHost, lobbyGuest]) {
            await page.locator('#game-screen').waitFor({ state: 'visible' });
            await page.waitForFunction(() => document.querySelectorAll('.playing-card').length === 5);
        }

        const desktopHome = await player(1440, 1000);
        await fits(desktopHome, 'Desktop home');
        await accessible(desktopHome, 'Desktop home');
        await desktopHome.screenshot({ path: path.join(artifacts, 'home-desktop.png'), fullPage: true });

        // Missing invites report a useful error rather than creating a phantom room.
        const missing = await player(390, 844);
        await missing.goto(`${baseURL}?room=missing-${Date.now()}`);
        await missing.locator('#player-name').fill('No room');
        await missing.locator('#start-button').click();
        await missing.locator('#form-error').waitFor({ state: 'visible' });
        assert.match(await missing.locator('#form-error').textContent(), /Game not found/);
        assert(await missing.locator('#start-button').isEnabled());
        assert.deepEqual(errors, [], `Browser exceptions: ${errors.join(', ')}`);
        console.log(`PASS (${process.env.PLAYWRIGHT_BROWSER || 'chromium'}): mobile/desktop layouts, accessibility, 4 real players, private hands, previews, turns, refresh/rejoin, offline recovery, leave/rejoin, AI practice, winner UI, lobby recovery and invalid invites.`);
        console.log(`Screenshots: ${artifacts}`);
    } finally {
        for (const context of contexts) await context.close();
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });