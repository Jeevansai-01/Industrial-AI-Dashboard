
let pollHandle = null;
let historyWindow = 60;
let scoreWindow = 60;
let contamination = 0.05;
let lastToken = 0;
let selectedModel = 'iforest';
let viewSeconds = 60;
let _lastViewSeconds = viewSeconds;
let chartsEverRendered = false;
let clockInterval = null; // Handle for the live clock


// --- Alert tuning variables ---
const MIN_ALERT_SCORE = 0.18;
const PERSIST_K = 3;
const PERSIST_M = 10;
let recentAnoms = [];
let lastAckedSeverity = 0;
let alertLatchedUntil = 0;


// --- Plotly layout variables ---
const plotCfg = {
  displayModeBar: false, 
  responsive: true, 
  scrollZoom: false 
};


// Main chart layout
const baseLayout = (yTitle) => ({
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(15, 23, 42, 0.6)',
  margin: { t: 30, r: 20, b: 40, l: 45 },
  font: { color: 'var(--text)', family: 'var(--font-body)' },
  xaxis: {
    title: 'Seconds ago',
    gridcolor: 'var(--stroke)',
    zeroline: false,
    visible: true,
    tickfont: {
      family: 'var(--font-mono)', 
      color: 'var(--muted)'
    }
  },
  yaxis: { 
    title: yTitle, 
    gridcolor: 'var(--stroke)',
    zeroline: false,
    visible: true,
    tickfont: {
      family: 'var(--font-mono)', 
      color: 'var(--muted)'
    }
  },
  legend: {
    orientation: 'h',
    yanchor: 'bottom',
    y: 1.02,
    xanchor: 'right',
    x: 1,
    font: { color: 'var(--text)' }
  },
  hoverlabel: {
    bgcolor: 'rgba(11,19,32,0.95)', 
    bordercolor: 'var(--stroke)', 
    font: { color: 'var(--text)', family: 'var(--font-body)' }
  }
});


// Chart Trace Definitions
const lineTrace = {
  mode: 'lines',
  line: { color: 'var(--accent)', width: 2 },
  hovertemplate: 'Date: %{text}<br>Value: %{y:.2f}<extra></extra>'
};


const anomalyTrace = {
  mode: 'markers',
  name: 'Anomaly',
  marker: { 
    color: 'var(--critical)', 
    size: 8, 
    symbol: 'circle',
    line: { width: 1, color: 'rgba(255, 255, 255, 0.7)' },
    opacity: 1
  },
  hovertemplate: 'Date: %{text}<br>Anomaly: %{y:.2f}<extra></extra>'
};


// Sparkline Definitions
const sparklineLayout = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  margin: { t: 0, r: 0, b: 0, l: 0 },
  xaxis: { visible: false, range: [0, 60] },
  yaxis: { visible: false },
  showlegend: false,
  hovermode: false
};
const sparklineTrace = {
  mode: 'lines',
  line: { color: 'var(--accent)', width: 2 },
  type: 'scatter'
};


function initCharts() {
  if (document.getElementById('tempChart')) {
    Plotly.newPlot('tempChart',
      [
        { ...lineTrace, name: 'Temp', x: [], y: [] },
        { ...anomalyTrace, x: [], y: [] }
      ],
      baseLayout('°C'),
      plotCfg
    );
  }


  if (document.getElementById('pressChart')) {
    Plotly.newPlot('pressChart',
      [
        { ...lineTrace, name: 'Pressure', x: [], y: [] },
        { ...anomalyTrace, x: [], y: [] }
      ],
      baseLayout('bar'),
      plotCfg
    );
  }


  if (document.getElementById('rpmChart')) {
    Plotly.newPlot('rpmChart',
      [
        { ...lineTrace, name: 'RPM', x: [], y: [] },
        { ...anomalyTrace, x: [], y: [] }
      ],
      baseLayout('RPM'),
      plotCfg
    );
  }


  // Initialize sparklines
  if (document.getElementById('tempSpark')) {
    Plotly.newPlot('tempSpark', [{ ...sparklineTrace, x: [], y: [] }], sparklineLayout, plotCfg);
  }
  if (document.getElementById('pressSpark')) {
    Plotly.newPlot('pressSpark', [{ ...sparklineTrace, x: [], y: [] }], sparklineLayout, plotCfg);
  }
  if (document.getElementById('rpmSpark')) {
    Plotly.newPlot('rpmSpark', [{ ...sparklineTrace, x: [], y: [] }], sparklineLayout, plotCfg);
  }
}



