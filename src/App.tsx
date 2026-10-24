import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';

type Department = { code: string; name: string; portal_id: number; count: number; name_verified?: boolean };
type Bid = {
  item_name?: string;
  supplier_id?: string;
  supplier_name?: string;
  rate?: string | number | null;
  total?: string | number | null;
  rank?: number | null;
  selected?: number | boolean | null;
};
type Tender = {
  tender_number: string;
  department_code?: string;
  department_name?: string;
  category?: string;
  status?: string;
  title?: string;
  published_date?: string;
  closing_date?: string;
  estimated_value?: string | number | null;
  created_at?: string;
  updated_at?: string;
  quoted?: boolean;
  bids_opened?: boolean;
  bids_opened_at?: string | null;
  our_rank?: number | null;
  our_rate?: string | number | null;
  our_total?: string | number | null;
  l1_name?: string | null;
  l1_rate?: string | number | null;
  l1_total?: string | number | null;
  difference?: number | null;
  result?: string;
  quote?: { source: string; added_at: string; last_checked_at?: string | null; bids_opened_at?: string | null } | null;
  bids?: Bid[];
  items?: Array<Record<string, string | number | null>>;
  timeline?: Array<{ previous_status?: string; new_status?: string; changed_at?: string; note?: string }>;
};
type Change = {
  id: number;
  tender_number: string;
  change_type: string;
  old_value?: string | null;
  new_value?: string | null;
  created_at: string;
};
type Dashboard = {
  stats: { tenders: number; quoted: number; bids_opened: number; won: number; lost: number; pending: number; not_public: number; total_won_value: number };
  quoted_tenders: Tender[];
  today_updates: Change[];
  departments: Department[];
  needs_confirmation: Array<{ supplier_id?: string | null; supplier_name: string; tenders: number }>;
  scan: {
    status: string;
    started_at?: string | null;
    completed_at?: string | null;
    message?: string | null;
    last_successful_scan_date?: string | null;
    quote_watch?: { status: string; message?: string | null };
  };
};
type TenderPage = { total: number; page: number; page_size: number; items: Tender[] };
type TodayPage = { groups: Array<{ department: Department; tenders: Array<Tender & { day_type?: string }> }> };
type MainTab = 'quoted' | 'today' | 'all';
type DetailTab = 'overview' | 'items' | 'bids' | 'timeline';

const STATUSES = ['PUBLISHED', 'CLOSED', 'UNDER_EVALUATION', 'EVALUATION_COMPLETED', 'AWARDED', 'RETENDERED', 'RECALLED'];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const message = typeof body?.detail === 'string'
      ? body.detail
      : body?.detail ? JSON.stringify(body.detail) : `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function formatMoney(value?: string | number | null) {
  if (value === null || value === undefined || value === '') return '—';
  const amount = Number(value);
  return Number.isFinite(amount)
    ? `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
    : String(value);
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function statusClass(status?: string) {
  return `status status-${(status || 'unknown').toLowerCase().replace(/_/g, '-')}`;
}

function displayOutcome(value?: string) {
  if (value === 'not_public') return 'Not public yet';
  if (!value) return 'Pending';
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ');
}

function buildFilterUrl(filters: {
  q: string; department: string; category: string; status: string;
  dateFrom: string; dateTo: string; closingSoon: boolean; quoted: string;
}) {
  const params = new URLSearchParams();
  params.set('tab', 'all');
  if (filters.q) params.set('q', filters.q);
  if (filters.department) params.set('department', filters.department);
  if (filters.category) params.set('category', filters.category);
  if (filters.status) params.set('status', filters.status);
  if (filters.dateFrom) params.set('date_from', filters.dateFrom);
  if (filters.dateTo) params.set('date_to', filters.dateTo);
  if (filters.closingSoon) params.set('closing_soon', 'true');
  if (filters.quoted) params.set('quoted', filters.quoted);
  return `?${params.toString()}`;
}

