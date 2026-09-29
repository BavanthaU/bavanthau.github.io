// Focused checks of the real visibility controller without a browser dependency.
const assert = require('assert').strict;
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(require('path').join(__dirname, '../../assets/media.js'), 'utf8');
const controller = source.slice(source.indexOf('  /* ---- autoplay only'), source.indexOf('  /* ---- visible play'));
function fixture(reduced = false) {
  const events = {}, docEvents = {};
  let observer;
  const video = {
    paused: true, dataset: {}, hiddenPanel: false, handlers: {},
    addEventListener(name, fn) { this.handlers[name] = fn; },
    closest() { return this.hiddenPanel ? {} : null; },
    play() { this.paused = false; this.handlers.play(); return Promise.resolve(); },
    pause() { this.paused = true; this.handlers.pause(); }
  };
  const document = { hidden: false, querySelectorAll: () => [video], addEventListener: (n, fn) => { docEvents[n] = fn; } };
  class IntersectionObserver {
    constructor(cb) { observer = cb; }
    observe() {}
  }
  vm.runInNewContext(controller, { reduced, document, window: { IntersectionObserver }, IntersectionObserver,
    WeakMap, WeakSet, addEventListener: (n, fn) => { events[n] = fn; } });
  return { video, document, ratio: n => observer([{ target: video, intersectionRatio: n }]),
    visibility: hidden => { document.hidden = hidden; docEvents.visibilitychange(); } };
}
let f = fixture();
f.ratio(1); assert.equal(f.video.paused, false, 'visible muted video starts');
f.ratio(0); assert.equal(f.video.paused, true, 'offscreen video pauses');
f.ratio(1); assert.equal(f.video.paused, false, 'automatic pause allows resuming');
f.video.pause(); f.ratio(0); f.ratio(1);
assert.equal(f.video.paused, true, 'native manual pause survives scrolling');
f.video.play(); f.visibility(true);
assert.equal(f.video.paused, true, 'background tab pauses');
f.visibility(false); assert.equal(f.video.paused, false, 'visible tab resumes');
f.video.hiddenPanel = true; f.video.pause(); f.ratio(0); f.ratio(1);
assert.equal(f.video.paused, true, 'hidden research panel stays paused');
f.video.hiddenPanel = false; f.ratio(1);
assert.equal(f.video.paused, false, 'selected research panel can resume');
f = fixture(true); f.ratio(1);
assert.equal(f.video.paused, true, 'reduced motion disables autoplay');
f.video.play(); assert.equal(f.video.paused, false, 'reduced motion permits manual playback');
f.ratio(0); assert.equal(f.video.paused, true, 'manual video still pauses offscreen');
console.log('PASS: visibility, manual pause, background tabs, research panels and reduced motion.');
const chapterStart = source.slice(source.indexOf('  /* ---- chapter-start clips'), source.indexOf('  /* ---- autoplay only'));
const clipEvents = {};
const clip = { dataset: { start: '59' }, readyState: 0, duration: 180, currentTime: 0, plays: 0,
  addEventListener(n, fn) { clipEvents[n] = fn; }, closest() { return null; },
  getBoundingClientRect() { return { top: 100, bottom: 350 }; },
  play() { this.plays++; return Promise.resolve(); } };
const clipDocument = { hidden: false, querySelectorAll: () => [clip] };
vm.runInNewContext(chapterStart, { document: clipDocument, window: { innerHeight: 800 } });
clipEvents.loadedmetadata(); assert.equal(clip.currentTime, 59, 'initial playback starts at SLAM segment');
clip.currentTime = 180; clipEvents.ended();
assert.equal(clip.currentTime, 59, 'repeat returns to SLAM segment');
assert.equal(clip.plays, 1);
clipDocument.hidden = true; clipEvents.ended();
assert.equal(clip.plays, 1, 'background page does not restart clip');
console.log('PASS: bachelor clip starts and repeats at 0:59.');
