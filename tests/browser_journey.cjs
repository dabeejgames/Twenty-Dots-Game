/* Runs in the private fixture suite; lessons never create a room or send moves. */
const assert = require('node:assert/strict');

module.exports = async (browser, base, audit, exceptions) => {
    const context = await browser.newContext({ viewport: { width: 320, height: 900 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    page.on('pageerror', error => exceptions.push(error.message));
    try {
        await page.goto(`${base}/web_client.html`);
        await page.locator('[data-learn]').click();
        await audit(page, 'Lesson intro at 320px');
        assert(await page.locator('#lesson-action').isDisabled());
        await page.locator('#lesson-board [data-location="A3"]').click();
        assert.match(await page.locator('#lesson-feedback').textContent(), /Select the card/);
        await page.locator('#lesson-card').focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.locator('#lesson-board .preview').count(), 1);
        await page.locator('#lesson-action').click();
        assert.match(await page.locator('#lesson-feedback').textContent(), /\+3 red/);
        assert.equal(await page.locator('#lesson-board .dot').count(), 0);
        await page.locator('#lesson-action').click();
        await page.locator('#lesson-card').click();
        await page.locator('#lesson-action').click();
        assert.match(await page.locator('#lesson-feedback').textContent(), /two blue and one yellow/);
        await page.locator('#lesson-action').click();
        await page.locator('#lesson-card').click();
        assert(await page.locator('#lesson-action').isDisabled());
        await page.locator('#lesson-board [data-location="A1"]').click();
        assert.match(await page.locator('#lesson-feedback').textContent(), /uses E4/);
        assert(await page.locator('#lesson-action').isDisabled());
        await page.locator('#lesson-board [data-location="E3"]').focus();
        await page.keyboard.press('ArrowRight');
        assert.equal(await page.evaluate(() => document.activeElement.dataset.location), 'E4');
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => document.activeElement.dataset.location), 'E4', 'Targeting preserves focus');
        await page.locator('#lesson-action').click();
        await page.locator('#lesson-action').click();
        await page.waitForFunction(() => JSON.parse(localStorage.getItem('twenty-dots.progress.v1'))?.tutorial);
        await audit(page, 'Lesson completion');
        assert.equal(await page.evaluate(() => localStorage.getItem('twenty-dots.seat.v1')), null);
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('twenty-dots.progress.v1')).rounds), 0);
        await page.locator('#lesson-practice').click();
        assert.equal(await page.locator('#tab-solo').getAttribute('aria-selected'), 'true');
        assert.equal(await page.locator('#difficulty').inputValue(), 'easy');
        await page.locator('#home-screen [data-stats]').click();
        assert.equal(await page.locator('.milestone.earned').count(), 1);
        await audit(page, 'Stats and badges at 320px');
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.keyboard.press('Escape');
        await page.reload();
        assert.match(await page.locator('#learning-note').textContent(), /First Connection/);
        await page.locator('[data-learn]').click();
        assert.match(await page.locator('#lesson-step').textContent(), /MOVE 1/);
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => document.activeElement === document.querySelector('[data-learn]'));
        // Storage denial must not prevent a new player learning or viewing zero stats.
        const blocked = await browser.newContext();
        try {
            await blocked.addInitScript(() => {
                Storage.prototype.getItem = () => { throw new Error('Storage blocked'); };
                Storage.prototype.setItem = () => { throw new Error('Storage blocked'); };
            });
            const blockedPage = await blocked.newPage();
            blockedPage.on('pageerror', error => exceptions.push(error.message));
            await blockedPage.goto(`${base}/web_client.html`);
            await blockedPage.locator('[data-learn]').click();
            await blockedPage.locator('#lesson-card').click();
            await blockedPage.locator('#lesson-action').click();
            assert.match(await blockedPage.locator('#lesson-feedback').textContent(), /\+3 red/);
        } finally { await blocked.close(); }
    } finally { await context.close(); }
};