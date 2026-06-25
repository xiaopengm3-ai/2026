// Shared: starfield background + white dwarf + music player
(function() {
  var canvas = document.getElementById('stars');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var w, h, particles = [], N = 400;
  var mouse = { x: -9999, y: -9999 }, time = 0;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  window.addEventListener('mousemove', function(e) { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener('mouseleave', function() { mouse.x = -9999; mouse.y = -9999; });
  window.addEventListener('touchmove', function(e) { mouse.x = e.touches[0].clientX; mouse.y = e.touches[0].clientY; }, { passive: true });
  window.addEventListener('touchend', function() { mouse.x = -9999; mouse.y = -9999; });

  for (var i = 0; i < N; i++) {
    var typeRoll = Math.random(), type, r, color, twinkleSpeed, twinkleAmp;
    if (typeRoll < 0.05) {
      type = 'bright'; r = 2 + Math.random() * 2.5;
      color = Math.random() < 0.4 ? [255,235,210] : [210,225,255];
      twinkleSpeed = 0.6 + Math.random() * 0.8; twinkleAmp = 0.35 + Math.random() * 0.35;
    } else if (typeRoll < 0.20) {
      type = 'warm'; r = 0.8 + Math.random() * 1.5;
      var shade = 160 + Math.random() * 95;
      color = [shade + 40, shade - 30, shade - 80];
      twinkleSpeed = 0.4 + Math.random() * 0.8; twinkleAmp = 0.2 + Math.random() * 0.3;
    } else {
      type = 'normal'; r = 0.5 + Math.random() * 1.3;
      color = [180 + Math.random() * 75, 195 + Math.random() * 60, 230 + Math.random() * 25];
      twinkleSpeed = 0.3 + Math.random() * 0.7; twinkleAmp = 0.12 + Math.random() * 0.3;
    }
    particles.push({
      type: type, x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.15, vy: (Math.random() - 0.5) * 0.15,
      r: r, baseR: r, color: color, phase: Math.random() * Math.PI * 2,
      twinkleSpeed: twinkleSpeed, twinkleAmp: twinkleAmp,
      baseOpacity: 0.3 + Math.random() * 0.2
    });
    particles[i].baseX = particles[i].x;
    particles[i].baseY = particles[i].y;
  }

  function drawSky() {
    var grad = ctx.createRadialGradient(w*0.5, h*0.45, 0, w*0.5, h*0.5, Math.max(w,h)*0.85);
    grad.addColorStop(0, '#0d0d24'); grad.addColorStop(0.4, '#08081a');
    grad.addColorStop(0.7, '#040410'); grad.addColorStop(1, '#020208');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, w, h);
  }

  function drawNebulae(t) {
    var patches = [
      { x: 0.22, y: 0.32, r: 0.25, color: [212, 165, 116] },
      { x: 0.74, y: 0.48, r: 0.22, color: [200, 140, 90] },
      { x: 0.38, y: 0.60, r: 0.28, color: [220, 175, 130] },
      { x: 0.62, y: 0.26, r: 0.18, color: [180, 130, 100] }
    ];
    for (var i = 0; i < patches.length; i++) {
      var p = patches[i], px = w * p.x, py = h * p.y, pr = Math.min(w, h) * p.r;
      var grad = ctx.createRadialGradient(px, py, 0, px, py, pr);
      grad.addColorStop(0, 'rgba('+p.color[0]+','+p.color[1]+','+p.color[2]+',0.02)');
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(px, py, pr, 0, Math.PI * 2); ctx.fill();
    }
  }

  function drawWhiteDwarf(t) {
    var cx = w * 0.5, cy = h * 0.45;
    var baseRadius = Math.min(w, h) * 0.7;
    var pulse = 1 + Math.sin(t * 0.0008) * 0.03;
    var r = baseRadius * pulse;

    var halo = ctx.createRadialGradient(cx, cy, r * 0.15, cx, cy, r * 1.4);
    halo.addColorStop(0, 'rgba(160,190,230,0.04)');
    halo.addColorStop(0.5, 'rgba(120,150,200,0.015)');
    halo.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, r * 1.4, 0, Math.PI * 2); ctx.fill();

    var mid = ctx.createRadialGradient(cx, cy, r * 0.02, cx, cy, r * 0.55);
    mid.addColorStop(0, 'rgba(220,235,255,0.12)');
    mid.addColorStop(0.3, 'rgba(180,210,250,0.05)');
    mid.addColorStop(0.7, 'rgba(100,140,200,0.01)');
    mid.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = mid; ctx.beginPath(); ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2); ctx.fill();

    var inner = ctx.createRadialGradient(cx, cy, r * 0.003, cx, cy, r * 0.15);
    inner.addColorStop(0, 'rgba(255,255,255,0.45)');
    inner.addColorStop(0.08, 'rgba(240,245,255,0.25)');
    inner.addColorStop(0.3, 'rgba(200,225,255,0.08)');
    inner.addColorStop(0.6, 'rgba(0,0,0,0)');
    ctx.fillStyle = inner; ctx.beginPath(); ctx.arc(cx, cy, r * 0.15, 0, Math.PI * 2); ctx.fill();

    var core = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 0.02);
    core.addColorStop(0, 'rgba(255,255,255,0.7)');
    core.addColorStop(0.4, 'rgba(255,255,255,0.2)');
    core.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = core; ctx.beginPath(); ctx.arc(cx, cy, r * 0.02, 0, Math.PI * 2); ctx.fill();
  }

  function drawStars(t) {
    for (var i = 0; i < N; i++) {
      var p = particles[i];
      var twinkle = Math.sin(t * 0.001 * p.twinkleSpeed + p.phase) * p.twinkleAmp;
      var opacity = p.baseOpacity + twinkle;
      if (opacity < 0.06) opacity = 0.06; if (opacity > 1) opacity = 1;

      var dx = p.x - mouse.x, dy = p.y - mouse.y;
      var dist = Math.sqrt(dx*dx + dy*dy), range = 130, repelRange = 70;
      if (dist < range && mouse.x > 0) {
        if (dist < repelRange) {
          var force = (1 - dist / repelRange) * 0.08;
          p.vx += (dx / (dist + 0.01)) * force;
          p.vy += (dy / (dist + 0.01)) * force;
          opacity = Math.max(0.06, opacity - 0.35);
        } else {
          var f = (1 - (dist - repelRange) / (range - repelRange)) * 0.02;
          p.vx += (dx / (dist + 0.01)) * f;
          p.vy += (dy / (dist + 0.01)) * f;
        }
        p.r = p.baseR;
      } else { p.r += (p.baseR - p.r) * 0.08; }

      p.x += p.vx; p.y += p.vy;
      p.vx *= 0.996; p.vy *= 0.996;
      p.vx += (p.baseX - p.x) * 0.00008; p.vy += (p.baseY - p.y) * 0.00008;
      p.vx += (Math.random() - 0.5) * 0.005; p.vy += (Math.random() - 0.5) * 0.005;
      if (p.x < -10) p.x = w + 10; if (p.x > w + 10) p.x = -10;
      if (p.y < -10) p.y = h + 10; if (p.y > h + 10) p.y = -10;

      var c = p.color;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba('+c[0]+','+c[1]+','+c[2]+','+opacity+')'; ctx.fill();
      var hlR = p.r * 0.35; if (hlR < 0.3) hlR = 0.3;
      ctx.beginPath(); ctx.arc(p.x - p.r*0.2, p.y - p.r*0.2, hlR, 0, Math.PI*2);
      ctx.fillStyle = 'rgba(255,255,255,' + (opacity * 0.55) + ')'; ctx.fill();

      if (p.type === 'bright' && opacity > 0.5) {
        var fl = p.r * 5, fo = (opacity - 0.5) * 0.5;
        ctx.strokeStyle = 'rgba('+c[0]+','+c[1]+','+c[2]+','+fo+')'; ctx.lineWidth = 0.4;
        ctx.beginPath(); ctx.moveTo(p.x-fl, p.y); ctx.lineTo(p.x+fl, p.y);
        ctx.moveTo(p.x, p.y-fl); ctx.lineTo(p.x, p.y+fl); ctx.stroke();
      }
    }
  }

  function drawConnections() {
    if (mouse.x < 0) return;
    for (var i = 0; i < N; i++) {
      var a = particles[i], dA = Math.hypot(mouse.x - a.x, mouse.y - a.y);
      if (dA > 100) continue;
      for (var j = i + 1; j < N; j++) {
        var b = particles[j], dB = Math.hypot(mouse.x - b.x, mouse.y - b.y);
        if (dB > 100) continue;
        var dx = a.x-b.x, dy = a.y-b.y, dist = Math.sqrt(dx*dx+dy*dy);
        if (dist > 60) continue;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = 'rgba(200,200,230,'+((1-dist/60)*0.1)+')'; ctx.lineWidth = 0.3; ctx.stroke();
      }
    }
  }

  function draw(t) { drawSky(); drawNebulae(t); drawWhiteDwarf(t); drawStars(t); drawConnections(); }
  function loop(ts) { time = ts; draw(ts); requestAnimationFrame(loop); }

  window.addEventListener('resize', function() {
    resize();
    for (var i = 0; i < N; i++) { particles[i].baseX = particles[i].x = Math.random() * w; particles[i].baseY = particles[i].y = Math.random() * h; }
  });
  requestAnimationFrame(loop);

  // Music player
  var bgm = document.getElementById('bgm');
  var musicBtn = document.getElementById('musicBtn');
  var musicPlayer = document.getElementById('musicPlayer');
  if (!bgm || !musicBtn) return;
  var musicIcon = musicBtn.querySelector('.vinyl-icon');
  var playing = false, autoplayAttempted = false;

  function setPlaying(state) {
    playing = state;
    if (state) { musicBtn.classList.add('playing'); musicPlayer.classList.add('visible'); musicIcon.innerHTML = '&#9835;'; }
    else { musicBtn.classList.remove('playing'); musicIcon.innerHTML = '&#9654;'; }
  }
  musicBtn.addEventListener('click', function() {
    if (playing) { bgm.pause(); setPlaying(false); }
    else { bgm.play().then(function() { setPlaying(true); }).catch(function() {}); }
  });
  bgm.volume = 0.35;
  bgm.play().then(function() { setPlaying(true); }).catch(function() { setPlaying(false); });
  function tryAutoplay() { if (!playing && !autoplayAttempted) { autoplayAttempted = true; bgm.play().then(function() { setPlaying(true); }).catch(function() {}); } }
  document.addEventListener('click', function(e) { if (!playing && !autoplayAttempted && e.target !== musicBtn) tryAutoplay(); });
  document.addEventListener('scroll', tryAutoplay, { once: true });
  document.addEventListener('keydown', tryAutoplay, { once: true });
  bgm.addEventListener('play', function() { musicPlayer.classList.add('visible'); setTimeout(function() { musicPlayer.classList.remove('visible'); }, 4000); });
})();
