/* The Quillmark front-end: theme toggle, ad slots, contact form, client-side feed refresh. */
(function () {
  'use strict';
  var C = window.QM_CONFIG || {};
  var PREFIX = window.QM_PREFIX || '';

  // ---- sticky nav: darken + blur once the page scrolls
  var bar = document.querySelector('.topbar');
  if (bar) {
    var onScroll = function () { bar.classList.toggle('scrolled', window.scrollY > 8); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

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
  // HubSpot renders the form inside a same-origin iframe, so page CSS cannot reach it; inject brand styles there.
  var FORM_CSS = [
    'body{background:transparent;color:#fff;font:400 16px/1.5 Inter,"Helvetica Neue",Helvetica,Arial,sans-serif;margin:0}',
    '.hs-form label,.hs-form legend{color:#fff!important;font:700 13px/1.3 Inter,"Helvetica Neue",Arial,sans-serif!important;text-transform:uppercase;letter-spacing:.06em}',
    '.hs-form legend.hs-field-desc{color:rgba(255,255,255,.62)!important;text-transform:none;letter-spacing:0;font-weight:400!important;font-size:13px!important}',
    '.hs-form .hs-form-required{color:#ff9aa8!important}',
    '.hs-form input[type=text],.hs-form input[type=email],.hs-form input[type=tel],.hs-form textarea,.hs-form select{background:#000!important;color:#fff!important;border:1px solid rgba(255,255,255,.22)!important;border-radius:4px!important;padding:12px 14px!important;font:400 16px/1.4 Inter,Arial,sans-serif!important;height:auto!important;box-sizing:border-box;width:100%!important}',
    '.hs-form input:focus,.hs-form textarea:focus{border-color:#8e7cc3!important;outline:none}',
    '.hs-form .hs-button{background:#9a00ff!important;border:1px solid #9a00ff!important;color:#fff!important;border-radius:50px!important;min-height:52px;padding:0 30px!important;font:700 14px/1 Inter,Arial,sans-serif!important;text-transform:uppercase;letter-spacing:.06em;cursor:pointer;transition:transform .15s}',
    '.hs-form .hs-button:hover{transform:translateY(-2px)}',
    '.hs-error-msgs label,.hs-error-msg{color:#ff9aa8!important;text-transform:none!important;letter-spacing:0!important;font-weight:400!important}',
    '.hs-richtext,.legal-consent-container,.legal-consent-container p{color:rgba(255,255,255,.62)!important}',
    '.hs-form a{color:#a99ae0!important}'
  ].join('');
  function brandForm(el) {
    var doc = el && el.ownerDocument;
    if (!doc || doc === document || doc.getElementById('qm-form-css')) return;
    var st = doc.createElement('style');
    st.id = 'qm-form-css';
    st.textContent = FORM_CSS;
    doc.head.appendChild(st);
  }
  var cslot = document.getElementById('contact-slot');
  if (cslot) {
    if (C.HUBSPOT_FORM_ID) {
      var hs = document.createElement('script');
      hs.src = 'https://js.hsforms.net/forms/embed/v2.js';
      hs.onload = function () {
        cslot.innerHTML = '';
        window.hbspt.forms.create({ region: C.HUBSPOT_REGION || 'na1', portalId: C.HUBSPOT_PORTAL_ID, formId: C.HUBSPOT_FORM_ID, target: '#contact-slot',
          onFormReady: function (form) { brandForm(form && (form[0] || form)); } });
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
    if (it.image) return '<div class="thumb s-' + it.section + '"><img src="' + esc(it.image) + '" alt="" loading="lazy" decoding="async" width="640" height="360" onerror="this.remove()"></div>';
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
