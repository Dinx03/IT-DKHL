(function(){
  'use strict';
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $  = function(s,c){ return (c||document).querySelector(s); };
  var $$ = function(s,c){ return Array.prototype.slice.call((c||document).querySelectorAll(s)); };

  /* ---------- language ----------
     Thai is what sits in the markup, so the page still reads correctly with no
     JavaScript. English lives next to it in data-en / data-en-html / data-en-text
     / data-en-aria / data-en-placeholder, and swapping is a straight text swap. */
  var langNodes = $$('[data-en],[data-en-html],[data-en-text],[data-en-aria],[data-en-placeholder]');
  langNodes.forEach(function(el){
    if (el.hasAttribute('data-en-html')) el._th = el.innerHTML;
    else if (el.hasAttribute('data-en')) el._th = el.textContent;
    else if (el.hasAttribute('data-en-text')) {
      // element mixes text with child elements: remember only its own text nodes
      el._thText = [];
      Array.prototype.forEach.call(el.childNodes, function(n){
        if (n.nodeType === 3 && n.nodeValue.trim()) el._thText.push([n, n.nodeValue]);
      });
    }
    if (el.hasAttribute('data-en-aria')) el._thAria = el.getAttribute('aria-label');
    if (el.hasAttribute('data-en-placeholder')) el._thPh = el.getAttribute('placeholder');
  });

  var langBtn = $('#langBtn');
  var langCode = $('#langCode');

  function setLang(lang){
    var en = lang === 'en';
    document.documentElement.setAttribute('data-lang', lang);
    document.documentElement.lang = lang;

    langNodes.forEach(function(el){
      if (el.hasAttribute('data-en-html')){
        el.innerHTML = en ? el.getAttribute('data-en-html') : el._th;
      } else if (el.hasAttribute('data-en')){
        el.textContent = en ? el.getAttribute('data-en') : el._th;
      } else if (el._thText){
        // only the first own text node carries the translated string
        el._thText.forEach(function(pair, i){
          pair[0].nodeValue = en ? (i === 0 ? el.getAttribute('data-en-text') : '') : pair[1];
        });
      }
      if (el.hasAttribute('data-en-aria')) el.setAttribute('aria-label', en ? el.getAttribute('data-en-aria') : el._thAria);
      if (el.hasAttribute('data-en-placeholder')) el.setAttribute('placeholder', en ? el.getAttribute('data-en-placeholder') : el._thPh);
    });

    if (langCode) langCode.textContent = en ? 'TH' : 'EN';   // label shows what you switch to
    try { localStorage.setItem('ona-lang', lang); } catch(e){}
  }

  if (langBtn){
    langBtn.addEventListener('click', function(){
      setLang(document.documentElement.getAttribute('data-lang') === 'en' ? 'th' : 'en');
    });
  }
  /* the first setLang() runs at the very bottom of this file, once every other
     control has been wired — calling it here would touch not-yet-assigned vars */

  /* ---------- cross-page anchors ----------
     Header and footer are shared by every page, so they spell the home page out
     (index.html#section). That way the links still work with JavaScript off —
     the markup itself points somewhere real from every page. On the home page
     that would reload the page to reach a section already on screen, so shorten
     those links to a bare hash and let the browser scroll instead. */
  $$('a[href^="index.html#"]').forEach(function(a){
    var id = a.getAttribute('href').slice(11);   // past 'index.html#'
    if (id && document.getElementById(id)){
      a.setAttribute('href', '#' + id);
    }
  });

  /* ---------- sticky stack: hairline, announcement reveal, offsets ---------- */
  var hdr = $('#hdr');
  var topbar = $('#topbar');
  var topbarH = 78;
  var ANNOUNCE_AT = 90;   // px scrolled before the strip rolls open

  function syncHeader(){
    hdr.classList.toggle('is-stuck', scrollY > 12);
    topbar.classList.toggle('has-announce', scrollY > ANNOUNCE_AT);
    var r = topbar.getBoundingClientRect();
    topbarH = r.height;
    var root = document.documentElement.style;
    root.setProperty('--topbar-h', Math.round(topbarH) + 'px');
    root.setProperty('--mega-top', Math.max(0, Math.round(r.bottom)) + 'px');
  }
  syncHeader();
  addEventListener('scroll', syncHeader, { passive:true });
  addEventListener('resize', syncHeader);
  /* the strip animates open, so keep measuring while it does */
  topbar.addEventListener('transitionend', syncHeader);

  /* ---------- mega menu ---------- */
  var items = $$('.nav__item');
  var openId = null;
  function closeMega(){
    if (!openId) return;
    var m = document.getElementById(openId);
    if (m) m.classList.remove('open');
    items.forEach(function(i){
      i.classList.remove('open');
      var b = $('.nav__btn', i); if (b) b.setAttribute('aria-expanded','false');
    });
    openId = null;
  }
  function openMega(id, item){
    if (openId === id) return;
    closeMega();
    var m = document.getElementById(id);
    if (!m) return;
    m.classList.add('open');
    item.classList.add('open');
    var b = $('.nav__btn', item); if (b) b.setAttribute('aria-expanded','true');
    openId = id;
  }
  var hoverTimer;
  items.forEach(function(item){
    var id = item.getAttribute('data-mega');
    var mega = document.getElementById(id);
    var btn = $('.nav__btn', item);
    item.addEventListener('mouseenter', function(){ clearTimeout(hoverTimer); openMega(id, item); });
    item.addEventListener('mouseleave', function(){ hoverTimer = setTimeout(closeMega, 220); });
    if (mega){
      mega.addEventListener('mouseenter', function(){ clearTimeout(hoverTimer); });
      mega.addEventListener('mouseleave', function(){ hoverTimer = setTimeout(closeMega, 220); });
    }
    if (btn){
      btn.addEventListener('click', function(e){
        e.preventDefault();
        if (openId === id) closeMega(); else openMega(id, item);
      });
    }
  });
  addEventListener('keydown', function(e){ if (e.key === 'Escape'){ closeMega(); closeMobile(); } });

  /* ---------- mobile nav ---------- */
  var mnav = $('#mnav');
  function closeMobile(){ mnav.classList.remove('open'); document.body.style.overflow=''; }
  $('#menuOpen').addEventListener('click', function(){ mnav.classList.add('open'); document.body.style.overflow='hidden'; });
  $('#menuClose').addEventListener('click', closeMobile);
  $$('.mnav__list a, .mnav .btn').forEach(function(a){ a.addEventListener('click', closeMobile); });

  /* ---------- reveal on scroll ---------- */
  if ('IntersectionObserver' in window && !reduce){
    var rio = new IntersectionObserver(function(es){
      es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add('in'); rio.unobserve(e.target); } });
    }, { threshold:.12, rootMargin:'0px 0px -6% 0px' });
    $$('.rv').forEach(function(el){ rio.observe(el); });
  } else {
    $$('.rv').forEach(function(el){ el.classList.add('in'); });
  }

  /* ---------- pinned journey ---------- */
  var track = $('#jTrack');
  var jSlides = $$('.jslide');
  var jFigs   = $$('.jfig');
  var jRail   = $$('.jrail__i');
  var jCount  = jSlides.length;
  var jCur = -1;

  function setJourney(i){
    if (i === jCur) return;
    jCur = i;
    jSlides.forEach(function(el,k){ el.classList.toggle('on', k===i); });
    jFigs.forEach(function(el,k){ el.classList.toggle('on', k===i); });
    jRail.forEach(function(el,k){ el.classList.toggle('on', k===i); });
  }
  function onJourneyScroll(){
    if (!track) return;
    var r = track.getBoundingClientRect();
    var total = r.height - (innerHeight - topbarH);
    if (total <= 0) { setJourney(0); return; }
    var p = Math.max(0, Math.min(0.9999, (-r.top) / total));
    setJourney(Math.floor(p * jCount));
  }
  jRail.forEach(function(btn){
    btn.addEventListener('click', function(){
      var i = +btn.getAttribute('data-j');
      var r = track.getBoundingClientRect();
      var docTop = r.top + scrollY;                 // offsetTop is relative to .journey, not the page
      var total = r.height - (innerHeight - topbarH);
      if (total <= 0) return;
      scrollTo({ top: docTop + total * ((i + .5) / jCount), behavior: reduce ? 'auto' : 'smooth' });
    });
  });
  /* Driven by rAF while the section is on screen rather than by scroll events:
     mobile browsers coalesce or drop scroll events during momentum scrolling,
     which leaves the sequence frozen on the first step. */
  var jRaf = 0;
  function jTick(){ onJourneyScroll(); jRaf = requestAnimationFrame(jTick); }
  function jStart(){ if (!jRaf) jRaf = requestAnimationFrame(jTick); }
  function jStop(){ if (jRaf){ cancelAnimationFrame(jRaf); jRaf = 0; } }
  if (track && 'IntersectionObserver' in window){
    new IntersectionObserver(function(es){
      es[0].isIntersecting ? jStart() : jStop();
    }, { rootMargin:'120px 0px' }).observe(track);
  } else {
    jStart();
  }
  addEventListener('scroll', onJourneyScroll, { passive:true });
  addEventListener('resize', onJourneyScroll);
  /* last resort: fires once after scrolling settles, so the sequence still lands
     on the right step where frames and scroll events are being throttled */
  addEventListener('scrollend', onJourneyScroll);
  onJourneyScroll();

  function pad(n){ return (n<10?'0':'') + n; }

  /* ---------- tablist (the farm-day programme) ---------- */
  var tabSec = $('.tabsec');
  var wTabs  = $$('.tabsec__tab');
  var wPanes = $$('.tabpane');
  var TAB_MS = 3000;

  function setWhy(i, focus){
    wTabs.forEach(function(t,k){
      var on = k === i;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      if (on && focus) t.focus();
    });
    wPanes.forEach(function(p,k){ p.hidden = k !== i; });
  }
  function currentTab(){
    var i = wTabs.findIndex(function(t){ return t.getAttribute('aria-selected') === 'true'; });
    return i < 0 ? 0 : i;
  }

  /* Autoplay cycles the programme continuously and does not stop for anything the
     reader does — hovering and clicking both leave it running. Picking a tab only
     restarts the clock from that tab, so a deliberate choice still gets its full
     dwell time before the cycle moves on. It pauses only where carrying on would
     be broken rather than merely unwanted: off screen, or in a hidden tab where no
     frames arrive and the fill bar would drift out of step with the timer. */
  var tabTimer = 0, tabVisible = false;
  function tabsPlay(){
    tabsPause();
    if (reduce || !tabVisible || wTabs.length < 2) return;
    if (tabSec) tabSec.classList.add('is-playing');
    tabTimer = setInterval(function(){
      setWhy((currentTab() + 1) % wTabs.length);
    }, TAB_MS);
  }
  function tabsPause(){
    clearInterval(tabTimer); tabTimer = 0;
    if (tabSec) tabSec.classList.remove('is-playing');
  }

  wTabs.forEach(function(tab, i){
    tab.addEventListener('click', function(){ setWhy(i); tabsPlay(); });
    tab.addEventListener('keydown', function(e){
      var last = wTabs.length - 1, n = null;
      if (e.key === 'ArrowRight') n = i === last ? 0 : i + 1;
      else if (e.key === 'ArrowLeft') n = i === 0 ? last : i - 1;
      else if (e.key === 'Home') n = 0;
      else if (e.key === 'End') n = last;
      if (n !== null){ e.preventDefault(); setWhy(n, true); tabsPlay(); }
    });
  });

  if (tabSec){
    /* Watch the panel, not the whole section, and take any sliver of it as
       visible: the section is taller than a laptop viewport, so a fractional
       threshold on it can never be met and autoplay would simply never start. */
    if ('IntersectionObserver' in window){
      new IntersectionObserver(function(es){
        tabVisible = es[0].isIntersecting;
        tabVisible ? tabsPlay() : tabsPause();
      }, { threshold:0 }).observe($('.tabsec__panel') || tabSec);
    } else {
      tabVisible = true; tabsPlay();
    }
    /* a backgrounded tab gets no frames, so the fill bar would desync */
    document.addEventListener('visibilitychange', function(){
      document.hidden ? tabsPause() : tabsPlay();
    });
  }

  /* ---------- scenario rail ---------- */
  var rs = $('#railScroll');
  var rCount = $('#railCount');
  var cards = rs ? $$('.scard', rs) : [];

  /* The rail is padded by one gutter and snaps on the x-axis, so scrollLeft never
     starts at 0 and relative scrollBy() fights the snap. Work off which card is
     currently nearest the scrollport edge instead. */
  function railEdge(){
    return rs.getBoundingClientRect().left + (parseFloat(getComputedStyle(rs).paddingLeft) || 0);
  }
  function railIndex(){
    var edge = railEdge();
    var best = 0, bestDist = Infinity;
    cards.forEach(function(c, i){
      var d = Math.abs(c.getBoundingClientRect().left - edge);
      if (d < bestDist){ bestDist = d; best = i; }
    });
    return best;
  }
  /* Tweened by hand: scrollTo({behavior:'smooth'}) is unreliable on an
     overflow container with scroll-snap, so drive scrollLeft per frame. */
  var railAnim = 0, railGuard = 0, RAIL_DUR = 680;
  function railGo(i){
    i = Math.max(0, Math.min(cards.length - 1, i));
    var from = rs.scrollLeft;
    var to = from + (cards[i].getBoundingClientRect().left - railEdge());
    cancelAnimationFrame(railAnim);
    clearTimeout(railGuard);
    if (reduce || from === to){ rs.scrollLeft = to; railSync(); return; }

    /* Snap points fight a per-frame scrollLeft write — the browser keeps nudging
       toward the nearest one, which is what makes the travel look like it is
       stuttering. Suspend snapping for the length of the glide and restore it
       after, so momentum dragging still snaps as before. */
    rs.style.scrollSnapType = 'none';

    var t0 = performance.now();
    railAnim = requestAnimationFrame(function step(now){
      var p = Math.min(1, (now - t0) / RAIL_DUR);
      /* ease-in-out: eases away from rest and settles back into it, rather than
         leaving at full speed the way a plain ease-out does */
      var e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
      rs.scrollLeft = from + (to - from) * e;
      if (p < 1) railAnim = requestAnimationFrame(step);
      else { rs.style.scrollSnapType = ''; railSync(); }
    });
    /* If frames are not being served — background tab, a host that has paused
       compositing — the tween never runs. Land the scroll anyway. */
    railGuard = setTimeout(function(){
      if (Math.abs(rs.scrollLeft - to) > 1){
        cancelAnimationFrame(railAnim);
        rs.scrollLeft = to;
      }
      rs.style.scrollSnapType = '';
      railSync();
    }, RAIL_DUR + 180);
  }
  function railSync(){
    var i = railIndex();
    rCount.textContent = pad(i + 1) + ' / ' + pad(cards.length);
    $('#railPrev').disabled = i === 0;
    $('#railNext').disabled = rs.scrollLeft >= rs.scrollWidth - rs.clientWidth - 2;
  }
  if (rs && cards.length){
    $('#railPrev').addEventListener('click', function(){ railGo(railIndex() - 1); });
    $('#railNext').addEventListener('click', function(){ railGo(railIndex() + 1); });
    rs.addEventListener('scroll', railSync, { passive:true });
    addEventListener('resize', railSync);
    railSync();
  }

  /* ---------- awards carousel ---------- */
  var aTrack = $('#aTrack');
  var aSlides = aTrack ? $$('.aslide', aTrack) : [];
  var aCur = 0;
  function aSync(){
    if (!aTrack) return;
    aTrack.style.transform = 'translateX(' + (-aCur * 100) + '%)';
    $('#aCount').textContent = pad(aCur+1) + ' / ' + pad(aSlides.length);
    $('#aPrev').disabled = aCur === 0;
    $('#aNext').disabled = aCur === aSlides.length - 1;
  }
  if (aTrack){
    $('#aPrev').addEventListener('click', function(){ if (aCur>0){ aCur--; aSync(); } });
    $('#aNext').addEventListener('click', function(){ if (aCur<aSlides.length-1){ aCur++; aSync(); } });
    aSync();
  }

  /* ---------- shop filter ---------- */
  var filts = $$('.filt');
  var itemsEls = $$('.item');
  filts.forEach(function(f){
    f.addEventListener('click', function(){
      filts.forEach(function(x){ x.classList.remove('on'); });
      f.classList.add('on');
      var v = f.getAttribute('data-f');
      itemsEls.forEach(function(it){
        it.hidden = !(v === 'all' || it.getAttribute('data-c') === v);
      });
    });
  });

  /* ---------- newsletter ---------- */
  var toast = $('#toast');
  var newsForm = $('#newsForm');
  if (newsForm) newsForm.addEventListener('submit', function(e){
    e.preventDefault();
    toast.classList.add('show');
    e.target.reset();
    setTimeout(function(){ toast.classList.remove('show'); }, 2800);
  });

  /* ---------- hero film ---------- */
  /* Plays once on load and settles on its final frame. The cut from that frame
     back to the first is a bigger jump than any movement inside the clip, so it
     is deliberately not looped.

     It also plays regardless of prefers-reduced-motion, which the owner asked for
     explicitly: the cover is meant to be moving the moment the page opens. A
     muted eight-second clip that stops by itself is the mildest form of that, but
     it is still motion someone may have asked not to see — the guard belongs here
     if it is ever wanted back. */
  (function(){
    var film = $('.hero__film');
    if (!film) return;
    /* `autoplay muted playsinline` is what every current browser asks for, but a
       handful of states refuse it outright anyway — iOS Low Power Mode, data
       saver, and embedded webviews that hold media until the page is touched.
       The rejection has to be caught either way or it surfaces as an unhandled
       error; catching it also gives somewhere to try again, on the first sign of
       life from the visitor, so the cover is moving as early as it is allowed. */
    var start = function(){
      var p = film.play();
      if (p && p.catch) p.catch(function(){});
    };
    var events = ['pointerdown', 'keydown', 'touchstart', 'scroll'];
    var retry = function(){
      events.forEach(function(ev){ window.removeEventListener(ev, retry); });
      start();
    };
    start();
    /* A resolved play() is not proof of playback. Embedded webviews hand back a
       promise that settles cleanly and then hold the clock at zero until the page
       is touched, so the only reliable check is whether the element actually left
       the paused state. Where it did not, wait for the first sign of life from the
       visitor and start there. */
    setTimeout(function(){
      if (!film.paused) return;
      events.forEach(function(ev){
        window.addEventListener(ev, retry, { passive: true });
      });
    }, 400);
  })();

  /* ---------- apply the stored language, last, so nothing above is half-built ---------- */
  (function(){
    var saved = null;
    try { saved = localStorage.getItem('ona-lang'); } catch(e){}
    if (saved !== 'th' && saved !== 'en'){
      saved = (navigator.language || '').toLowerCase().indexOf('th') === 0 ? 'th' : 'en';
    }
    setLang(saved);
  })();
})();