function toHMSutc(ms){ return new Date(ms).toUTCString().split(' ')[4]; }


function toISOutc(ms){
  const d = new Date(ms);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} UTC`;
}


function startLiveClock() {
  if (clockInterval) clearInterval(clockInterval);


  function updateClock() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const timeString = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    
    document.querySelectorAll('.live-clock').forEach(el => {
      el.textContent = timeString;
    });
  }
  updateClock();
  clockInterval = setInterval(updateClock, 1000);
}



let backoffMs = 1000;
const MIN_MS = 1000, MAX_MS = 15000;



function showToast(message, opts = {}) {
  const host = document.getElementById('toastHost');
  if (!host) return;
  const role = opts.role || 'alert';
  const timeout = opts.timeout ?? 3500;
  const variant = opts.variant || 'error';


  const el = document.createElement('div');
  el.className = `toast ${variant}`;
  el.setAttribute('role', role);
  el.setAttribute('aria-atomic', 'true');
  el.innerHTML = `
    <div class="msg">${escapeHtml(message)}</div>
    <button class="close" aria-label="Close notification" title="Close">×</button>
  `;
  host.appendChild(el);


  requestAnimationFrame(() => el.classList.add('show'));


  const remove = () => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 180);
  };
  el.querySelector('.close').addEventListener('click', remove);


  if (timeout > 0) {
    const t = setTimeout(remove, timeout);
    el.addEventListener('mouseenter', () => clearTimeout(t), { once: true });
  }
}


function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}



async function fetchAndUpdate() {
  const token = ++lastToken;
  const root = document.querySelector('.activity');
  root?.classList.add('busy');
  try {
    const [histResp, scoreResp] = await Promise.all([
      fetch(`/history?n=${viewSeconds}&_t=${Date.now()}`), 
      fetch(`/scores_for_window?n=${scoreWindow}&c=${contamination.toFixed(3)}&model=${encodeURIComponent(selectedModel)}&_t=${Date.now()}`)
    ]);


    if (token !== lastToken) return;


    const [histPayload, scorePayload] = await Promise.all([histResp.json(), scoreResp.json()]);


    const histRows = Array.isArray(histPayload) ? histPayload : (histPayload.rows || []);
    const scoredNewestFirst = Array.isArray(scorePayload) ? scorePayload : (scorePayload.rows || []);


    const histAsc = [...histRows].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
    const times = histAsc.map(r => Date.parse(r.timestamp));
    const temps = histAsc.map(r => Number(r.temperature));
    const press = histAsc.map(r => Number(r.pressure));
    const rpm   = histAsc.map(r => Number(r.motor_speed));


    const dataNow = times.length ? times[times.length - 1] : Date.now();
    const liveNow = Number((histPayload && histPayload.server_now) || Date.now());
    const replayNow = Number((histPayload && histPayload.replay_now) || 0);
    const viewNow = isReplay ? (replayNow || liveNow) : liveNow;
    
    const newest = times.length ? times[times.length - 1] : 0;
    if (fetchAndUpdate.lastTs === undefined) fetchAndUpdate.lastTs = -1;
    if (fetchAndUpdate.lastCutoff === undefined) fetchAndUpdate.lastCutoff = 0;


    const prevNewest = fetchAndUpdate.lastTs ?? 0;
    const prevCutoff = fetchAndUpdate.lastCutoff ?? 0;


    const cutoff = dataNow - viewSeconds * 1000;
    const cutoffBucket = Math.floor(cutoff / 1000);


    const redrawNeeded = chartsEverRendered === false
      || (newest !== prevNewest)
      || (cutoffBucket !== Math.floor(prevCutoff / 1000));


    if (histAsc.length > 0) {
      const latest = histAsc[histAsc.length - 1];
      const kpiTemp = document.getElementById('kpiTemp');
      const kpiPress = document.getElementById('kpiPress');
      const kpiRpm = document.getElementById('kpiRpm');
      
      if (kpiTemp) kpiTemp.textContent = Number(latest.temperature).toFixed(1);
      if (kpiPress) kpiPress.textContent = Number(latest.pressure).toFixed(2);
      if (kpiRpm) kpiRpm.textContent = Number(latest.motor_speed).toFixed(0);


      const latestTempEl = document.getElementById('latest-temp-reading');
      const latestPressEl = document.getElementById('latest-press-reading');
      const latestRpmEl = document.getElementById('latest-rpm-reading');


      if (latestTempEl) latestTempEl.textContent = `${Number(latest.temperature).toFixed(1)} °C`;
      if (latestPressEl) latestPressEl.textContent = `${Number(latest.pressure).toFixed(2)} bar`;
      if (latestRpmEl) latestRpmEl.textContent = `${Number(latest.motor_speed).toFixed(0)} RPM`;
    }


    const axT = [], at = [];
    const axP = [], apy = [];
    const axR = [], ary = [];
    for (const r of scoredNewestFirst) {
      if (!r?.is_anomaly) continue;
      const t = Date.parse(r.timestamp);
      if (t >= cutoff) {
        axT.push(t); at.push(Number(r.temperature));
        axP.push(t); apy.push(Number(r.pressure));
        axR.push(t); ary.push(Number(r.motor_speed));
      }
    }
    await updateBadges(scoredNewestFirst, null); 
    
    const keepIdx = [];
    for (let i = 0; i < times.length; i++) if (times[i] >= cutoff) keepIdx.push(i);


    const times60 = keepIdx.map(i => {
        const timestamp = times[i];
        const secondsAgo = (viewNow - timestamp) / 1000;
        return viewSeconds - secondsAgo;
    });


    const temps60 = keepIdx.map(i => temps[i]);
    const press60 = keepIdx.map(i => press[i]);
    const rpm60   = keepIdx.map(i => rpm[i]);


    if (times.length > 0 && times60.length < 2) {
      const tLast = times[times.length - 1];
      const yT = temps[temps.length - 1], yP = press[press.length - 1], yR = rpm[rpm.length - 1];
      const tPrev = times.length > 1 ? times[times.length - 2] : tLast - 1000;
      const yTprev = temps.length > 1 ? temps[temps.length - 2] : yT;
      const yPprev = press.length > 1 ? press[press.length - 2] : yP;
      const yRprev = rpm.length > 1 ? rpm[rpm.length - 2] : yR;


      const xLast = viewSeconds - ((viewNow - tLast) / 1000);
      const xPrev = viewSeconds - ((viewNow - tPrev) / 1000);
      times60.splice(0, times60.length, xPrev, xLast);


      temps60.splice(0, temps60.length, yTprev, yT);
      press60.splice(0, press60.length, yPprev, yP);
      rpm60.splice(0, rpm60.length, yRprev, yR);
    }


    const axT60 = [], at60 = [], axP60 = [], apy60 = [], axR60 = [], ary60 = [];
    for (let i = 0; i < axT.length; i++) {
        const timestamp = axT[i];
        const secondsAgo = (viewNow - timestamp) / 1000;
        axT60.push(viewSeconds - secondsAgo);
        at60.push(at[i]);
    }
    for (let i = 0; i < axP.length; i++) {
        const timestamp = axP[i];
        const secondsAgo = (viewNow - timestamp) / 1000;
        axP60.push(viewSeconds - secondsAgo);
        apy60.push(apy[i]);
    }
    for (let i = 0; i < axR.length; i++) {
        const timestamp = axR[i];
        const secondsAgo = (viewNow - timestamp) / 1000;
        axR60.push(viewSeconds - secondsAgo);
        ary60.push(ary[i]);
    }


    const timesISO60 = keepIdx.map(i => toISOutc(times[i]));
    const axTiso60 = axT60.map((x, i) => toISOutc(axT[i]));
    const axPiso60 = axP60.map((x, i) => toISOutc(axP[i]));
    const axRiso60 = axR60.map((x, i) => toISOutc(axR[i]));


    
    if (redrawNeeded) {
      
      if (document.getElementById('tempSpark')) {
        Plotly.react('tempSpark', [{ ...sparklineTrace, x: times60, y: temps60 }], sparklineLayout, plotCfg);
      }
      if (document.getElementById('pressSpark')) {
        Plotly.react('pressSpark', [{ ...sparklineTrace, x: times60, y: press60 }], sparklineLayout, plotCfg);
      }
      if (document.getElementById('rpmSpark')) {
        Plotly.react('rpmSpark', [{ ...sparklineTrace, x: times60, y: rpm60 }], sparklineLayout, plotCfg);
      }


      // Update Main Charts
      if (document.getElementById('tempChart')) {
        Plotly.react('tempChart',
          [
            { ...lineTrace, name: 'Temp', x: times60, y: temps60, text: timesISO60 },
            { ...anomalyTrace, x: axT60, y: at60, text: axTiso60, hovertemplate: 'Date: %{text}<br>Anomaly — Temp: %{y:.2f}<extra></extra>' }
          ],
          baseLayout('°C'),
          plotCfg
        );
      }
      if (document.getElementById('pressChart')) {
        Plotly.react('pressChart',
          [
            { ...lineTrace, name: 'Pressure', x: times60, y: press60, text: timesISO60, hovertemplate: 'Date: %{text}<br>Pressure: %{y:.2f}<extra></extra>' },
            { ...anomalyTrace, x: axP60, y: apy60, text: axPiso60, hovertemplate: 'Date: %{text}<br>Anomaly — Pressure: %{y:.2f}<extra></extra>' }
          ],
          baseLayout('bar'),
          plotCfg
        );
      }
      if (document.getElementById('rpmChart')) {
        Plotly.react('rpmChart',
          [
            { ...lineTrace, name: 'RPM', x: times60, y: rpm60, text: timesISO60, hovertemplate: 'Date: %{text}<br>RPM: %{y:.0f}<extra></extra>' },
            { ...anomalyTrace, x: axR60, y: ary60, text: axRiso60, hovertemplate: 'Date: %{text}<br>Anomaly — RPM: %{y:.0f}<extra></extra>' }
          ],
          baseLayout('RPM'),
          plotCfg
        );
      }
      chartsEverRendered = true;
      fetchAndUpdate.lastTs = newest;
      fetchAndUpdate.lastCutoff = cutoff;
    }


    const steps  = 6;
    const tickVals = [], tickText = [];
    for (let i = 0; i <= steps; i++) {
        const val = (i / steps) * viewSeconds;
        const sec = (i / steps) * viewSeconds;
        tickVals.push(val);
        tickText.push(sec === viewSeconds ? '0' : `-${Math.round(viewSeconds - sec)}`);
    }


    const slidingAxis = {
      'xaxis.type': 'linear',
      'xaxis.range': [0, viewSeconds],
      'xaxis.tickmode': 'array',
      'xaxis.tickvals': tickVals,
      'xaxis.ticktext': tickText,
      'xaxis.title': 'Seconds ago'
    };


    if (document.getElementById('tempChart')) Plotly.relayout('tempChart', slidingAxis);
    if (document.getElementById('pressChart')) Plotly.relayout('pressChart', slidingAxis);
    if (document.getElementById('rpmChart')) Plotly.relayout('rpmChart', slidingAxis);


    const sparkAxis = { 'xaxis.range': [0, viewSeconds] };
    if (document.getElementById('tempSpark')) Plotly.relayout('tempSpark', sparkAxis);
    if (document.getElementById('pressSpark')) Plotly.relayout('pressSpark', sparkAxis);
    if (document.getElementById('rpmSpark')) Plotly.relayout('rpmSpark', sparkAxis);



    let maxScore = 0;
    let anomCount = 0;
    for (const r of scoredNewestFirst) {
      if (r?.is_anomaly) {
        anomCount += 1;
        maxScore = Math.max(maxScore, Number(r.anomaly_score || 0));
      }
    }
    pushAnomFlag(anomCount > 0); 


    if (shouldShowAlert(maxScore)) {
      showOverlay(maxScore, `Anomalies detected; max score ${maxScore.toFixed(3)}`);
    } else {
      if (Date.now() >= alertLatchedUntil && recentAnoms.reduce((a,b)=>a+b,0) === 0) {
        hideOverlay();
      }
    }


    const statusValEl = document.getElementById('statusValue');
    const statusPanelEl = document.getElementById('systemStatus');
    if (statusValEl && statusPanelEl) {
      let status = 'NOMINAL';
      let statusClass = 'status-nominal';
      
      const anomTableRows = scoredNewestFirst.filter(r => r.is_anomaly);


      if (anomTableRows.length > 0 && anomTableRows.length < 3) {
        status = 'WARNING';
        statusClass = 'status-warning';
      } else if (anomTableRows.length >= 3) {
        status = 'CRITICAL';
        statusClass = 'status-critical';
      }
      
      statusValEl.textContent = status;
      statusPanelEl.className = 'status-card '  + statusClass;
    }


    if (token !== lastToken) return;
    if (document.getElementById('viewOverview').classList.contains('active')) {
      await refreshAnomalyTable(scoredNewestFirst.filter(r => r.is_anomaly));
    }


    const lastTs = times.length ? new Date(times[times.length-1]).toUTCString().split(' ')[4] : '--';
    const statusEl = document.getElementById('statusText');
    if (statusEl) {
        statusEl.textContent =
        `Updated at ${new Date().toLocaleTimeString()} • last sample (UTC): ${lastTs}`;
    }


    backoffMs = MIN_MS;


  } catch (err) {
    console.error("Fetch/Update Error:", err);
    const statusEl = document.getElementById('statusText');
    if (statusEl) statusEl.textContent = `Update Error: ${err.message}. Retrying...`;
    backoffMs = Math.min(MAX_MS, backoffMs * 1.5);
  } finally {
    root?.classList.remove('busy');
  }
}


function pushAnomFlag(flag){
  recentAnoms.push(flag ? 1 : 0);
  if (recentAnoms.length > PERSIST_M) recentAnoms.shift();
}


function shouldShowAlert(maxScore){
  const now = Date.now();
  if (now < alertLatchedUntil) return false;
  const sum = recentAnoms.reduce((a,b)=>a+b,0);
  if (sum < PERSIST_K) return false;
  if (maxScore < MIN_ALERT_SCORE) return false;
  if (maxScore <= lastAckedSeverity) return false;
  return true;
}


function showOverlay(maxScore, detailsText){
  const o = document.getElementById('alertOverlay');
  const d = document.getElementById('alertDetails');
  if (!o) return;
  if (d) d.textContent = detailsText || `Max anomaly score: ${maxScore.toFixed(3)}`;
  o.style.display = 'flex';
}


function hideOverlay(){
  const o = document.getElementById('alertOverlay');
  if (o) o.style.display = 'none';
}


function resetUIStatus(){
  ['kpiTemp','kpiPress','kpiRpm'].forEach(id => { const el=document.getElementById(id); if (el) el.textContent='--'; });
  const ka=document.getElementById('kpiAnom'); if (ka) ka.textContent='--';
  const dot=document.getElementById('globalAlert'); if (dot) dot.style.display='none';
  ['badgeWinTemp','badgeWinPress','badgeWinRpm'].forEach(id => { const el=document.getElementById(id); if (el){ el.className='badge'; el.textContent=''; }});


  ['latest-temp-reading', 'latest-press-reading', 'latest-rpm-reading'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.textContent = '--';
  });


  const statusValEl = document.getElementById('statusValue');
  const statusPanelEl = document.getElementById('systemStatus');
  if (statusValEl && statusPanelEl) {
    statusValEl.textContent = '...';
    statusPanelEl.className = 'kpi glass';
  }
  const lastAnomEl = document.getElementById('lastAnomalyTime');
  if(lastAnomEl) lastAnomEl.textContent = '--';
}



async function setMode(mode){
  await fetch('/mode', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ mode }) });
  resetUIStatus();
  initCharts();
  
  const anomBody = document.querySelector('#anomTable tbody');
  if (anomBody) anomBody.innerHTML = '';


  stopPolling();
  backoffMs = MIN_MS;
  setReplayControlsEnabled(mode === 'replay');
  startPolling();

  if (mode === 'replay') {
    if (playBtn) {
      playBtn.textContent = 'Pause';
      playBtn.dataset.playing = '1';
    }
  } else { 
    if (playBtn) {
      playBtn.textContent = 'Play';
      playBtn.dataset.playing = '0';
    }
  }
}


let speedSel, playBtn, stepBack, stepFwd, jumpInp, jumpBtn;
let isReplay = false;


function setReplayControlsEnabled(enabled){
  isReplay = enabled;
  [playBtn, stepBack, stepFwd, speedSel, jumpInp, jumpBtn].forEach(el => {
    if (el) el.disabled = !enabled;
  });
  document.querySelector('.replay-pack')?.classList.toggle('active', enabled);
}


async function replayStep(delta){
  try {
    const resp = await fetch('/replay/step', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ delta })
    });
    if (!resp.ok) {
      const msg = `Step failed: HTTP ${resp.status}`;
      document.getElementById('statusText').textContent = msg;
      return;
    }
    await fetchAndUpdate();
  } catch (e) {
    const statusEl = document.getElementById('statusText');
    if(statusEl) statusEl.textContent = `Step error: ${e.message}`;
  }
}



async function refreshAnomalyTable(anomalyRows) {
  try {
    let rows = anomalyRows;
    
    if (!rows) {
      const resp = await fetch(`/anomalies?n=${scoreWindow}&c=${contamination.toFixed(3)}&model=${encodeURIComponent(selectedModel)}&_t=${Date.now()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      rows = await resp.json();
    }


    rows.sort((a, b) => Number(b.anomaly_score || 0) - Number(a.anomaly_score || 0));


    const lastAnomalyEl = document.getElementById('lastAnomalyTime');
    if (lastAnomalyEl) {
      if (rows.length > 0) {
        lastAnomalyEl.textContent = toISOutc(Date.parse(rows[0].timestamp));
      } else {
        lastAnomalyEl.textContent = 'None in window';
      }
    }


    rows = rows.slice(0, 15); 


    const body = document.querySelector('#anomTable tbody');
    if (!body) return;
    
    const newTbody = document.createElement('tbody');
    rows.forEach((r) => {
      if (!r || !r.timestamp) return;
      const tr = newTbody.insertRow();
      const score = Number(r.anomaly_score ?? 0);
      if (score >= 0.20) {
        tr.className = 'severity-high';
      } else if (score >= 0.10) {
        tr.className = 'severity-medium';
      }


      const t = Date.parse(r.timestamp);
      const dtText = toISOutc(t);
      tr.innerHTML = `
        <td>${dtText}</td>
        <td>${Number(r.temperature).toFixed(2)}</td>
        <td>${Number(r.pressure).toFixed(2)}</td>
        <td>${Number(r.motor_speed).toFixed(0)}</td>
        <td>${score.toFixed(3)}</td>
      `;
    });
    
    body.innerHTML = newTbody.innerHTML; 


    const box = document.getElementById('anomContainer');
    if (box) box.scrollTop = 0;
  } catch (e) {
    console.warn('Anomaly table refresh failed:', e);
  }
}



