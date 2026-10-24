// K.K. Allianze KPPP Platform — Frontend Engine
let allTendersData = [];
let companyData = null;

function switchTab(tabId) {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === tabId);
  });

  if (tabId === 'tab-tenders' && allTendersData.length === 0) {
    loadAllTenders();
  } else if (tabId === 'tab-company' && !companyData) {
    loadCompanyData();
  } else if (tabId === 'tab-my-tenders') {
    loadMyTenders();
  } else if (tabId === 'tab-coverage') {
    loadCoverage();
  }
}

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// Helper for status badge
function getStatusBadge(status) {
  const st = (status || 'UNKNOWN').toUpperCase();
  let cls = 'badge-closed';
  if (st === 'PUBLISHED') cls = 'badge-published';
  else if (st === 'AWARDED') cls = 'badge-awarded';
  else if (st === 'EVALUATION_COMPLETED') cls = 'badge-eval';
  return `<span class="badge ${cls}">${status || '—'}</span>`;
}

// 1. DASHBOARD
async function loadDashboard() {
  const res = await fetch('/dashboard').then(r => r.json());
  const s = res.stats || {};

  const cards = [
    { label: 'In-Scope Tenders', val: s.tender_count ?? 0, sub: '17 Focus Departments' },
    { label: 'Departments', val: s.department_count ?? 17, sub: 'Strictly Scoped' },
    { label: 'My Tenders', val: s.my_tenders_count ?? 0, sub: 'K.K. Allianze Participated' },
    { label: 'Total Won Value', val: `₹${(s.total_won_val || 0).toLocaleString('en-IN')}`, sub: 'Evaluated L1 Value' },
    { label: 'New / Unknown', val: s.unknown_count ?? 0, sub: 'Not in Baseline Excel' },
  ];

  document.getElementById('statsGrid').innerHTML = cards.map(c => `
    <div class="card">
      <h3>${c.label}</h3>
      <strong>${c.val}</strong>
      <div class="sub">${c.sub}</div>
    </div>
  `).join('');

  document.getElementById('dashTenderTable').innerHTML = (res.tenders || []).slice(0, 8).map(t => `
    <tr>
      <td><strong>${t.tender_number}</strong></td>
      <td>${t.department_code || '—'}</td>
      <td>${getStatusBadge(t.status)}</td>
      <td>${t.estimated_value ? '₹' + Number(t.estimated_value).toLocaleString('en-IN') : '—'}</td>
      <td><button class="action-btn" onclick="openTenderModal('${encodeURIComponent(t.tender_number)}')">View &rarr;</button></td>
    </tr>
  `).join('') || '<tr><td colspan="5">No tenders loaded</td></tr>';

  document.getElementById('dashDeptPills').innerHTML = (res.departments || []).map(d => `
    <div class="dept-pill">
      <strong>${d.department_code}</strong> <span>(${d.tender_count || 0})</span>
    </div>
  `).join('');
}

// 2. ALL TENDERS
async function loadAllTenders() {
  allTendersData = await fetch('/tenders?limit=250').then(r => r.json());
  
  // Populate dept filter dropdown
  const depts = Array.from(new Set(allTendersData.map(t => t.department_code).filter(Boolean))).sort();
  const sel = document.getElementById('tenderDeptFilter');
  sel.innerHTML = '<option value="">All 17 Departments</option>' + depts.map(d => `<option value="${d}">${d}</option>`).join('');

  renderTendersTable(allTendersData);
}

function filterTenders() {
  const dVal = document.getElementById('tenderDeptFilter').value.toLowerCase();
  const sVal = document.getElementById('tenderStatusFilter').value.toLowerCase();
  const qVal = document.getElementById('tenderSearchInput').value.toLowerCase();

  const filtered = allTendersData.filter(t => {
    const matchDept = !dVal || (t.department_code || '').toLowerCase() === dVal;
    const matchStatus = !sVal || (t.status || '').toLowerCase() === sVal;
    const matchQ = !qVal || (t.tender_number || '').toLowerCase().includes(qVal);
    return matchDept && matchStatus && matchQ;
  });

  renderTendersTable(filtered);
}

function renderTendersTable(list) {
  document.getElementById('allTendersTable').innerHTML = list.map(t => {
    let flagBadges = '';
    if (t.found_automatically) flagBadges += '<span class="badge badge-auto">MY TENDER</span> ';
    if (t.unknown_to_us) flagBadges += '<span class="badge badge-unknown">UNKNOWN</span>';

    return `
      <tr>
        <td><strong>${t.tender_number}</strong></td>
        <td>${t.department_code || '—'}</td>
        <td>${t.category || '—'}</td>
        <td>${getStatusBadge(t.status)}</td>
        <td>${t.published_date ? t.published_date.slice(0, 10) : '—'}</td>
        <td>${t.closing_date ? t.closing_date.slice(0, 10) : '—'}</td>
        <td>${flagBadges || '—'}</td>
        <td><button class="action-btn" onclick="openTenderModal('${encodeURIComponent(t.tender_number)}')">Details</button></td>
      </tr>
    `;
  }).join('') || '<tr><td colspan="8">No tenders match criteria</td></tr>';
}

