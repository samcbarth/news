/* The Quillmark front-end: theme toggle, ad slots, contact form, client-side feed refresh. */
(function () {
  'use strict';
  var C = window.QM_CONFIG || {};
  var PREFIX = window.QM_PREFIX || '';

  // ---- theme
  var btn = document.querySelector('.theme-btn');
  if (btn) btn.addEventListener('click', function () {
    var root = document.documentElement;
    var dark = root.dataset.theme ? root.dataset.theme === 'dark'
      : window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('qm-theme', root.dataset.theme); } catch (_) {}
  });

  // ---- ads: nothing renders until ADSENSE_CLIENT is set
  var slots = document.querySelectorAll('.ad-slot');
  if (C.ADSENSE_CLIENT && slots.length) {
    var s = document.createElement('script');
    s.async = true; s.crossOrigin = 'anonymous';
    s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + encodeURIComponent(C.ADSENSE_CLIENT);
    document.head.appendChild(s);
    slots.forEach(function (el) {
      var name = el.getAttribute('data-ad-slot-name');
      var ins = document.createElement('ins');
      ins.className = 'adsbygoogle';
      ins.style.display = 'block';
      ins.setAttribute('data-ad-client', C.ADSENSE_CLIENT);
      var id = (C.ADSENSE_SLOTS || {})[name];
      if (id) ins.setAttribute('data-ad-slot', id);
      ins.setAttribute('data-ad-format', 'auto');
      ins.setAttribute('data-full-width-responsive', 'true');
      el.appendChild(ins);
      el.classList.add('on');
      el.removeAttribute('aria-hidden');
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    });
  } else {
    slots.forEach(function (el) { el.remove(); });
  }

  // ---- contact page
  var cslot = document.getElementById('contact-slot');
  if (cslot) {
    if (C.HUBSPOT_FORM_ID) {
      var hs = document.createElement('script');
      hs.src = 'https://js.hsforms.net/forms/embed/v2.js';
      hs.onload = function () {
        cslot.innerHTML = '';
        window.hbspt.forms.create({ region: C.HUBSPOT_REGION || 'na1', portalId: C.HUBSPOT_PORTAL_ID, formId: C.HUBSPOT_FORM_ID, target: '#contact-slot' });
      };
      document.body.appendChild(hs);
    } else if (C.CONTACT_EMAIL) {
      cslot.innerHTML = '<p>Email <a href="mailto:' + C.CONTACT_EMAIL + '">' + C.CONTACT_EMAIL + '</a>.</p>';
    } else {
      cslot.innerHTML = '<p>The contact form is being set up. Please check back soon.</p>';
    }
  }

  // ---- client-side refresh of network feeds
  var dataEl = document.getElementById('qm-items');
  var feeds = window.QM_FEEDS || [];
  if (!dataEl || !feeds.length || !window.fetch) return;
  var known;
  try { known = JSON.parse(dataEl.textContent); } catch (_) { return; }
  var SECTION_NAMES = {};
  document.querySelectorAll('.sections a').forEach(function (a) {
    var m = a.getAttribute('href').match(/\/section\/([^/]+)\//);
    if (m) SECTION_NAMES[m[1]] = a.textContent;
  });
  var SLUG = { realestate: 'real-estate', tools: 'tools-tech', games: 'gaming', streaming: 'streaming', homerepair: 'home', deals: 'deals' };
  function secName(k) { return SECTION_NAMES[SLUG[k]] || k; }
  function esc(s) { return String(s || '').replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function nice(iso) { var d = new Date(iso); return isNaN(d) ? '' : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  function href(it) { return it.external ? it.url : PREFIX + it.url; }
  function meta(it) {
    return '<span class="meta"><time datetime="' + esc(it.date) + '">' + nice(it.date) + '</time> <span class="src' + (it.external ? '' : ' own') + '">' + esc(it.site_label) + '</span></span>';
  }
  function thumb(it) {
    if (it.image) return '<div class="thumb s-' + it.section + '"><img src="' + esc(it.image) + '" alt="" loading="lazy" decoding="async" width="640" height="360"></div>';
    return '<div class="thumb s-' + it.section + ' art" aria-hidden="true"><span>' + esc(secName(it.section).charAt(0)) + '</span></div>';
  }
  function card(it, variant) {
    var summ = variant === 'row' && it.summary ? '<p class="summary">' + esc(it.summary) + '</p>' : '';
    return '<article class="' + variant + '"><a href="' + esc(href(it)) + '"' + (it.external ? ' rel="noopener"' : '') + '>' + thumb(it) +
      '<div class="card-body"><span class="kicker k-' + it.section + '">' + esc(secName(it.section)) + '</span><h3>' + esc(it.title) + '</h3>' + summ + meta(it) + '</div></a></article>';
  }
  function normalize(feed, section) {
    return (feed.items || []).slice(0, 40).map(function (it) {
      var url = it.url || it.external_url;
      if (!url || !it.title || !it.date_published || !/^https:\/\//.test(url)) return null;
      if (!PREFIX && (feed._test || it._test || /^\[TEST\]/.test(it.title))) return null;
      return { title: it.title, url: url, summary: it.summary || '', image: /^https:\/\//.test(it.image || '') ? it.image : '',
        date: it.date_published, section: section, external: true, site_label: url.split('/')[2] };
    }).filter(Boolean);
  }
  Promise.all(feeds.map(function (f) {
    return fetch(f.url, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { return j ? normalize(j, f.section) : []; }).catch(function () { return []; });
  })).then(function (lists) {
    var urls = {}; known.forEach(function (i) { urls[i.url] = 1; });
    var fresh = [].concat.apply([], lists).filter(function (i) { return !urls[i.url]; });
    if (!fresh.length) return;
    var all = known.concat(fresh).sort(function (a, b) { return new Date(b.date) - new Date(a.date); });
    var latest = document.getElementById('latest-list');
    if (latest) {
      var n = latest.children.length || 10;
      latest.innerHTML = all.slice(0, n).map(function (it) {
        return '<li><span class="kicker k-' + it.section + '">' + esc(secName(it.section)) + '</span><a href="' + esc(href(it)) + '"' +
          (it.external ? ' rel="noopener"' : '') + '>' + esc(it.title) + '</a>' + meta(it) + '</li>';
      }).join('');
    }
    document.querySelectorAll('[data-rail]').forEach(function (rail) {
      var k = rail.getAttribute('data-rail');
      if (!fresh.some(function (i) { return i.section === k; })) return;
      var variant = rail.getAttribute('data-variant') || 'card';
      var list = all.filter(function (i) { return i.section === k; });
      rail.innerHTML = list.slice(0, variant === 'row' ? 40 : 4).map(function (it) { return card(it, variant); }).join('');
    });
    var up = document.getElementById('feed-updated');
    if (up) { up.hidden = false; up.textContent = 'Updated ' + new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); }
  });
})();