async function updateBadges(scoredNewestFirst, visibleSecs = null) {
  try {
    const scoredNF = Array.isArray(scoredNewestFirst) ? scoredNewestFirst : [];
    
    const toSec = d => Math.floor(Date.parse(d)/1000);
    const anyAnom = scoredNF.some(r => r?.is_anomaly && (!visibleSecs || visibleSecs.has(toSec(r.timestamp))));


    const dot = document.getElementById('globalAlert');
    if (dot) dot.style.display = anyAnom ? 'inline-block' : 'none';


    const badgeText = anyAnom ? 'Anomaly' : '';
    ['badgeWinOverview', 'badgeWinTemp', 'badgeWinPress', 'badgeWinRpm'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.className = anyAnom ? 'badge alert' : 'badge';
      el.textContent = badgeText;
    });


    const kpiAnom = document.getElementById('kpiAnom');
    if (kpiAnom) kpiAnom.textContent = anyAnom ? 'Yes' : 'No';
  } catch(e) {
    console.warn('Badge update failed:', e);
  }
}



async function loadDefaults() {
  try {
    const resp = await fetch('/config?_t=' + Date.now());
    if (!resp.ok) return;
    const cfg = await resp.json();


    if (cfg.default_model) {
      selectedModel = String(cfg.default_model).toLowerCase();
      const ds = document.getElementById('detectorSelect');
      if (ds) ds.value = selectedModel;
    }


    if (cfg.contamination_default) {
      contamination = Number(cfg.contamination_default);
      const s = document.getElementById('contSlider');
      if (s) s.value = contamination.toFixed(2);
      const c = document.getElementById('contVal');
      if (c) c.textContent = contamination.toFixed(2);
      const rc = document.getElementById('rangeCont');
      if (rc) rc.value = contamination.toFixed(2);
    }
    if (cfg.view_window_seconds) {
        viewSeconds = Number(cfg.view_window_seconds);
        const sel = document.getElementById('viewWindowSelect');
        if (sel) sel.value = String(viewSeconds);
    }
    if (cfg.score_window_default) {
      scoreWindow = Number(cfg.score_window_default);
      const sel2 = document.getElementById('scoreWindowSelect');
      if (sel2) sel2.value = String(scoreWindow);
    }
    if (cfg.history_window_default) {
      historyWindow = Number(cfg.history_window_default);
    }
  } catch(e) { console.warn('loadDefaults failed', e); }
}



async function persistConfig(kv) {
  try {
    await fetch('/config', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(kv)
    });
  } catch(e) { console.warn('persistConfig failed', e); }
}


function scheduleNextTick() {
  pollHandle = setTimeout(async () => {
    await fetchAndUpdate();
    scheduleNextTick();
  }, backoffMs);
}


function startPolling() {
  if (pollHandle) return;
  backoffMs = MIN_MS;
  fetchAndUpdate().then(() => scheduleNextTick());
}


function stopPolling() {
  if (pollHandle) {
    clearTimeout(pollHandle);
    pollHandle = null;
  }
}


function tableToCsv() {
  const rows = [];
  const header = ['Time','Temp (°C)','Pressure (bar)','RPM','Score'];
  rows.push(header.join(','));


  document.querySelectorAll('#anomTable tbody tr').forEach(tr => {
    const cols = Array.from(tr.children).map(td => {
      const txt = td.textContent.trim();
      return /[",\n]/.test(txt) ? `"${txt.replace(/"/g, '""')}"` : txt;
    });
    rows.push(cols.join(','));
  });
  return rows.join('\n');
}


function downloadCsv(csv) {
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'anomalies_table.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}



function toUtcIsoFromLocalInput(value){
  const local = new Date(value);
  return new Date(local.getTime() - local.getTimezoneOffset()*60000).toISOString();
}


function setActiveTab(tabId) {
  document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
  document.querySelectorAll('.view-content').forEach(view => view.classList.remove('active'));


  document.getElementById(`navTab${tabId}`)?.classList.add('active');
  const view = document.getElementById(`view${tabId}`);
  if (view) {
    view.classList.add('active');
  }


  if (tabId === 'Temp') {
    Plotly.Plots.resize('tempChart');
  } else if (tabId === 'Pressure') {
    Plotly.Plots.resize('pressChart');
  } else if (tabId === 'Rpm') {
    Plotly.Plots.resize('rpmChart');
  }
}


document.addEventListener('DOMContentLoaded', () => {


  document.getElementById('alertAckBtn')?.addEventListener('click', () => {
    alertLatchedUntil = Date.now() + 2*60*1000;
    hideOverlay();
  });


  document.getElementById('startLiveBtn')?.addEventListener('click', () => setMode('live'));
  document.getElementById('stopLiveBtn')?.addEventListener('click', stopPolling);
  document.getElementById('startReplayBtn')?.addEventListener('click', () => setMode('replay'));
  document.getElementById('resetReplayBtn')?.addEventListener('click', async () => {
    await fetch('/replay/reset', { method:'POST' });
    backoffMs = MIN_MS; 
    await fetchAndUpdate();
  });


  speedSel = document.getElementById('replaySpeed');
  playBtn  = document.getElementById('replayPlayBtn');
  stepBack = document.getElementById('replayStepBack');
  stepFwd  = document.getElementById('replayStepFwd');
  jumpInp  = document.getElementById('replayJumpTs');
  jumpBtn  = document.getElementById('replayJumpBtn');


  if (playBtn) { playBtn.textContent = 'Play'; playBtn.dataset.playing = '0'; }
  
  speedSel?.addEventListener('change', async e => {
    const stride = Number(e.target.value || 1);
    await persistConfig({ replay_stride: stride });
  });


  playBtn?.addEventListener('click', async () => {
    const isPlaying = playBtn.dataset.playing === '1';
    if (isPlaying) {
      stopPolling();
      playBtn.dataset.playing = '0';
      playBtn.textContent = 'Play';
    } else {
      if (!isReplay) await setMode('replay');
      startPolling();
      playBtn.dataset.playing = '1';
      playBtn.textContent = 'Pause';
    }
  });


  stepBack?.addEventListener('click', async () => {
    if (!isReplay) await setMode('replay');
    const stride = Number(speedSel?.value || 1);
    await replayStep(-Math.abs(stride));
  });


  stepFwd?.addEventListener('click', async () => {
    if (!isReplay) await setMode('replay');
    const stride = Number(speedSel?.value || 1);
    await replayStep(+stride);
  });


  jumpBtn?.addEventListener('click', async () => {
    if (!jumpInp?.value) return;
    await setMode('replay');
    const local = new Date(jumpInp.value);
    const isoUtc = new Date(local.getTime() - local.getTimezoneOffset()*60000).toISOString();
    await fetch('/replay/seek?ts=' + encodeURIComponent(isoUtc));
    await fetchAndUpdate();
  });


  setReplayControlsEnabled(false);


  document.getElementById('detectorSelect')?.addEventListener('change', async e => {
    selectedModel = e.target.value || 'iforest';
    await persistConfig({ default_model: selectedModel });
    fetchAndUpdate();
  });


  document.getElementById('contSlider').addEventListener('input', e => {
    contamination = Number(e.target.value);
    document.getElementById('contVal').textContent = contamination.toFixed(2);
  });
  document.getElementById('contSlider').addEventListener('change', e => {
    contamination = Number(e.target.value);
    persistConfig({ contamination_default: contamination.toFixed(2) });
    fetchAndUpdate(); 
  });


  document.getElementById('viewWindowSelect').addEventListener('change', e => {
    viewSeconds = Number(e.target.value);
    persistConfig({ view_window_seconds: viewSeconds });
    fetchAndUpdate();
  });


  document.getElementById('scoreWindowSelect').addEventListener('change', e => {
    scoreWindow = Number(e.target.value);
    persistConfig({ score_window_default: scoreWindow });
    refreshAnomalyTable(); 
  });


  document.getElementById('copyCsvBtn').addEventListener('click', () => {
    const csv = tableToCsv();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(csv).then(() => {
        showToast('Table copied to clipboard', { variant: 'info' });
      }).catch(() => downloadCsv(csv));
    } else {
      downloadCsv(csv);
    }
  });
  
  document.getElementById('exportRangeBtn')?.addEventListener('click', () => {
    const fromEl = document.getElementById('rangeFrom');
    const toEl = document.getElementById('rangeTo');
    if (!fromEl?.value || !toEl?.value) {
      showToast('Select From and To before exporting', { variant: 'error', role: 'alert', timeout: 4000 });
      return;
    }
    const fromIso = toUtcIsoFromLocalInput(fromEl.value);
    const toIso = toUtcIsoFromLocalInput(toEl.value);
    const url = `/export?from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}`;
    window.location = url;
  });


  document.getElementById('reportRangeBtn')?.addEventListener('click', () => {
    const fromEl = document.getElementById('rangeFrom');
    const toEl = document.getElementById('rangeTo');
    const cEl = document.getElementById('rangeCont');
    if (!fromEl?.value || !toEl?.value) {
      showToast('Select From and To before generating PDF', { variant: 'error', role: 'alert', timeout: 4000 });
      return;
    }
    const fromIso = toUtcIsoFromLocalInput(fromEl.value);
    const toIso = toUtcIsoFromLocalInput(toEl.value);
    const c = Math.max(0.001, Math.min(0.5, Number(cEl?.value || contamination)));
    const url = `/report?from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}&c=${c.toFixed(3)}`;
    window.open(url, '_blank');
  });


  window.addEventListener('resize', () =>
    ['tempChart','pressChart','rpmChart'].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.offsetParent !== null) {
          Plotly.Plots.resize(el);
        }
    }));


  document.getElementById('exportBtn').addEventListener('click', () => {
    window.location = `/export?n=${viewSeconds}&model=${encodeURIComponent(selectedModel)}`; 
  });


  document.getElementById('reportBtn').addEventListener('click', () => {
    const url = `/report?n=${scoreWindow}&c=${contamination.toFixed(3)}&model=${encodeURIComponent(selectedModel)}`;
    showToast('Opening PDF report...', { variant: 'info', role: 'status', timeout: 1800 });
    window.open(url, '_blank');
  });


  document.getElementById('navTabOverview').addEventListener('click', () => setActiveTab('Overview'));
  document.getElementById('navTabTemp').addEventListener('click', () => setActiveTab('Temp'));
  document.getElementById('navTabPressure').addEventListener('click', () => setActiveTab('Pressure'));
  document.getElementById('navTabRpm').addEventListener('click', () => setActiveTab('Rpm'));


  // Boot
  loadDefaults().then(() => {
    _lastViewSeconds = Number(document.getElementById('viewWindowSelect')?.value || viewSeconds);
    initCharts();
    setActiveTab('Overview');
    startPolling();
    startLiveClock();
  });


});