// 3. IND SEARCH
async function runIndSearch() {
  const q = document.getElementById('indSearchQuery').value.trim();
  const header = document.getElementById('indSearchResultsHeader');
  const tbody = document.getElementById('indSearchResultsTable');

  if (!q) {
    header.textContent = 'Enter an IND query above to search.';
    tbody.innerHTML = '';
    return;
  }

  const results = await fetch(`/tenders?search=${encodeURIComponent(q)}&limit=100`).then(r => r.json());
  header.textContent = `Found ${results.length} tender(s) matching "${q}" across the 17 departments:`;

  tbody.innerHTML = results.map(t => `
    <tr>
      <td><strong>${t.tender_number}</strong></td>
      <td>${t.department_code || '—'}</td>
      <td>${getStatusBadge(t.status)}</td>
      <td>${t.estimated_value ? '₹' + Number(t.estimated_value).toLocaleString('en-IN') : '—'}</td>
      <td>${t.published_date ? t.published_date.slice(0, 10) : '—'}</td>
      <td><button class="action-btn" onclick="openTenderModal('${encodeURIComponent(t.tender_number)}')">View &rarr;</button></td>
    </tr>
  `).join('') || '<tr><td colspan="6">No tenders found matching this query.</td></tr>';
}

// 4. COMPANY (K.K. ALLIANZE)
async function loadCompanyData() {
  companyData = await fetch('/company/kk-allianze').then(r => r.json());

  document.getElementById('companyStatsGrid').innerHTML = `
    <div class="card">
      <h3>Participated Tenders</h3>
      <strong>${companyData.total_participated}</strong>
    </div>
    <div class="card">
      <h3>Won Tenders (All / Part)</h3>
      <strong>${companyData.total_won_tenders}</strong>
    </div>
    <div class="card">
      <h3>Lost Tenders</h3>
      <strong>${companyData.total_lost_tenders}</strong>
    </div>
    <div class="card">
      <h3>Total Value Won</h3>
      <strong>₹${(companyData.total_won_value || 0).toLocaleString('en-IN')}</strong>
    </div>
  `;

  document.getElementById('companyTendersTable').innerHTML = (companyData.tenders || []).map(t => `
    <tr>
      <td><strong>${t.tender_number}</strong></td>
      <td>${t.department_code}</td>
      <td>${t.category || 'GOODS'}</td>
      <td>${getStatusBadge(t.status)}</td>
      <td><button class="action-btn" onclick="openTenderModal('${encodeURIComponent(t.tender_number)}')">Details</button></td>
    </tr>
  `).join('');

  document.getElementById('competitorsTable').innerHTML = (companyData.competitors_who_beat_us || []).map(c => `
    <tr>
      <td><strong>${c.name}</strong></td>
      <td><span class="badge badge-eval">${c.times_beat_us} items</span></td>
    </tr>
  `).join('') || '<tr><td colspan="2">No competitor data</td></tr>';

  document.getElementById('priceComparisonTable').innerHTML = (companyData.lost_items || []).slice(0, 50).map(item => `
    <tr>
      <td>${item.tender_number}</td>
      <td>${item.item_name}</td>
      <td>₹${Number(item.our_rate || 0).toLocaleString('en-IN')}</td>
      <td>₹${Number(item.our_total || 0).toLocaleString('en-IN')}</td>
      <td>Rank ${item.our_rank || '—'}</td>
      <td><strong>${item.winner_name || '—'}</strong></td>
      <td>₹${Number(item.winner_rate || 0).toLocaleString('en-IN')}</td>
      <td>₹${Number(item.winner_total || 0).toLocaleString('en-IN')}</td>
    </tr>
  `).join('') || '<tr><td colspan="8">No lost items recorded</td></tr>';
}

