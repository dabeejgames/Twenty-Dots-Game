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

    class TableMusic {
        constructor(onStatus) {
            this.onStatus = onStatus;
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
            context.addEventListener('statechange', () => this.sync());
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
            if (this.timer !== null) return;
            this.nextTime = this.context.currentTime + .05;
            this.timer = setInterval(() => this.tick(), 80);
            this.report('playing');
            this.tick();
        }

        stop() {
            clearInterval(this.timer);
            this.timer = null;
            if (this.master) {
                this.master.gain.cancelScheduledValues(this.context.currentTime);
                this.master.gain.setValueAtTime(0, this.context.currentTime);
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