export default function App() {
  const initial = new URLSearchParams(window.location.search);
  const initialTab = initial.get('tab');
  const [tab, setTab] = useState<MainTab>(initialTab === 'today' || initialTab === 'all' ? initialTab : 'quoted');
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [tenderPage, setTenderPage] = useState<TenderPage>({ total: 0, page: 1, page_size: 50, items: [] });
  const [todayPage, setTodayPage] = useState<TodayPage>({ groups: [] });
  const [period, setPeriod] = useState<'today' | 'yesterday' | '7days'>('today');
  const [query, setQuery] = useState(initial.get('q') || '');
  const [department, setDepartment] = useState(initial.get('department') || '');
  const [category, setCategory] = useState(initial.get('category') || '');
  const [status, setStatus] = useState(initial.get('status') || '');
  const [dateFrom, setDateFrom] = useState(initial.get('date_from') || '');
  const [dateTo, setDateTo] = useState(initial.get('date_to') || '');
  const [closingSoon, setClosingSoon] = useState(initial.get('closing_soon') === 'true');
  const [quotedFilter, setQuotedFilter] = useState(initial.get('quoted') || '');
  const [page, setPage] = useState(1);
  const [quoteInput, setQuoteInput] = useState('');
  const [quoteMessage, setQuoteMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedTender, setSelectedTender] = useState<Tender | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>('overview');
  const [seenChangeId, setSeenChangeId] = useState(() => Number(localStorage.getItem('kppp-seen-change') || 0));

  const refreshDashboard = useCallback(async () => {
    const result = await api<Dashboard>('/api/dashboard');
    setDashboard(result);
    const latest = result.today_updates.reduce((max, change) => Math.max(max, change.id), 0);
    if (latest) {
      window.setTimeout(() => {
        localStorage.setItem('kppp-seen-change', String(latest));
        setSeenChangeId(latest);
      }, 3000);
    }
  }, []);

  const refreshTenders = useCallback(async (pageNumber = 1) => {
    const params = new URLSearchParams({ page: String(pageNumber), page_size: '50' });
    if (query.trim()) params.set('q', query.trim());
    if (department) params.set('department', department);
    if (category) params.set('category', category);
    if (status) params.set('status', status);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (closingSoon) params.set('closing_soon', 'true');
    if (quotedFilter) params.set('quoted', String(quotedFilter === 'yes'));
    setTenderPage(await api<TenderPage>(`/api/tenders?${params}`));
  }, [category, closingSoon, dateFrom, dateTo, department, query, quotedFilter, status]);

  const refreshToday = useCallback(async (selectedPeriod: typeof period) => {
    setTodayPage(await api<TodayPage>(`/api/today?period=${selectedPeriod}`));
  }, []);

  const refresh = useCallback(async () => {
    setError('');
    try {
      await Promise.all([refreshDashboard(), refreshTenders(page), refreshToday(period)]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load local KPPP data.');
    } finally {
      setLoading(false);
    }
  }, [page, period, refreshDashboard, refreshTenders, refreshToday]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    const stream = new EventSource('/api/events');
    stream.addEventListener('change', () => void refresh());
    stream.addEventListener('status', () => void refreshDashboard());
    return () => {
      window.clearInterval(timer);
      stream.close();
    };
  }, [refresh, refreshDashboard]);

  useEffect(() => {
    const filterUrl = buildFilterUrl({ q: query, department, category, status, dateFrom, dateTo, closingSoon, quoted: quotedFilter });
    window.history.replaceState({}, '', tab === 'all' ? filterUrl : `?tab=${tab}`);
    setPage(1);
  }, [category, closingSoon, dateFrom, dateTo, department, query, quotedFilter, status, tab]);

  useEffect(() => {
    void refreshTenders(page).catch(cause => setError(cause instanceof Error ? cause.message : 'Tender search failed.'));
  }, [page, refreshTenders]);

  useEffect(() => {
    void refreshToday(period).catch(cause => setError(cause instanceof Error ? cause.message : 'Today view failed.'));
  }, [period, refreshToday]);

  const departments = dashboard?.departments || [];
  const quotedTenders = dashboard?.quoted_tenders || [];
  const activeFilters = useMemo(
    () => [department, category, status, dateFrom, dateTo, closingSoon, quotedFilter].filter(Boolean).length,
    [category, closingSoon, dateFrom, dateTo, department, quotedFilter, status],
  );

  async function addQuotes(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuoteMessage('');
    setError('');
    const tenderNumbers = quoteInput.split(/[\n,;]+/).map(value => value.trim()).filter(Boolean);
    if (!tenderNumbers.length) {
      setError('Enter one or more in-scope tender numbers.');
      return;
    }
    try {
      const result = await api<{ added: string[]; already_watched: number }>('/api/quotes', {
        method: 'POST',
        body: JSON.stringify({ tender_numbers: tenderNumbers }),
      });
      setQuoteMessage(`${result.added.length} added; ${result.already_watched} already watched.`);
      setQuoteInput('');
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not add quoted tenders.');
    }
  }

  async function showTender(number: string, initialTab: DetailTab = 'overview') {
    setError('');
    setDetailTab(initialTab);
    try {
      setSelectedTender(await api<Tender>(`/api/tender?number=${encodeURIComponent(number)}`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load tender details.');
    }
  }

  function clearFilters() {
    setQuery('');
    setDepartment('');
    setCategory('');
    setStatus('');
    setDateFrom('');
    setDateTo('');
    setClosingSoon(false);
    setQuotedFilter('');
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">KK</span>
          <div>
            <h1>K.K. Allianze</h1>
            <p>KPPP tender monitor · 17 focus departments</p>
          </div>
        </div>
        <div className="health-pill" data-health={dashboard?.scan.status || 'unknown'}>
          <span className="health-dot" />
          {dashboard?.scan.status === 'completed' ? 'Scan healthy' : dashboard?.scan.status === 'running' ? 'Scan running' : 'Scan not verified'}
        </div>
      </header>

      <nav className="main-nav" aria-label="Main navigation">
        {([
          ['quoted', 'My Quoted Tenders'],
          ['today', "Today's Tenders"],
          ['all', 'All Tenders'],
        ] as const).map(([key, label]) => (
          <button key={key} className={tab === key ? 'nav-link active' : 'nav-link'} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </nav>

      <main className="content">
        {error && <div className="alert error" role="alert">{error}</div>}
        {quoteMessage && <div className="alert success" role="status">{quoteMessage}</div>}
        {loading && !dashboard && <div className="empty">Loading the local database…</div>}

        {tab === 'quoted' && (
          <>
            <section className="updates panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">LIVE CHANGE FEED</p>
                  <h2>Today's updates</h2>
                </div>
                <span className="muted">Changes are recorded from database updates.</span>
              </div>
              {dashboard?.today_updates.length ? (
                <ul className="change-list">
                  {dashboard.today_updates.slice(0, 8).map(change => (
                    <li key={change.id} className={change.id > seenChangeId ? 'change new' : 'change'}>
                      <span className="change-dot" />
                      <button className="text-button" onClick={() => void showTender(change.tender_number)}>
                        <strong>{change.tender_number}</strong>
                      </button>
                      <span>{change.change_type.replace(/_/g, ' ')}</span>
                      <span className="muted">{change.old_value || '—'} → {change.new_value || '—'}</span>
                      <time>{formatDate(change.created_at)}</time>
                    </li>
                  ))}
                </ul>
              ) : <p className="empty compact">No recorded changes today.</p>}
            </section>

            <section className="stat-grid" aria-label="Quoted tender summary">
              {[
                ['Quoted', dashboard?.stats.quoted ?? 0],
                ['Bids opened', dashboard?.stats.bids_opened ?? 0],
                ['Won', dashboard?.stats.won ?? 0],
                ['Lost', dashboard?.stats.lost ?? 0],
                ['Pending', dashboard?.stats.pending ?? 0],
                ['Not public', dashboard?.stats.not_public ?? 0],
                ['Total value won', formatMoney(dashboard?.stats.total_won_value)],
              ].map(([label, value]) => <div className="stat-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}
            </section>

            <section className="panel">
              <div className="section-heading">
                <div><p className="eyebrow">WATCH LIST</p><h2>My quoted tenders</h2></div>
              </div>
              <form className="quote-form" onSubmit={addQuotes}>
                <label htmlFor="quote-numbers">Add quoted tender numbers</label>
                <textarea id="quote-numbers" value={quoteInput} onChange={event => setQuoteInput(event.target.value)} placeholder={'Paste one or more tender numbers, one per line'} rows={2} />
                <button className="button primary" type="submit">Add to watch list</button>
              </form>
              <div className="table-wrap">
                <table>
                  <thead><tr>
                    <th>Tender</th><th>Department</th><th>Title</th><th>Status</th><th>Closing</th>
                    <th>Bids opened</th><th>Our rank</th><th>L1</th><th>L1 rate</th><th>Our rate</th>
                    <th>Difference</th><th>Result</th><th>Last checked</th>
                  </tr></thead>
                  <tbody>
                    {quotedTenders.map(tender => <tr key={tender.tender_number}>
                      <td><button className="text-button strong" onClick={() => void showTender(tender.tender_number)}>{tender.tender_number}</button></td>
                      <td>{tender.department_code || '—'}</td>
                      <td>{tender.title || '—'}</td>
                      <td><span className={statusClass(tender.status)}>{tender.status || 'Not found'}</span></td>
                      <td>{formatDate(tender.closing_date)}</td>
                      <td>{tender.bids_opened ? `Yes · ${formatDate(tender.bids_opened_at || tender.quote?.bids_opened_at || null)}` : 'No'}</td>
                      <td>{tender.our_rank ?? '—'}</td><td>{tender.l1_name || '—'}</td>
                      <td>{formatMoney(tender.l1_rate)}</td><td>{formatMoney(tender.our_rate)}</td>
                      <td>{formatMoney(tender.difference)}</td><td>{displayOutcome(tender.result)}</td>
                      <td>{formatDate(tender.quote?.last_checked_at || null)}</td>
                    </tr>)}
                    {!quotedTenders.length && <tr><td colSpan={13} className="empty">No quoted tenders are being watched yet.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>
            {dashboard?.needs_confirmation.length ? <section className="panel">
              <div className="section-heading">
                <div><p className="eyebrow">REVIEW BEFORE MATCHING</p><h2>Needs confirmation</h2></div>
                <span className="muted">Similar names are not automatically treated as K.K. Allianze.</span>
              </div>
              <div className="table-wrap"><table>
                <thead><tr><th>Supplier name</th><th>Supplier ID</th><th>Matching tenders</th></tr></thead>
                <tbody>{dashboard.needs_confirmation.map((candidate, index) => <tr key={`${candidate.supplier_id}-${index}`}>
                  <td>{candidate.supplier_name}</td><td>{candidate.supplier_id || '—'}</td><td>{candidate.tenders}</td>
                </tr>)}</tbody>
              </table></div>
            </section> : null}
          </>
        )}

        {tab === 'today' && (
          <section className="panel">
            <div className="section-heading">
              <div><p className="eyebrow">DISCOVERED TENDERS</p><h2>Today's tenders</h2></div>
              <div className="segmented" role="tablist" aria-label="Tender date range">
                {([['today', 'Today'], ['yesterday', 'Yesterday'], ['7days', 'Last 7 days']] as const).map(([key, label]) => (
                  <button key={key} className={period === key ? 'selected' : ''} onClick={() => setPeriod(key)}>{label}</button>
                ))}
              </div>
            </div>
            <p className="muted">Published and newly discovered dates are shown separately. Departments with no matches remain visible.</p>
            {todayPage.groups.map(group => (
              <details className="department-group" key={group.department.code} open>
                <summary><strong>{group.department.code}</strong><span title={group.department.name_verified ? 'Department name verified' : 'Department name is from the local snapshot; live directory verification is pending'}>{group.department.name}{group.department.name_verified ? '' : ' · unverified'}</span><span className="count">{group.tenders.length}</span></summary>
                {group.tenders.length ? <div className="table-wrap">
                  <table><thead><tr><th>Tender</th><th>Title</th><th>Status</th><th>Category</th><th>Published</th><th>Closing</th><th>Found</th></tr></thead>
                    <tbody>{group.tenders.map(tender => <tr key={tender.tender_number}>
                      <td><button className="text-button strong" onClick={() => void showTender(tender.tender_number)}>{tender.tender_number}</button></td>
                      <td>{tender.title || '—'}</td><td><span className={statusClass(tender.status)}>{tender.status || '—'}</span></td>
                      <td>{tender.category || '—'}</td><td>{formatDate(tender.published_date)}</td><td>{formatDate(tender.closing_date)}</td>
                      <td><span className="new-tag">{tender.day_type === 'published_today' ? 'PUBLISHED TODAY' : 'NEW'}</span></td>
                    </tr>)}</tbody>
                  </table>
                </div> : <p className="empty compact">No tenders for this period.</p>}
              </details>
            ))}
          </section>
        )}

        {tab === 'all' && (
          <section className="panel">
            <div className="section-heading">
              <div><p className="eyebrow">SEARCH THE LOCAL DATABASE</p><h2>All tenders</h2></div>
              <span className="result-count">{tenderPage.total.toLocaleString()} results</span>
            </div>
            <div className="filters">
              <label className="search-field">Search tender, IND number, title or item
                <input value={query} onChange={event => setQuery(event.target.value)} placeholder="e.g. IND2012 or medical supplies" />
              </label>
              <label>Department<select value={department} onChange={event => setDepartment(event.target.value)}>
                <option value="">All departments</option>{departments.map(item => <option key={item.code} value={item.code}>{item.code}</option>)}
              </select></label>
              <label>Category<select value={category} onChange={event => setCategory(event.target.value)}>
                <option value="">All categories</option><option>GOODS</option><option>WORKS</option><option>SERVICES</option>
              </select></label>
              <label>Status<select value={status} onChange={event => setStatus(event.target.value)}>
                <option value="">All statuses</option>{STATUSES.map(item => <option key={item}>{item}</option>)}
              </select></label>
              <label>Published from<input type="date" value={dateFrom} onChange={event => setDateFrom(event.target.value)} /></label>
              <label>Published to<input type="date" value={dateTo} onChange={event => setDateTo(event.target.value)} /></label>
              <label>Quoted<select value={quotedFilter} onChange={event => setQuotedFilter(event.target.value)}>
                <option value="">All tenders</option><option value="yes">Quoted</option><option value="no">Not quoted</option>
              </select></label>
              <label className="check-filter"><input type="checkbox" checked={closingSoon} onChange={event => setClosingSoon(event.target.checked)} /> Closing within 7 days</label>
              {activeFilters > 0 && <button className="button subtle" onClick={clearFilters}>Clear {activeFilters} filters</button>}
            </div>
            {activeFilters > 0 && <div className="filter-chips" aria-label="Active filters">
              {department && <button onClick={() => setDepartment('')}>Department: {department} ×</button>}
              {category && <button onClick={() => setCategory('')}>Category: {category} ×</button>}
              {status && <button onClick={() => setStatus('')}>Status: {status} ×</button>}
              {dateFrom && <button onClick={() => setDateFrom('')}>From: {dateFrom} ×</button>}
              {dateTo && <button onClick={() => setDateTo('')}>To: {dateTo} ×</button>}
              {closingSoon && <button onClick={() => setClosingSoon(false)}>Closing soon ×</button>}
              {quotedFilter && <button onClick={() => setQuotedFilter('')}>Quoted: {quotedFilter} ×</button>}
            </div>}
            <div className="table-wrap">
              <table><thead><tr><th>Tender</th><th>Department</th><th>Title</th><th>Category</th><th>Status</th><th>Published</th><th>Closing</th><th>Est. value</th><th>Quoted</th><th>Action</th></tr></thead>
                <tbody>{tenderPage.items.map(tender => <tr key={tender.tender_number}>
                  <td><button className="text-button strong" onClick={() => void showTender(tender.tender_number)}>{tender.tender_number}</button></td>
                  <td>{tender.department_code || '—'}</td><td>{tender.title || '—'}</td><td>{tender.category || '—'}</td>
                  <td><span className={statusClass(tender.status)}>{tender.status || '—'}</span></td>
                  <td>{formatDate(tender.published_date)}</td><td>{formatDate(tender.closing_date)}</td>
                  <td>{formatMoney(tender.estimated_value)}</td><td>{tender.quoted ? 'Yes' : 'No'}</td>
                  <td><button className="button small" onClick={() => void showTender(tender.tender_number)}>Details</button></td>
                </tr>)}
                {!tenderPage.items.length && <tr><td colSpan={10} className="empty">No matching in-scope tenders in the local database.</td></tr>}</tbody>
              </table>
            </div>
            <div className="pagination">
              <button className="button subtle" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Previous</button>
              <span>Page {page} of {Math.max(1, Math.ceil(tenderPage.total / tenderPage.page_size))}</span>
              <button className="button subtle" disabled={page * tenderPage.page_size >= tenderPage.total} onClick={() => setPage(value => value + 1)}>Next</button>
            </div>
          </section>
        )}
      </main>

      <footer className="footer">
        <span>Last successful scan: {formatDate(dashboard?.scan.last_successful_scan_date || null)}</span>
        <span>Health: {dashboard?.scan.message || 'Waiting for first scan.'}</span>
        <span>Quoted watch: {dashboard?.scan.quote_watch?.message || 'Not started.'}</span>
        <span>{dashboard?.departments.length || 17} focus departments</span>
      </footer>

      {selectedTender && (
        <div className="modal-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setSelectedTender(null); }}>
          <section className="tender-modal" role="dialog" aria-modal="true" aria-labelledby="tender-title">
            <div className="modal-heading">
              <div><p className="eyebrow">TENDER DETAILS</p><h2 id="tender-title">{selectedTender.tender_number}</h2></div>
              <button className="close-button" onClick={() => setSelectedTender(null)} aria-label="Close tender details">×</button>
            </div>
            <nav className="detail-tabs" aria-label="Tender detail tabs">
              {([['overview', 'Overview'], ['items', 'Items'], ['bids', 'Bidders and Prices'], ['timeline', 'Timeline']] as const).map(([key, label]) => (
                <button key={key} className={detailTab === key ? 'active' : ''} onClick={() => setDetailTab(key)}>{label}</button>
              ))}
            </nav>
            <div className="modal-body">
              {detailTab === 'overview' && <div className="detail-grid">
                {[
                  ['Department', selectedTender.department_name || selectedTender.department_code],
                  ['Title', selectedTender.title],
                  ['Status', selectedTender.status],
                  ['Category', selectedTender.category],
                  ['Published', formatDate(selectedTender.published_date)],
                  ['Closing', formatDate(selectedTender.closing_date)],
                  ['Estimated value', formatMoney(selectedTender.estimated_value)],
                  ['Quoted', selectedTender.quoted ? 'Yes' : 'No'],
                ].map(([label, value]) => <div className="detail-cell" key={label}><span>{label}</span><strong>{value || '—'}</strong></div>)}
              </div>}
              {detailTab === 'items' && <div className="table-wrap">
                <table><thead><tr><th>Item</th><th>Quantity</th><th>Unit</th><th>Rate</th><th>Total</th></tr></thead>
                  <tbody>{selectedTender.items?.map((item, index) => <tr key={`${item.item_code || item.item_name}-${index}`}>
                    <td>{item.item_name || item.item_code || '—'}</td><td>{item.quantity || '—'}</td><td>{item.unit || '—'}</td>
                    <td>{formatMoney(item.rate)}</td><td>{formatMoney(item.total)}</td>
                  </tr>)}
                  {!selectedTender.items?.length && <tr><td colSpan={5} className="empty">No public item details stored.</td></tr>}</tbody>
                </table>
              </div>}
              {detailTab === 'bids' && <div className="table-wrap">
                {selectedTender.bids?.length ? <table><thead><tr><th>Bidder</th><th>Supplier ID</th><th>Item</th><th>Rate</th><th>Total</th><th>Rank</th><th>Selected</th></tr></thead>
                  <tbody>{selectedTender.bids.map((bid, index) => {
                    const isUs = bid.supplier_id === '5086' || ['K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN', 'KAMAL KUMAR P JAIN'].includes((bid.supplier_name || '').trim().toUpperCase());
                    return <tr key={`${bid.supplier_id}-${bid.item_name}-${index}`} className={isUs ? 'our-bid' : ''}>
                      <td>{bid.supplier_name || '—'}</td><td>{bid.supplier_id || '—'}</td><td>{bid.item_name || '—'}</td>
                      <td>{formatMoney(bid.rate)}</td><td>{formatMoney(bid.total)}</td><td>{bid.rank ?? '—'}</td>
                      <td>{bid.selected ? 'Yes' : 'No'}</td>
                    </tr>;
                  })}</tbody>
                </table> : <p className="empty">No public bidder or price data is stored yet. Last checked: {formatDate(selectedTender.quote?.last_checked_at || null)}.</p>}
              </div>}
              {detailTab === 'timeline' && <ol className="timeline">
                {selectedTender.timeline?.map((item, index) => <li key={`${item.changed_at}-${index}`}>
                  <strong>{item.previous_status || 'Start'} → {item.new_status || 'Update'}</strong>
                  <time>{formatDate(item.changed_at)}</time><span>{item.note || ''}</span>
                </li>)}
                {!selectedTender.timeline?.length && <li className="empty">No status changes recorded.</li>}
              </ol>}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