// 5. MY TENDERS
async function loadMyTenders() {
  const unknownOnly = document.getElementById('unknownOnlyCheck').checked;
  const list = await fetch(`/my-tenders?unknown_only=${unknownOnly}`).then(r => r.json());

  document.getElementById('myTendersTable').innerHTML = list.map(t => `
    <tr>
      <td><strong>${t.tender_number}</strong></td>
      <td>${t.department_code || '—'}</td>
      <td>${getStatusBadge(t.status)}</td>
      <td><span class="badge badge-auto">Found Automatically</span></td>
      <td>${t.unknown_to_us ? '<span class="badge badge-unknown">UNKNOWN TO US (Not in Excel)</span>' : '<span class="badge badge-awarded">VERIFIED IN EXCEL</span>'}</td>
      <td><button class="action-btn" onclick="openTenderModal('${encodeURIComponent(t.tender_number)}')">View &rarr;</button></td>
    </tr>
  `).join('') || '<tr><td colspan="6">No tenders matching filter</td></tr>';
}

// 6. COVERAGE & SCAN LOG
async function loadCoverage() {
  const data = await fetch('/coverage').then(r => r.json());

  document.getElementById('coverageTable').innerHTML = (data.departments || []).map(d => `
    <tr>
      <td><strong>${d.department_code}</strong></td>
      <td>${d.department_name}</td>
      <td>${d.tender_count || 0}</td>
      <td><span class="badge badge-awarded">Active & Scoped</span></td>
    </tr>
  `).join('');

  document.getElementById('scanLogTable').innerHTML = (data.scan_runs || []).map(s => `
    <tr>
      <td>${s.source_name}</td>
      <td>${s.started_at ? s.started_at.slice(0, 19).replace('T', ' ') : '—'}</td>
      <td><span class="badge badge-published">${s.status}</span></td>
      <td>${s.notes || '—'}</td>
    </tr>
  `).join('') || '<tr><td colspan="4">No scan runs logged yet</td></tr>';
}

// TENDER DETAIL MODAL
async function openTenderModal(encodedTenderNum) {
  const tender = await fetch(`/tender/${encodedTenderNum}`).then(r => r.json());
  const modal = document.getElementById('tenderModal');

  document.getElementById('modalTenderTitle').textContent = tender.tender_number;

  document.getElementById('modalMetaGrid').innerHTML = `
    <div class="meta-item"><label>Department</label><span>${tender.department_name || tender.department_code || '—'}</span></div>
    <div class="meta-item"><label>Status</label><span>${tender.status || '—'}</span></div>
    <div class="meta-item"><label>Category</label><span>${tender.category || '—'}</span></div>
    <div class="meta-item"><label>Est. Value</label><span>${tender.estimated_value ? '₹' + Number(tender.estimated_value).toLocaleString('en-IN') : '—'}</span></div>
    <div class="meta-item"><label>EMD Amount</label><span>${tender.emd_amount ? '₹' + Number(tender.emd_amount).toLocaleString('en-IN') : '—'}</span></div>
    <div class="meta-item"><label>Published Date</label><span>${tender.published_date || '—'}</span></div>
    <div class="meta-item"><label>Closing Date</label><span>${tender.closing_date || '—'}</span></div>
  `;

  // Documents
  const docs = tender.documents || [];
  document.getElementById('modalDocList').innerHTML = docs.map(d => `
    <li>
      <span>📄 <strong>${d.file_name}</strong> (${(d.size / 1024).toFixed(1)} KB)</span>
      <a class="action-btn" href="/tender-file/${encodeURIComponent(tender.tender_number)}/${encodeURIComponent(d.file_name)}" target="_blank">Download / View</a>
    </li>
  `).join('') || '<li>No attached files stored on disk</li>';

  // Bids
  const bids = tender.bids || [];
  document.getElementById('modalBidsTable').innerHTML = bids.map(b => `
    <tr>
      <td>${b.item_name || '—'}</td>
      <td><strong>${b.supplier_name || '—'}</strong></td>
      <td>${b.rate ? '₹' + Number(b.rate).toLocaleString('en-IN') : '—'}</td>
      <td>${b.total ? '₹' + Number(b.total).toLocaleString('en-IN') : '—'}</td>
      <td>Rank ${b.rank || '—'}</td>
      <td>${b.selected ? '<span class="badge badge-awarded">SELECTED (L1)</span>' : '<span class="badge badge-closed">Not Selected</span>'}</td>
    </tr>
  `).join('') || '<tr><td colspan="6">No comparative bids for this tender (or bids not public yet)</td></tr>';

  // Timeline
  const timeline = tender.timeline || [];
  document.getElementById('modalTimeline').innerHTML = timeline.map(tl => `
    <li>
      <strong>${tl.new_status}</strong> <span style="color:#64748b">(${tl.changed_at})</span>: ${tl.note || 'Status changed'}
    </li>
  `).join('') || '<li>No recorded status transitions</li>';

  modal.classList.add('open');
}

function closeModal() {
  document.getElementById('tenderModal').classList.remove('open');
}

// Global init
loadDashboard();

const evtSource = new EventSource('/events');
evtSource.onmessage = () => {
  loadDashboard();
};
