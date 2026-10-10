/* Original, locally synthesized game-night music. No recordings or streaming services. */
(() => {
    'use strict';

    const CHORDS = [
        [48, 60, 64, 67, 71], [45, 60, 64, 67, 69],
        [41, 57, 60, 64, 67], [43, 59, 62, 67, 69],
        [48, 59, 62, 64, 67], [45, 57, 60, 64, 67],
        [41, 57, 60, 64, 67], [43, 55, 59, 62, 69],
    ];
    const MELODY = [4, null, 2, 3, null, 1, 2, null];
    const STEP = 60 / 80 / 2; // Eight gently swung eighth notes per bar, 80 BPM.
    const SYNTH_TITLE = 'A Little Company';
    // Add a song: drop the MP3 in static/music/ and list it here.
    const SONGS = [
        { title: 'Still Movin’', src: 'static/music/still-movin.mp3' },
        { title: 'Midnight Ride', src: 'static/music/midnight-ride.mp3' },
        { title: 'Lost My Way', src: 'static/music/lost-my-way.mp3' },
        { title: 'The Dance', src: 'static/music/the-dance.mp3' },
        { title: 'The Drop (Extended Version)', src: 'static/music/the-drop-extended.mp3' },
        { title: 'In The Act', src: 'static/music/in-the-act.mp3' },
        { title: 'Through The Smoke', src: 'static/music/through-the-smoke.mp3' },
        { title: 'Before The Day’s End', src: 'static/music/before-the-days-end.mp3' },
        { title: 'Steps', src: 'static/music/steps.mp3' },
        { title: 'No Words', src: 'static/music/no-words.mp3' },
    ];

    function shuffled(items) {
        const order = items.map((_, index) => index);
        for (let i = order.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [order[i], order[j]] = [order[j], order[i]];
        }
        return order;
    }

    class TableMusic {
        constructor(onStatus) {
            this.onStatus = onStatus;
            this.songs = SONGS.length > 0;
            this.order = shuffled(SONGS);
            this.position = 0;
            this.broken = new Set();
            this.element = null;
            this.context = null;
            this.enabled = false;
            this.volume = 35;
            this.hidden = false;
            this.timer = null;
            this.voices = new Set();
            this.step = 0;
            this.failed = false;
            this.status = '';
        }

        attach(context) {
            if (this.context === context) return;
            this.context = context;
            this.master = context.createGain();
            this.master.gain.value = 0;
            this.filter = context.createBiquadFilter();
            this.filter.type = 'lowpass';
            this.filter.frequency.value = 1800;
            this.delay = context.createDelay(1);
            this.delay.delayTime.value = STEP * 1.5;
            this.feedback = context.createGain();
            this.feedback.gain.value = .2;
            this.wet = context.createGain();
            this.wet.gain.value = .18;
            this.filter.connect(this.master);
            this.filter.connect(this.delay);
            this.delay.connect(this.feedback).connect(this.delay);
            this.delay.connect(this.wet).connect(this.master);
            this.master.connect(context.destination);
            if (this.songs) {
                // Only the current song is fetched; preload stays off until it plays.
                this.element = new Audio();
                this.element.preload = 'none';
                this.element.addEventListener('ended', () => this.next());
                this.element.addEventListener('error', () => this.skipBroken());
                context.createMediaElementSource(this.element).connect(this.master);
            }
            context.addEventListener('statechange', () => this.sync());
        }

        get title() {
            return this.songs ? SONGS[this.order[this.position]].title : SYNTH_TITLE;
        }

        playSong() {
            const song = SONGS[this.order[this.position]];
            if (!this.element.src.endsWith(song.src)) this.element.src = song.src;
            if (!this.element.paused) return;
            this.element.play().catch(error => {
                // A pause or skip interrupting play() is expected; a policy block is not.
                if (error.name === 'NotAllowedError') this.report('ready');
            });
        }

        next() {
            if (!this.songs) return;
            do {
                this.position = (this.position + 1) % SONGS.length;
                if (this.position === 0) this.order = shuffled(SONGS);
            } while (this.broken.has(this.order[this.position]));
            this.element.pause();
            this.element.removeAttribute('src');
            if (this.status === 'playing') this.playSong();
            this.onStatus(this.status);
        }

        skipBroken() {
            if (!this.songs || !this.element.getAttribute('src')) return;
            this.broken.add(this.order[this.position]);
            if (this.broken.size < SONGS.length) return this.next();
            // Every song failed to load: fall back to the synthesized track.
            this.songs = false;
            this.element.pause();
            this.element.removeAttribute('src');
            this.status = '';
            this.sync();
        }

        update(enabled, volume, hidden) {
            this.enabled = enabled;
            this.volume = volume;
            this.hidden = hidden;
            this.sync();
        }

        report(status) {
            if (status === this.status) return;
            this.status = status;
            this.onStatus(status);
        }

        sync() {
            const paused = !this.enabled ? 'off' : this.failed ? 'unavailable'
                : this.hidden ? 'paused' : this.volume === 0 ? 'muted'
                    : this.context?.state !== 'running' ? 'ready' : null;
            if (paused) {
                this.stop();
                this.report(paused);
                return;
            }
            this.master.gain.setTargetAtTime(this.volume / 100 * .7, this.context.currentTime, .08);
            if (this.songs) {
                this.report('playing');
                this.playSong();
                return;
            }
            if (this.timer !== null) return;
            this.nextTime = this.context.currentTime + .05;
            this.timer = setInterval(() => this.tick(), 80);
            this.report('playing');
            this.tick();
        }

        stop() {
            clearInterval(this.timer);
            this.timer = null;
            this.element?.pause();
            if (this.master) {
                // Cancel from 0 so a fade already in progress cannot keep the gain up.
                this.master.gain.cancelScheduledValues(0);
                this.master.gain.value = 0;
            }
            for (const voice of this.voices) {
                voice.oscillator.stop();
                voice.oscillator.disconnect();
                voice.gain.disconnect();
            }
            this.voices.clear();
        }

        note(midi, time, duration, level, type = 'sine') {
            const oscillator = this.context.createOscillator();
            const gain = this.context.createGain();
            oscillator.type = type;
            oscillator.frequency.value = 440 * 2 ** ((midi - 69) / 12);
            gain.gain.setValueAtTime(0, time);
            gain.gain.linearRampToValueAtTime(level, time + .025);
            gain.gain.exponentialRampToValueAtTime(.0001, time + duration);
            oscillator.connect(gain).connect(this.filter);
            const voice = { oscillator, gain };
            this.voices.add(voice);
            oscillator.onended = () => {
                oscillator.disconnect();
                gain.disconnect();
                this.voices.delete(voice);
            };
            oscillator.start(time);
            oscillator.stop(time + duration + .02);
        }

        tick() {
            if (this.context?.state !== 'running' || this.hidden || !this.enabled) return this.sync();
            try {
                // A stalled tab resumes ahead of the clock, never with a burst of missed notes.
                if (this.nextTime < this.context.currentTime) this.nextTime = this.context.currentTime + .05;
                while (this.nextTime < this.context.currentTime + .2) {
                    const beat = this.step % 8;
                    const chord = CHORDS[Math.floor(this.step / 8) % CHORDS.length];
                    if (beat === 0) chord.slice(1).forEach(pitch => this.note(pitch, this.nextTime, 2.6, .025));
                    if (beat === 0 || beat === 4) this.note(chord[0], this.nextTime, 1.1, .1);
                    const tone = MELODY[beat];
                    if (tone !== null) this.note(chord[tone] + 12, this.nextTime, .65, .04, 'triangle');
                    this.nextTime += STEP * (beat % 2 === 0 ? 1.08 : .92);
                    this.step = (this.step + 1) % (CHORDS.length * 8);
                }
            } catch {
                this.failed = true;
                this.stop();
                this.report('unavailable');
            }
        }
    }

    window.TableMusic = TableMusic;
})();