(function () {
  var cfg = window.rtNarrate;
  if (!cfg) return;
  var btn = document.getElementById('narrate-btn');
  var auto = document.getElementById('narrate-auto');
  if (!btn) return;
  var audio = new Audio();
  audio.preload = 'auto';
  var cache = {};
  var state = { page: -1, words: [], idx: -1, playing: false, token: 0, session: false };

  function curPage() {
    var i = Reveal.getIndices();
    return i.h;
  }
  function spans(page) {
    return $('.slides > section').eq(page).find('.reading-word');
  }
  function clear() {
    $('.reading-word.active').removeClass('active');
    state.idx = -1;
  }
  function setBtn(label, busy) {
    btn.textContent = label;
    btn.disabled = !!busy;
  }
  function fetchPage(page) {
    if (cache[page]) return cache[page];
    var qs = (cfg.book ? 'book=' + encodeURIComponent(cfg.book) : 'story=' + encodeURIComponent(cfg.story)) + '&page=' + page;
    cache[page] = fetch('/api/audio/page?' + qs, { method: 'POST' }).then(function (r) {
      if (!r.ok) throw new Error('narration ' + r.status);
      return r.json();
    }).catch(function (e) { delete cache[page]; throw e; });
    return cache[page];
  }
  function prefetch(page) {
    if (page + 1 < $('.slides > section').length) fetchPage(page + 1).catch(function () {});
  }
  function start(page, fromWord) {
    var tok = ++state.token;
    audio.pause();
    clear();
    setBtn('Loading...', true);
    fetchPage(page).then(function (n) {
      if (tok !== state.token) return;
      if (!n.audio || !n.words || !n.words.length) {
        state.page = page;
        if (auto && auto.checked && page + 1 < $('.slides > section').length) { Reveal.slide(page + 1); } else { state.session = false; setBtn('Listen', false); }
        return;
      }
      state.page = page;
      state.words = n.words;
      audio.src = n.audio;
      var seek = 0;
      if (fromWord != null) {
        for (var i = 0; i < n.words.length; i++) if (n.words[i].i === fromWord) { seek = n.words[i].t; break; }
      }
      audio.onloadedmetadata = function () { if (seek) audio.currentTime = seek; };
      audio.play().then(function () {
        state.playing = true;
        setBtn('Pause', false);
        prefetch(page);
      }).catch(function () { setBtn('Listen', false); });
    }).catch(function () { setBtn('Listen', false); btn.title = 'Narration unavailable'; });
  }
  function stop() {
    state.token++;
    state.session = false;
    audio.pause();
    state.playing = false;
    clear();
    setBtn('Listen', false);
  }
  audio.addEventListener('timeupdate', function () {
    var t = audio.currentTime, w = state.words, k = -1;
    for (var i = 0; i < w.length; i++) { if (w[i].t <= t + 0.05) k = i; else break; }
    if (k === state.idx) return;
    $('.reading-word.active').removeClass('active');
    state.idx = k;
    if (k >= 0) spans(state.page).eq(w[k].i).addClass('active');
  });
  audio.addEventListener('ended', function () {
    clear();
    state.playing = false;
    var next = state.page + 1;
    if (auto && auto.checked && next < $('.slides > section').length) {
      Reveal.slide(next);
    } else {
      state.session = false;
      setBtn('Listen', false);
    }
  });
  btn.addEventListener('click', function () {
    if (state.playing) {
      audio.pause();
      state.playing = false;
      state.session = false;
      setBtn('Resume', false);
    } else if (audio.src && audio.paused && audio.currentTime > 0 && !audio.ended && state.page === curPage()) {
      state.session = true;
      audio.play().then(function () { state.playing = true; setBtn('Pause', false); });
    } else {
      state.session = true;
      start(curPage());
    }
  });
  Reveal.addEventListener('slidechanged', function (e) {
    audio.pause();
    state.playing = false;
    clear();
    if (state.session && auto && auto.checked) start(e.indexh); else { state.session = false; setBtn('Listen', false); }
  });
  $(document).on('click', '.slides .reading-word', function () {
    var page = curPage();
    var el = $('.slides > section').eq(page).find('.reading-word');
    var idx = el.index(this);
    if (idx < 0) return;
    if (state.page === page && audio.src && state.words.length) {
      for (var i = 0; i < state.words.length; i++) {
        if (state.words[i].i === idx) {
          audio.currentTime = state.words[i].t;
          audio.play().then(function () { state.playing = true; setBtn('Pause', false); });
          return;
        }
      }
    }
    state.session = true;
    start(page, idx);
  });
})();
