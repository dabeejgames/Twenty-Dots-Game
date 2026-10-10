/* Run against a local game server: npm run test:music --prefix tests. */
const engines = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const baseURL = process.env.GAME_URL || 'http://127.0.0.1:5000/web_client.html';
const key = 'twenty-dots.preferences.v1';

(async () => {
    const browser = await engines[process.env.PLAYWRIGHT_BROWSER || 'chromium'].launch();
    const errors = [];
    async function page(options = {}) {
        const context = await browser.newContext({ viewport: { width: 320, height: 900 } });
        if (options.noSongs) await context.route('**/*.mp3', route => route.abort());
        await context.addInitScript(({ options, key }) => {
            if (options.saved !== undefined) localStorage.setItem(key, JSON.stringify(options.saved));
            // Observe the real music engine without a production debug API.
            let Music;
            Object.defineProperty(window, 'TableMusic', {
                configurable: true, get: () => Music,
                set: Original => { Music = new Proxy(Original, { construct(Target, args) {
                    const instance = new Target(...args);
                    window.testMusic = instance;
                    return instance;
                } }); },
            });
            if (options.unsupported) {
                window.AudioContext = undefined;
                window.webkitAudioContext = undefined;
            } else if (options.blocked) {
                const Context = window.AudioContext || window.webkitAudioContext;
                window.AudioContext = new Proxy(Context, { construct(Target, args) {
                    const audio = new Target(...args);
                    audio.suspend();
                    audio.resume = () => Promise.reject(new Error('Playback requires permission'));
                    return audio;
                } });
            }
        }, { options, key });
        const tab = await context.newPage();
        tab.on('pageerror', error => errors.push(error.message));
        await tab.goto(baseURL);
        await tab.waitForFunction(() => Boolean(window.testMusic));
        return tab;
    }
    async function status(tab, value) {
        await tab.waitForFunction(expected => window.testMusic.status === expected, value);
    }
    async function audit(tab) {
        await tab.evaluate(async () => {
            await document.fonts.ready;
            await Promise.all(document.getAnimations().filter(a => a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})));
        });
        const results = await new AxeBuilder({ page: tab }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
        assert.deepEqual(results.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.failureSummary) })), []);
        assert(await tab.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    }
    try {
        const tab = await page();
        assert.equal(await tab.evaluate(() => window.testMusic.context), null, 'No audio context/autoplay on load');
        await tab.locator('#home-screen [data-preferences]').click();
        assert.equal(await tab.locator('#pref-music').isChecked(), false);
        assert.equal(await tab.locator('#pref-music-volume').inputValue(), '35');
        await tab.locator('#pref-music').check();
        // Playwright's Windows WebKit build does not expose Web Audio. Verify the
        // honest fallback there; never report an audio-output check as passing.
        if (!await tab.evaluate(() => Boolean(window.AudioContext || window.webkitAudioContext))) {
            await status(tab, 'unavailable');
            assert.equal(await tab.evaluate(() => window.testMusic.timer), null);
            await tab.locator('#pref-music-volume').focus();
            await tab.keyboard.press('End');
            assert.equal(await tab.locator('#music-volume-value').textContent(), '100%');
            await audit(tab);
            await tab.locator('#pref-music').uncheck();
            await status(tab, 'off');
            await tab.reload();
            await tab.locator('#home-screen [data-preferences]').click();
            assert.equal(await tab.locator('#pref-music').isChecked(), false);
            assert.equal(await tab.locator('#pref-music-volume').inputValue(), '100');
            await tab.keyboard.press('Escape');
            await tab.locator('#player-name').fill('Quiet browser');
            await tab.locator('#start-button').click();
            await tab.locator('#lobby-screen').waitFor({ state: 'visible' });
            assert.deepEqual(errors, []);
            console.log(`PASS (${process.env.PLAYWRIGHT_BROWSER || 'chromium'}): controls, saved volume, 320px accessibility, and gameplay with unavailable audio. Audio-output tests skipped: this browser build has no Web Audio API.`);
            return;
        }
        await status(tab, 'playing');
        assert.equal(await tab.locator('#pref-sound').isChecked(), false, 'Music is independent of effects');
        await tab.evaluate(() => {
            const music = window.testMusic;
            window.testAnalyser = music.context.createAnalyser();
            music.master.connect(window.testAnalyser);
        });
        await tab.waitForFunction(() => {
            const samples = new Float32Array(window.testAnalyser.fftSize);
            window.testAnalyser.getFloatTimeDomainData(samples);
            return samples.some(sample => Math.abs(sample) > .0001);
        });
        // The playlist streams one song at a time and the skip button advances it.
        assert(await tab.evaluate(() => window.testMusic.songs && !window.testMusic.element.paused));
        assert.equal(await tab.evaluate(() => window.testMusic.element.preload), 'none');
        const firstSong = await tab.evaluate(() => window.testMusic.title);
        assert.equal(await tab.locator('#music-status').textContent(), `Now playing · ${firstSong}`);
        await tab.locator('#music-skip').click();
        await tab.waitForFunction(old => window.testMusic.title !== old && !window.testMusic.element.paused, firstSong);
        assert.match(await tab.locator('#music-status').textContent(), /^Now playing · /);
        await audit(tab);
        // Native keyboard slider interaction updates the live gain and saved value.
        await tab.locator('#pref-music-volume').focus();
        await tab.keyboard.press('Home');
        await status(tab, 'muted');
        assert.equal(await tab.evaluate(() => window.testMusic.voices.size), 0);
        assert.equal(await tab.evaluate(() => window.testMusic.master.gain.value), 0);
        await tab.keyboard.press('ArrowRight');
        await status(tab, 'playing');
        assert.equal(await tab.locator('#music-volume-value').textContent(), '5%');
        await tab.locator('#pref-sound').check();
        await tab.locator('#pref-sound').uncheck();
        await status(tab, 'playing');
        const timer = await tab.evaluate(() => window.testMusic.timer);
        await tab.keyboard.press('Tab');
        assert.equal(await tab.evaluate(() => window.testMusic.timer), timer, 'Repeated gestures do not layer loops');
        // Simulate the lifecycle notification, not a claim of physical phone testing.
        await tab.evaluate(() => {
            Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await status(tab, 'paused');
        assert.equal(await tab.evaluate(() => window.testMusic.voices.size), 0);
        assert.equal(await tab.evaluate(() => window.testMusic.timer), null);
        await tab.evaluate(() => {
            delete document.hidden;
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await status(tab, 'playing');
        await tab.evaluate(() => window.dispatchEvent(new Event('pagehide')));
        await status(tab, 'paused');
        await tab.evaluate(() => window.dispatchEvent(new Event('pageshow')));
        await status(tab, 'playing');
        // Exercise every chord and the loop boundary without waiting for an entire song.
        await tab.evaluate(() => {
            const music = window.testMusic;
            for (let i = 0; i < 65; i++) {
                music.stop();
                music.sync();
            }
            if (music.voices.size > 6) throw new Error('Voices leaked across music restarts');
        });
        await status(tab, 'playing');
        await tab.locator('#pref-music').uncheck();
        await status(tab, 'off');
        assert.equal(await tab.evaluate(() => window.testMusic.voices.size), 0);
        await tab.locator('#pref-music').check();
        await status(tab, 'playing');
        await tab.reload();
        await tab.waitForFunction(() => Boolean(window.testMusic));
        assert.equal(await tab.evaluate(() => window.testMusic.context), null, 'Saved preference still requires a new gesture');
        await tab.locator('#home-screen [data-preferences]').click();
        await status(tab, 'playing');
        assert.equal(await tab.locator('#pref-music-volume').inputValue(), '5');
        await tab.keyboard.press('Escape');
        await tab.locator('#player-name').fill('Music test');
        await tab.locator('#start-button').click();
        await tab.locator('#lobby-screen').waitFor({ state: 'visible' });
        await status(tab, 'playing');
        await tab.locator('#lobby-screen [data-preferences]').click();
        await tab.locator('#pref-music').uncheck();
        await status(tab, 'off');

        const legacy = await page({ saved: { sound: true, haptics: true, motion: true, muted: true } });
        await legacy.locator('#home-screen [data-preferences]').click();
        assert(await legacy.locator('#pref-sound').isChecked());
        assert(await legacy.locator('#pref-haptics').isChecked());
        assert.equal(await legacy.locator('#pref-music').isChecked(), false);
        assert.equal(await legacy.locator('#pref-music-volume').inputValue(), '35');
        for (const [volume, expected] of [[1000, '100'], [-12, '0'], ['bad', '35']]) {
            const invalid = await page({ saved: { musicVolume: volume } });
            assert.equal(await invalid.locator('#pref-music-volume').inputValue(), expected);
            await invalid.context().close();
        }
        const noSongs = await page({ noSongs: true });
        await noSongs.locator('#home-screen [data-preferences]').click();
        await noSongs.locator('#pref-music').check();
        await noSongs.waitForFunction(() => !window.testMusic.songs && window.testMusic.timer !== null);
        await status(noSongs, 'playing');
        assert.equal(await noSongs.locator('#music-status').textContent(), 'Now playing · A Little Company');
        assert(await noSongs.locator('#music-skip').isHidden());
        await noSongs.locator('#pref-music').uncheck();
        await status(noSongs, 'off');
        const unsupported = await page({ unsupported: true });
        await unsupported.locator('#home-screen [data-preferences]').click();
        await unsupported.locator('#pref-music').check();
        await status(unsupported, 'unavailable');
        await unsupported.locator('#pref-music').uncheck();
        await status(unsupported, 'off');
        const blocked = await page({ blocked: true });
        await blocked.locator('#home-screen [data-preferences]').click();
        await blocked.locator('#pref-music').check();
        await status(blocked, 'ready');
        await blocked.locator('#pref-music').uncheck();
        await status(blocked, 'off');
        assert.deepEqual(errors, []);
        console.log(`PASS (${process.env.PLAYWRIGHT_BROWSER || 'chromium'}): actual playlist audio, skip, synthesized fallback, opt-in, independent effects, volume/mute, persistence/migration, lifecycle pause, loop cleanup, unsupported/blocked audio, 320px accessibility.`);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });