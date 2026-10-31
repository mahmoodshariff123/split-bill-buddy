const $ = (s, el = document) => el.querySelector(s);
const view = $('#view');
const COLORS = ['#e8505b', '#13854e', '#8b5cf6', '#1f6fe0', '#d97706', '#0891b2', '#db2777', '#4b5563'];
const SAMPLES = { 'Dinner': 'dinner_receipt.jpg', 'Taxi (THB)': 'taxi_receipt.jpg', 'Groceries': 'grocery_receipt.jpg' };
let CFG = null;
let sdkCurrency = null;

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (cents, cur) => `${cur} ${(cents / 100).toFixed(2)}`;

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || r.statusText));
  return body;
}
const postJSON = (path, data) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });

async function init() {
  CFG = await api('/api/config');
  $('#badges').innerHTML =
    `<span class="badge ${CFG.paypal_mode === 'sandbox' ? 'live' : ''}">PayPal: ${esc(CFG.paypal_mode)}</span>` +
    `<span class="badge ${CFG.ai_mode !== 'demo' ? 'live' : ''}">AI: ${esc(CFG.ai_mode)}</span>`;
  window.addEventListener('hashchange', route);
  route();
}

function route() {
  const m = location.hash.match(/^#\/trip\/(\w+)/);
  (m ? showTrip(m[1]) : showHome()).catch(e => { view.innerHTML = `<div class="alert">${esc(e.message)}</div>`; });
}

async function showHome() {
  const groups = await api('/api/groups');
  view.innerHTML = `
    <div class="card">
      <h1>Trip with friends? Stop doing spreadsheet math.</h1>
      <p class="muted">Snap the receipts, say who had what in normal words, and everyone pays back with one PayPal tap.</p>
      <div class="how">
        <div><b>1</b>Create a trip and add your friends</div>
        <div><b>2</b>Upload receipt photos. AI reads every item</div>
        <div><b>3</b>Type "Sara didn't drink". AI splits fairly</div>
        <div><b>4</b>Everyone settles up with PayPal</div>
      </div>
    </div>
    <div class="grid">
      <div class="card"><h2>Start a new trip</h2>
        <form id="new">
          <label>Trip name</label><input name="tripname" required placeholder="Goa Trip">
          <label>Currency</label>
          <select name="currency">${CFG.currencies.map(c => `<option ${c === 'USD' ? 'selected' : ''}>${c}</option>`).join('')}</select>
          <label>Friends (name + PayPal email where they receive money)</label>
          <div id="members"></div>
          <div class="row">
            <button type="button" class="secondary sm" id="addm">+ Add friend</button>
            <button type="button" class="secondary sm" id="demo">Fill demo trip</button>
          </div>
          <div class="row"><button>Create trip</button></div>
          <div id="err"></div>
        </form>
      </div>
      <div class="card"><h2>Your trips</h2>
        <div class="list">${groups.length ? groups.map(g => `
          <a href="#/trip/${g.id}"><span><b>${esc(g.name)}</b><br>
          <span class="muted small">${g.members.length} friends · ${g.expenses.length} receipts · ${g.settle.length} payments left</span></span>
          <b>${money(g.total_spent, g.currency)}</b></a>`).join('') : '<p class="muted">No trips yet. Create one to start.</p>'}
        </div>
      </div>
    </div>`;
  const addRow = (n = '', e = '') => {
    const d = document.createElement('div');
    d.className = 'mrow';
    d.innerHTML = `<input placeholder="Name" value="${esc(n)}"><input type="email" placeholder="PayPal email (optional)" value="${esc(e)}">`;
    $('#members').append(d);
  };
  [0, 1, 2].forEach(() => addRow());
  $('#addm').onclick = () => addRow();
  $('#demo').onclick = () => {
    $('[name=tripname]').value = 'Goa Trip';
    $('#members').innerHTML = '';
    ['Ali', 'Ravi', 'Sara'].forEach(n => addRow(n));
  };
  $('#new').onsubmit = async ev => {
    ev.preventDefault();
    const f = ev.target;
    const members = [...document.querySelectorAll('.mrow')]
      .map(r => ({ name: r.children[0].value.trim(), email: r.children[1].value.trim() })).filter(m => m.name);
    try {
      const g = await postJSON('/api/groups', { name: f.tripname.value, currency: f.currency.value, members });
      location.hash = `#/trip/${g.id}`;
    } catch (e) { $('#err').innerHTML = `<div class="alert">${esc(e.message)}</div>`; }
  };
}

async function showTrip(id, data) {
  const g = data || await api(`/api/groups/${id}`);
  const idx = n => Math.max(0, g.members.findIndex(m => m.name === n));
  const av = n => `<i class="av" style="background:${COLORS[idx(n) % COLORS.length]}" title="${esc(n)}">${esc((n || '?')[0].toUpperCase())}</i>`;
  const paid = g.payments.filter(p => p.status === 'COMPLETED');

  view.innerHTML = `
    <p><a href="#/">← All trips</a></p>
    <div class="card"><div class="row between" style="margin:0">
      <div><h1>${esc(g.name)}</h1><div>${g.members.map(m => `${av(m.name)} ${esc(m.name)}`).join(' &nbsp; ')}</div></div>
      <div style="text-align:right"><div class="muted">Total spent</div><div class="big">${money(g.total_spent, g.currency)}</div></div>
    </div></div>
    <div class="grid">
      <div class="card"><h2>1. Add a receipt</h2>
        <form id="exp">
          <label>Receipt photo</label><input type="file" name="receipt" accept="image/*">
          <div class="row small muted" style="margin-top:8px">or try a sample:
            ${Object.entries(SAMPLES).map(([k, v]) => `<button type="button" class="secondary sm" data-sample="${v}">${k}</button>`).join('')}
          </div>
          <label>Who paid?</label>
          <select name="paid_by">${g.members.map(m => `<option>${esc(m.name)}</option>`).join('')}</select>
          <label>Anything special? Say it in normal words (optional)</label>
          <textarea name="instruction" placeholder="e.g. Sara didn't drink beer. Sunscreen was only for Ali."></textarea>
          <div class="row"><button id="expbtn">Read receipt & split</button></div>
          <div id="experr"></div>
        </form>
      </div>
      <div class="card"><h2>2. Who owes whom</h2>
        ${g.members.map(m => { const c = g.balances[m.name] || 0; return `
          <div class="bal"><span>${av(m.name)} ${esc(m.name)}</span>
          <b class="${c > 0 ? 'ok' : c < 0 ? 'no' : 'muted'}">${c > 0 ? 'gets back ' + money(c, g.currency) : c < 0 ? 'owes ' + money(-c, g.currency) : 'settled'}</b></div>`; }).join('')}
        <h2 style="margin-top:18px">3. Settle up</h2>
        ${g.settle.length ? g.settle.map((d, i) => `
          <div class="owe"><span>${av(d.from)} <b>${esc(d.from)}</b> pays ${av(d.to)} <b>${esc(d.to)}</b> &nbsp;<b>${money(d.cents, g.currency)}</b></span>
          <div class="pp" id="pp-${i}"></div></div>`).join('')
          : `<p class="ok"><b>✓ Everyone is settled up.</b></p>`}
        ${paid.length ? `<h2 style="margin-top:18px">Payments done</h2><ul class="paid">${paid.map(p => `
          <li>✓ ${esc(p.from)} paid ${esc(p.to)} <b>${money(p.cents, g.currency)}</b> via PayPal${p.mode === 'demo' ? ' (demo)' : ''}
          <br><code>${esc(p.capture_id)}</code></li>`).join('')}</ul>` : ''}
      </div>
    </div>
    <div class="card"><h2>Receipts (${g.expenses.length})</h2>
      ${g.expenses.length ? g.expenses.slice().reverse().map(e => `
        <div class="exp">
          <a href="/uploads/${esc(e.photo)}" target="_blank"><img class="thumb" src="/uploads/${esc(e.photo)}" alt="receipt"></a>
          <div class="grow">
            <div class="row between" style="margin:0"><b>${esc(e.title)}</b>
              <span>${esc(e.currency)} ${Number(e.receipt.total).toFixed(2)} · paid by ${av(e.paid_by)} ${esc(e.paid_by)}</span></div>
            ${e.instruction ? `<div class="muted small">You said: "${esc(e.instruction)}"</div>` : ''}
            <div class="ai"><b>AI:</b> ${esc(e.summary)}</div>
            <table class="items">${e.items.map(it => `<tr>
              <td>${it.quantity > 1 ? esc(it.quantity) + '× ' : ''}${esc(it.name)}</td><td class="r">${Number(it.amount).toFixed(2)}</td>
              <td class="who">${it.people.map(av).join('')}</td><td class="muted small">${esc(it.reason)}</td></tr>`).join('')}
            </table>
            <div class="small" style="margin-top:8px"><b>Shares:</b> ${Object.entries(e.shares).map(([n, c]) => `${esc(n)} ${money(c, g.currency)}`).join(' · ')}</div>
            ${e.warnings.map(w => `<div class="warn">⚠ ${esc(w)}</div>`).join('')}
            <div class="small muted" style="margin-top:6px">Read by ${esc(e.receipt.source)} · split by ${esc(e.ai_source)}
              · <button class="link" data-del="${e.id}">remove</button></div>
          </div>
        </div>`).join('') : '<p class="muted">No receipts yet. Add one on the left.</p>'}
    </div>`;

  let sample = null;
  document.querySelectorAll('[data-sample]').forEach(b => b.onclick = async () => {
    document.querySelectorAll('[data-sample]').forEach(x => x.classList.remove('picked'));
    b.classList.add('picked');
    const blob = await (await fetch(`/samples/${b.dataset.sample}`)).blob();
    sample = new File([blob], b.dataset.sample, { type: 'image/jpeg' });
    $('[name=receipt]').value = '';
  });
  $('[name=receipt]').onchange = () => { sample = null; document.querySelectorAll('[data-sample]').forEach(x => x.classList.remove('picked')); };

  $('#exp').onsubmit = async ev => {
    ev.preventDefault();
    const f = ev.target;
    const file = f.receipt.files[0] || sample;
    if (!file) { $('#experr').innerHTML = '<div class="alert">Choose a receipt photo or a sample first.</div>'; return; }
    const fd = new FormData();
    fd.append('receipt', file);
    fd.append('paid_by', f.paid_by.value);
    fd.append('instruction', f.instruction.value);
    const btn = $('#expbtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>AI is reading the receipt…';
    try {
      showTrip(g.id, await api(`/api/groups/${g.id}/expenses`, { method: 'POST', body: fd }));
    } catch (e) {
      $('#experr').innerHTML = `<div class="alert">${esc(e.message)}</div>`;
      btn.disabled = false;
      btn.textContent = 'Read receipt & split';
    }
  };
  document.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => {
    if (confirm('Remove this receipt?')) showTrip(g.id, await api(`/api/groups/${g.id}/expenses/${b.dataset.del}`, { method: 'DELETE' }));
  });
  renderPayButtons(g);
}

function loadPayPalSdk(currency) {
  if (window.paypal && sdkCurrency === currency) return Promise.resolve();
  return new Promise((resolve, reject) => {
    $('#pp-sdk')?.remove();
    const s = document.createElement('script');
    s.id = 'pp-sdk';
    s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(CFG.paypal_client_id)}&currency=${currency}&components=buttons`;
    s.onload = () => { sdkCurrency = currency; resolve(); };
    s.onerror = () => reject(new Error('Could not load PayPal'));
    document.head.append(s);
  });
}

async function renderPayButtons(g) {
  const order = d => postJSON(`/api/groups/${g.id}/settle/order`, { from_name: d.from, to_name: d.to });
  const capture = orderId => postJSON(`/api/groups/${g.id}/settle/capture`, { order_id: orderId });
  if (!CFG.paypal_client_id) {
    g.settle.forEach((d, i) => {
      const el = $(`#pp-${i}`);
      el.innerHTML = `<button class="green sm">Pay with PayPal (demo)</button>`;
      el.firstChild.onclick = async () => { el.firstChild.disabled = true; showTrip(g.id, await capture((await order(d)).id)); };
    });
    return;
  }
  try { await loadPayPalSdk(g.currency); } catch (e) { return; }
  g.settle.forEach((d, i) => {
    window.paypal.Buttons({
      style: { layout: 'horizontal', height: 38, tagline: false, label: 'pay' },
      createOrder: async () => (await order(d)).id,
      onApprove: async data => showTrip(g.id, await capture(data.orderID)),
      onError: err => alert('PayPal error: ' + err),
    }).render(`#pp-${i}`);
  });
}

init();
