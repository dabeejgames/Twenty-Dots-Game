/* Deterministic real-backend replay tests. Starts and stops a private fixture server. */
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const http = require('node:http');
const path = require('node:path');
const assert = require('node:assert/strict');
const engines = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const key = randomBytes(24).toString('hex');
const port = process.env.BROWSER_FIXTURE_PORT || '5001';
const base = `http://127.0.0.1:${port}`;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

function request(url, payload) {
    return new Promise((resolve, reject) => {
        const body = payload ? JSON.stringify(payload) : null;
        const req = http.request(url, { method: body ? 'POST' : 'GET', headers: {
            'X-Fixture-Key': key, ...(body ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } : {}),
        } }, response => {
            let text = '';
            response.setEncoding('utf8');
            response.on('data', data => { text += data; });
            response.on('end', () => resolve({ status: response.statusCode, text }));
            response.on('error', reject);
        });
        req.on('error', reject);
        req.setTimeout(5000, () => req.destroy(new Error('Fixture HTTP timeout')));
        req.end(body);
    });
}

async function audit(page, label) {
    await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(document.getAnimations().filter(a => a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})));
    });
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    assert.deepEqual(result.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.failureSummary) })), [], label);
}

(async () => {
    const server = spawn(process.env.TEST_PYTHON || 'python', ['tests/browser_fixture_server.py'], {
        cwd: path.join(__dirname, '..'), env: { ...process.env, BROWSER_FIXTURE_KEY: key, BROWSER_FIXTURE_PORT: port },
        stdio: ['ignore', 'pipe', 'pipe'],
    });
    let output = '', startupError;
    server.on('error', error => { startupError = error; });
    for (const stream of [server.stdout, server.stderr]) stream.on('data', data => { output = (output + data).slice(-8000); });
    let browser;
    try {
        let ready = false;
        for (let i = 0; i < 100; i++) {
            if (startupError) throw startupError;
            if (server.exitCode !== null) throw new Error(`Fixture server exited: ${output}`);
            try { if ((await request(`${base}/favicon.ico`)).status === 204) { ready = true; break; } } catch {}
            await pause(100);
        }
        assert(ready, `Fixture server did not start: ${output}`);
        browser = await engines[process.env.PLAYWRIGHT_BROWSER || 'chromium'].launch();
        const pages = [], exceptions = [];
        for (const [index, name] of ['Alex', 'Maya', 'Jules', '<img onerror=alert(1)>'].entries()) {
            const context = await browser.newContext({ viewport: { width: index === 3 ? 1440 : 320, height: 900 } });
            await context.addInitScript(() => {
                let exposed;
                window.observed = [];
                window.particleCount = 0;
                const animate = Element.prototype.animate;
                Element.prototype.animate = function (...args) {
                    if (this.classList.contains('collection-particle')) window.particleCount++;
                    return animate.apply(this, args);
                };
                Object.defineProperty(window, 'io', { configurable: true, get: () => exposed, set: original => {
                    exposed = Object.assign((...args) => {
                        const socket = original(...args);
                        window.testSocket = socket;
                        socket.onAny((event, data) => {
                            window.observed.push(event);
                            if (event === 'game_started' || event === 'game_updated') window.lastState = data;
                        });
                        return socket;
                    }, original);
                } });
            });
            const page = await context.newPage();
            page.on('pageerror', error => exceptions.push(error.message));
            pages.push(page);
            const code = index ? await pages[0].locator('#lobby-code').textContent() : null;
            await page.goto(`${base}/web_client.html${code ? `?room=${code}` : ''}`);
            await page.waitForFunction(() => typeof window.io === 'function');
            await page.locator('#player-name').fill(name);
            if (!index) await page.locator('input[value="4"]').check();
            await page.locator('#start-button').click();
            await page.locator(index === 3 ? '#game-screen' : '#lobby-screen').waitFor({ state: 'visible' });
        }
        const [host, guest, third, fourth] = pages;
        for (const page of pages) await page.waitForFunction(() => window.lastState && document.querySelectorAll('.playing-card').length === 5);
        const code = await host.locator('#game-room-code').textContent();
        const token = await host.evaluate(() => JSON.parse(localStorage.getItem('twenty-dots.seat.v1')).resume_token);
        async function prepare(page, options = {}) {
            const player = await page.evaluate(() => JSON.parse(localStorage.getItem('twenty-dots.seat.v1')).player_name);
            const response = await request(`${base}/__test__/position`, { game_id: code, player, ...options });
            assert.equal(response.status, 200);
            const card = JSON.parse(response.text);
            await page.waitForFunction(({ location }) => window.lastState.board[location.charCodeAt(0) - 65][Number(location[1]) - 1]?.color === 'yellow' && !window.lastState.can_roll_dice, card);
            return card;
        }
        async function playPrepared(page, options) {
            const card = await prepare(page, options);
            await page.getByRole('button', { name: `${card.color}, ${card.location}`, exact: true }).click();
            // Replacements are drawn after two cards, not after the first card.
            if (options.exhaust) await page.getByRole('button', { name: `${card.spare.color}, ${card.spare.location}`, exact: true }).click();
            await page.locator('#primary-action').click();
            await page.waitForFunction(() => window.lastState.last_move?.points === 6);
            return card;
        }
        async function round(number, starter) {
            for (const page of pages) {
                await page.waitForFunction(n => window.lastState.round_id === n && !document.querySelector('#winner-dialog').open && document.querySelectorAll('.playing-card').length === 5, number);
                assert.equal(await page.evaluate(() => window.lastState.current_turn), starter);
                assert.equal(await page.locator('#game-room-code').textContent(), code);
                assert.equal(await page.locator('.playing-card.selected').count(), 0);
            }
        }
        async function allReady() {
            for (const page of pages) await page.locator('#rematch-button').click();
        }

        await host.locator('#preferences-button').click();
        assert.equal(await host.locator('#pref-sound').isChecked(), true);
        assert.equal(await host.locator('#pref-haptics').isChecked(), false);
        await host.locator('#pref-motion').check();
        await host.locator('#pref-sound').uncheck();
        await host.locator('#pref-sound').check();
        await audit(host, 'Preferences accessibility');
        await host.keyboard.press('Escape');
        await guest.emulateMedia({ reducedMotion: 'reduce' });
        await guest.waitForFunction(() => document.body.classList.contains('reduce-motion'));

        await host.locator('#game-screen [data-reaction="nice_move"]').click();
        await guest.waitForFunction(() => document.querySelector('#reaction-message').textContent === 'Alex: Nice move!');
        assert(await host.locator('#game-screen [data-reaction="close_one"]').isDisabled());
        await guest.locator('#mute-reactions').click();
        await fourth.locator('#game-screen [data-reaction="well_played"]').click();
        await host.waitForFunction(() => document.querySelector('#reaction-message').textContent.includes('<img onerror=alert(1)>: Well played!'));
        assert.equal(await host.locator('#reaction-message img').count(), 0);
        assert.equal(await guest.locator('#reaction-message').textContent(), '');
        await host.waitForFunction(() => !document.querySelector('#game-screen [data-reaction="close_one"]').disabled);
        // Offscreen effects intentionally do not animate; keep the destination visible.
        await fourth.evaluate(() => window.scrollTo(0, 0));

        await playPrepared(host, { exhaust: true });
        await host.waitForFunction(() => window.lastState.deck_reshuffles === 1);
        assert.match(await host.locator('#toast').textContent(), /Deck refreshed/);
        assert.match(await host.locator('#move-summary').textContent(), /Double line/);
        assert.equal(await host.evaluate(() => window.particleCount), 0, 'User reduced motion suppresses collection animation');
        assert.equal(await guest.evaluate(() => window.particleCount), 0, 'OS reduced motion suppresses collection animation');
        await fourth.waitForFunction(() => window.particleCount > 0);
        assert.equal(await host.locator('.playing-card').count(), 5);
        assert.equal(await host.locator('.last-collected').count(), 5);
        const animations = await fourth.evaluate(() => window.particleCount);
        await fourth.evaluate(() => window.testSocket.onevent({ data: ['game_updated', window.lastState] }));
        assert.equal(await fourth.evaluate(() => window.particleCount), animations, 'Duplicate snapshot does not replay effects');

        await playPrepared(host, { winning: true });
        for (const page of pages) await page.locator('#winner-dialog').waitFor({ state: 'visible' });
        assert.match(await host.locator('#move-summary').textContent(), /Wild finish/);
        await audit(host, 'Round result at 320px');
        assert(await guest.locator('#rematch-host-options').isHidden());
        await host.locator('#winner-dialog [data-reaction="rematch"]').click();
        await third.waitForFunction(() => document.querySelector('#winner-dialog .reaction-message').textContent === 'Alex: Rematch?');
        await host.reload();
        await host.locator('#resume-button').click();
        await host.locator('#winner-dialog').waitFor({ state: 'visible' });
        assert.equal(await host.evaluate(() => window.particleCount), 0, 'Terminal resume does not animate historic move');
        assert(await host.evaluate(() => document.body.classList.contains('reduce-motion')));
        assert.equal(await host.evaluate(() => JSON.parse(localStorage.getItem('twenty-dots.seat.v1')).resume_token), token);
        await guest.locator('#rematch-button').click();
        await host.waitForFunction(() => document.querySelector('#rematch-status').textContent.includes('1/4 ready'));
        await host.locator('#rematch-mode').selectOption('five_colors');
        await guest.waitForFunction(() => document.querySelector('#rematch-button').getAttribute('aria-pressed') === 'false');
        await host.waitForFunction(() => document.querySelector('#rematch-status').textContent.includes('0/4 ready'));
        await allReady();
        await round(2, 'Maya');
        assert.equal(await host.evaluate(() => window.lastState.game_mode), 'five_colors');
        assert.equal(await host.evaluate(() => window.lastState.series.wins.Alex), 1);
        assert.equal(await host.evaluate(() => window.lastState.deck_reshuffles), 0);

        await playPrepared(host, { winning: true });
        for (const page of pages) await page.locator('#winner-dialog').waitFor({ state: 'visible' });
        assert.match(await host.locator('#series-result').textContent(), /Alex wins game night 1/);
        assert.equal(await host.locator('#result-eyebrow').textContent(), 'GAME NIGHT CHAMPION');
        await audit(host, 'Series result');
        await allReady();
        await round(3, 'Jules');
        assert.equal(await host.evaluate(() => window.lastState.series.number), 2);
        assert.equal(await host.evaluate(() => window.lastState.series.round), 1);
        assert.deepEqual(await host.evaluate(() => Object.values(window.lastState.series.wins)), [0, 0, 0, 0]);
        assert.equal(await host.evaluate(() => JSON.parse(localStorage.getItem('twenty-dots.seat.v1')).resume_token), token);
        await guest.reload();
        await guest.locator('#resume-button').click();
        await guest.locator('#game-screen').waitFor({ state: 'visible' });
        assert.equal(await guest.locator('#mute-reactions').getAttribute('aria-pressed'), 'true');
        await audit(host, 'New series table');
        for (const page of pages) assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await require('./browser_powers.cjs')(browser, base, request, audit, exceptions);
        assert.deepEqual(exceptions, []);
        console.log(`PASS (${process.env.PLAYWRIGHT_BROWSER || 'chromium'}): real-backend deck recycling, double-line/wild feedback, motion preferences/dedup, reactions/cooldown/mute, terminal refresh, host goal/readiness reset, two rematches, rotating starters, fresh series, accessibility.`);
    } finally {
        if (browser) await browser.close();
        server.kill();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });