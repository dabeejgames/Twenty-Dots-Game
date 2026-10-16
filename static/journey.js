/* Browser-only learning and progress UI. Never sends game actions. */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const symbols = { red: 'R', blue: 'B', green: 'G', purple: 'P', yellow: '✳' };
    const lessons = [
        {
            title: 'Find your first line.', color: 'red', target: 'A3',
            dots: { A1: 'red', A2: 'red' }, collected: ['A1', 'A2', 'A3'],
            description: 'A card names a color and a square. Select red A3, preview its position, then play it to connect three red dots.',
            hint: 'A3 means row A, column 3. In a live turn, play up to two regular cards, together or separately.',
            result: 'A lovely line! +3 red dots. Collected dots leave the board. Lines also work vertically and diagonally.',
        },
        {
            title: 'A little wild goes a long way.', color: 'blue', target: 'C4',
            dots: { C2: 'blue', C3: 'yellow' }, collected: ['C2', 'C3', 'C4'],
            description: 'Yellow joins every color. Select blue C4 to connect blue, yellow, and blue.',
            hint: 'In live games, dice choose yellow’s square. This example already has a wild dot waiting for you.',
            result: '+3 dots: two blue and one yellow. Collecting or replacing yellow requires another wild roll unless you win. A roll that scores a line means roll again.',
        },
        {
            title: 'Make a power move.', color: 'purple', target: 'E4', power: true,
            dots: { E2: 'purple', E3: 'purple' }, collected: ['E2', 'E3', 'E4'],
            description: 'With optional Power Play, Paint can use any empty square. Select Paint, choose the marked E4 square, then confirm.',
            hint: 'For this lesson, aim at E4. In a live game, a power replaces both regular cards and must be played before any regular card that turn. Roll first if required.',
            result: '+3 purple dots! Paint scores a completed line, not placement alone. Shift moves your color to an empty neighbor; Swap exchanges two regular dots. Neither moves yellow.',
        },
    ];

    function element(tag, className, text) {
        const item = document.createElement(tag);
        item.className = className;
        if (text !== undefined) item.textContent = text;
        return item;
    }

    function dot(color) {
        const item = element('i', `dot ${color}`, symbols[color]);
        item.setAttribute('aria-hidden', 'true');
        return item;
    }

    class DotsJourney {
        constructor(progress, hooks) {
            this.progress = progress;
            this.hooks = hooks;
            this.step = 0;
            document.querySelectorAll('[data-learn]').forEach(button => button.addEventListener('click', () => this.start(button)));
            $('lesson-dialog').addEventListener('close', () => {
                if (this.opener?.getClientRects().length && !document.querySelector('dialog[open]')) this.opener.focus({ preventScroll: true });
                this.opener = null;
            });
            document.querySelectorAll('[data-stats]').forEach(button => button.addEventListener('click', () => {
                this.renderStats();
                $('stats-dialog').showModal();
            }));
            $('lesson-card').addEventListener('click', () => {
                if (this.done) return;
                this.selected = !this.selected;
                this.targeted = false;
                this.renderLesson();
            });
            $('lesson-action').addEventListener('click', () => this.advance());
            $('lesson-practice').addEventListener('click', () => {
                this.opener = null;
                $('lesson-dialog').close();
                this.hooks.practice();
            });
            window.addEventListener('storage', event => {
                if (event.key === window.DotsProgress.KEY || event.key === null) {
                    this.progress.invalidate();
                    this.renderStats();
                }
            });
            this.renderStats();
        }

        start(opener) {
            this.opener = opener;
            this.step = 0;
            this.selected = this.targeted = this.done = false;
            this.renderLesson();
            $('lesson-dialog').showModal();
            $('lesson-title').focus();
        }

        renderLesson() {
            const lesson = lessons[this.step];
            $('lesson-step').textContent = `MOVE ${this.step + 1} OF 3 · LEARN BY PLAYING`;
            document.querySelectorAll('.lesson-progress i').forEach((pip, i) => pip.classList.toggle('complete', i < this.step || (i === this.step && this.done)));
            $('lesson-title').textContent = lesson.title;
            $('lesson-description').textContent = lesson.description;
            $('lesson-play-area').hidden = false;
            $('lesson-practice').hidden = true;
            $('lesson-card-hint').textContent = lesson.hint;
            const card = $('lesson-card');
            card.disabled = this.done;
            card.classList.toggle('selected', this.selected && !this.done);
            card.classList.toggle('power-card', Boolean(lesson.power));
            card.setAttribute('aria-pressed', String(this.selected && !this.done));
            card.setAttribute('aria-label', lesson.power ? 'Purple Paint power' : `${lesson.color}, ${lesson.target}`);
            card.replaceChildren(element('span', 'card-coordinate', lesson.power ? '✦ Paint' : lesson.target), dot(lesson.color), element('span', 'card-color', lesson.color.toUpperCase()));
            const board = $('lesson-board');
            const focused = board.contains(document.activeElement) ? document.activeElement.dataset.location : null;
            board.replaceChildren(element('span', 'board-label'));
            for (let col = 1; col <= 6; col++) board.append(element('span', 'board-label', String(col)));
            for (const row of 'ABCDEF') {
                board.append(element('span', 'board-label', row));
                for (let col = 1; col <= 6; col++) {
                    const location = `${row}${col}`;
                    const target = location === lesson.target;
                    const preview = target && this.selected && (!lesson.power || this.targeted) && !this.done;
                    const color = this.done ? null : preview ? lesson.color : lesson.dots[location];
                    const cell = element('button', 'cell');
                    cell.type = 'button';
                    cell.dataset.location = location;
                    cell.classList.toggle('preview', Boolean(preview));
                    cell.classList.toggle('lesson-target', target && !this.done);
                    cell.classList.toggle('last-collected', this.done && lesson.collected.includes(location));
                    cell.setAttribute('aria-label', `${location}: ${color || 'empty'}${target && !this.done ? '; lesson target' : ''}${preview ? '; preview' : ''}`);
                    cell.append(element('span', 'cell-coordinate', location));
                    if (color) cell.append(dot(color));
                    else if (target && !this.done) cell.append(element('span', 'target-plus', '+'));
                    cell.addEventListener('click', () => {
                        if (this.done) return;
                        if (!this.selected) {
                            $('lesson-feedback').textContent = 'Select the card below the board first.';
                        } else if (!target) {
                            $('lesson-feedback').textContent = `This guided move uses ${lesson.target}. Choose the marked square.`;
                        } else {
                            this.targeted = true;
                            this.renderLesson();
                        }
                    });
                    cell.addEventListener('keydown', event => {
                        const offsets = { ArrowUp: -6, ArrowDown: 6, ArrowLeft: -1, ArrowRight: 1 };
                        if (!(event.key in offsets)) return;
                        event.preventDefault();
                        const cells = [...board.querySelectorAll('button')];
                        cells[Math.max(0, Math.min(35, cells.indexOf(cell) + offsets[event.key]))].focus();
                    });
                    board.append(cell);
                }
            }
            if (focused) [...board.querySelectorAll('button')].find(cell => cell.dataset.location === focused)?.focus();
            const ready = this.selected && (!lesson.power || this.targeted);
            $('lesson-action').disabled = !this.done && !ready;
            $('lesson-action').textContent = this.done ? this.step === 2 ? 'Finish the lesson ✳' : 'Next move →'
                : !this.selected ? 'Choose your card' : !ready ? `Choose ${lesson.target} on the board` : lesson.power ? 'Confirm Paint ✦' : `Play ${lesson.target} ↗`;
            $('lesson-feedback').textContent = this.done ? lesson.result : ready ? 'That’s your preview. Confirm below to collect the line.' : 'Nothing is played until you confirm.';
        }

        advance() {
            if (this.step >= lessons.length) {
                $('lesson-dialog').close();
                return;
            }
            if (!this.done) {
                if (!this.selected || (lessons[this.step].power && !this.targeted)) return;
                this.done = true;
                this.renderLesson();
                this.hooks.note(true, false);
                return;
            }
            this.step++;
            if (this.step < lessons.length) {
                this.selected = this.targeted = this.done = false;
                this.renderLesson();
            } else {
                $('lesson-step').textContent = 'LESSON COMPLETE';
                $('lesson-title').textContent = 'You’ve got the connection.';
                $('lesson-description').textContent = 'In Classic, collect 20 dots to win. Other modes ask for five of each color. Start with an easy practice game, or invite your people.';
                $('lesson-play-area').hidden = true;
                $('lesson-feedback').textContent = 'First Connection badge earned. Your first real table is waiting.';
                $('lesson-action').textContent = 'Back to the table';
                $('lesson-practice').hidden = !this.hooks.canPractice();
                this.progress.learn().then(() => this.renderStats());
            }
            $('lesson-title').focus();
        }

        async observe(state, player) {
            const result = await this.progress.observe(state, player);
            this.renderStats();
            if (state.winner && result.counted && this.hooks.isCurrent(state)) {
                $('personal-result').textContent = result.unlocked.length
                    ? `New badges: ${result.unlocked.map(badge => badge.title).join(' · ')}`
                    : 'Round saved to your stats. Every good game counts.';
            }
        }

        renderStats() {
            const stats = this.progress.read();
            $('learning-note').textContent = stats.tutorial ? 'First Connection ✓ · Replay the lesson anytime.' : 'Three guided moves. No room or account needed.';
            const values = [
                ['Rounds finished', stats.rounds], ['Wins', stats.wins],
                ['Win rate', stats.rounds ? `${Math.round(stats.wins / stats.rounds * 100)}%` : '—'],
                ['Current win streak', stats.streak], ['Best win streak', stats.bestStreak],
                ['Dots in finished rounds', stats.dots], ['Best move · dots', stats.bestMove],
                ['Best round · dots', stats.bestRound],
            ];
            $('stats-grid').replaceChildren(...values.map(([label, value]) => {
                const group = element('div', 'stat-tile');
                group.append(element('dt', '', label), element('dd', '', String(value)));
                return group;
            }));
            $('badge-list').replaceChildren(...window.DotsProgress.BADGES.map(badge => {
                const earned = badge.test(stats);
                const item = element('li', `milestone${earned ? ' earned' : ''}`);
                const mark = element('span', 'milestone-mark', earned ? '✳' : '○');
                mark.setAttribute('aria-hidden', 'true');
                const text = element('div', '');
                text.append(element('strong', '', `${badge.title} · ${earned ? 'Earned' : 'Locked'}`), element('p', '', badge.description));
                item.append(mark, text);
                return item;
            }));
        }
    }
    window.DotsJourney = DotsJourney;
})();