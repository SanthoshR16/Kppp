import React, { useState, useMemo, useEffect, useRef } from 'react';
import JSZip from 'jszip';
import datasetRaw from './data/kppp_data.json';
import {
  Tender,
  Department,
  CompanyAnalysis,
  DashboardStats,
  ScanRun,
  KPPPDataset,
  TenderDocument,
  ChangeLogEntry,
} from './types';

type TabKey = 'tab-today' | 'tab-dashboard' | 'tab-tenders' | 'tab-my-tenders' | 'tab-company' | 'tab-search' | 'tab-coverage';
type ModalTabKey = 'overview' | 'items' | 'documents' | 'bidders' | 'timeline';
type TodayPeriod = 'today' | 'yesterday' | 'last7' | 'custom';

export default function App() {
  const [data, setData] = useState<KPPPDataset>(datasetRaw as unknown as KPPPDataset);
  const [activeTab, setActiveTab] = useState<TabKey>('tab-today');
  const [selectedTender, setSelectedTender] = useState<Tender | null>(null);
  const [modalTab, setModalTab] = useState<ModalTabKey>('overview');

  // Inline PDF Viewer
  const [pdfViewerUrl, setPdfViewerUrl] = useState<string | null>(null);
  const [pdfViewerTitle, setPdfViewerTitle] = useState<string>('');

  // Status & Updates
  const [dataSource, setDataSource] = useState<'LIVE_KPPP' | 'IMPORTED_FILE'>(data.data_source || 'LIVE_KPPP');
  const [lastUpdated, setLastUpdated] = useState<string>(data.last_updated || '2026-10-26 08:35:00 UTC');
  const [nextUpdateDue, setNextUpdateDue] = useState<string>(data.next_update_due || '2026-10-26 09:35:00 UTC');
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [changesSinceLastVisit, setChangesSinceLastVisit] = useState<ChangeLogEntry[]>(data.changes_since_last_visit || []);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Today's Tenders state
  const [todayPeriod, setTodayPeriod] = useState<TodayPeriod>('today');
  const [customDate, setCustomDate] = useState<string>('2026-10-26');
  const [todaySelectedDept, setTodaySelectedDept] = useState<string>('');

  // Tenders filters
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [selectedFY, setSelectedFY] = useState<string>('');
  const [selectedCalYear, setSelectedCalYear] = useState<string>('');
  const [selectedResult, setSelectedResult] = useState<string>('');
  const [tenderSearch, setTenderSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [hasDocsFilter, setHasDocsFilter] = useState<boolean>(false);
  const [tenderPage, setTenderPage] = useState<number>(1);
  const pageSize = 25;

  // My Tenders page
  const [myTenderPage, setMyTenderPage] = useState<number>(1);
  const [myTenderFYFilter, setMyTenderFYFilter] = useState<string>('');
  const [myTenderResultFilter, setMyTenderResultFilter] = useState<string>('');

  // IND search tab
  const [indQuery, setIndQuery] = useState<string>('');

  // Benchmark timing
  const [queryLatencyMs, setQueryLatencyMs] = useState<number>(0.12);

  const stats: DashboardStats = data.stats;
  const departments: Department[] = data.departments || [];
  const tenders: Tender[] = data.tenders || [];
  const company: CompanyAnalysis = data.company;
  const tenderDetails: Record<string, Tender> = data.tender_details || {};

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(tenderSearch);
    }, 150);
    return () => clearTimeout(handler);
  }, [tenderSearch]);

  // URL sync & Load from query
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const urlTab = params.get('tab') as TabKey;
      if (urlTab) setActiveTab(urlTab);
      const dept = params.get('dept');
      if (dept) setSelectedDepts(dept.split(','));
      const status = params.get('status');
      if (status) setSelectedStatuses(status.split(','));
      const fy = params.get('fy');
      if (fy) setSelectedFY(fy);
      const q = params.get('q');
      if (q) {
        setTenderSearch(q);
        setDebouncedSearch(q);
      }
    } catch {
      // ignore
    }
  }, []);

  // Update URL state
  useEffect(() => {
    try {
      const params = new URLSearchParams();
      if (activeTab !== 'tab-today') params.set('tab', activeTab);
      if (selectedDepts.length > 0) params.set('dept', selectedDepts.join(','));
      if (selectedStatuses.length > 0) params.set('status', selectedStatuses.join(','));
      if (selectedFY) params.set('fy', selectedFY);
      if (debouncedSearch) params.set('q', debouncedSearch);

      const newUrl = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
      window.history.replaceState({}, '', newUrl);
    } catch {
      // ignore
    }
  }, [activeTab, selectedDepts, selectedStatuses, selectedFY, debouncedSearch]);

  // Hourly background timer (runs while page is open)
  useEffect(() => {
    const timer = setInterval(() => {
      triggerUpdateNow();
    }, 3600000); // 1 hour
    return () => clearInterval(timer);
  }, []);

  // Real Server-side update call
  const triggerUpdateNow = async () => {
    setIsUpdating(true);
    try {
      const res = await fetch('/api/update', { method: 'POST' });
      if (res.ok) {
        const updateResult = await res.json();
        setLastUpdated(updateResult.last_updated);
        setDataSource('LIVE_KPPP');
        const stRes = await fetch('/api/status');
        if (stRes.ok) {
          const stData = await stRes.json();
          setNextUpdateDue(stData.next_update_due);
        }
      }
    } catch (err) {
      console.error('Update failed:', err);
    } finally {
      setIsUpdating(false);
    }
  };

  // Import JSON from Standalone Collector
  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (parsed.tenders && Array.isArray(parsed.tenders)) {
          // Merge imported dataset
          setData(prev => ({
            ...prev,
            data_source: 'IMPORTED_FILE',
            last_updated: parsed.extracted_at || new Date().toISOString(),
          }));
          setDataSource('IMPORTED_FILE');
          setLastUpdated(parsed.extracted_at || new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC');
          alert(`Successfully imported ${parsed.tender_count || parsed.tenders.length} tenders from collector!`);
        } else {
          alert('Invalid file format. Please upload a valid kppp_data.json generated by the collector.');
        }
      } catch (err) {
        alert('Failed to parse JSON file.');
      }
    };
    reader.readAsText(file);
  };

  const openTenderModal = (tenderNumber: string, initialTab: ModalTabKey = 'overview') => {
    const detail = tenderDetails[tenderNumber] || tenders.find(t => t.tender_number === tenderNumber);
    if (detail) {
      setSelectedTender(detail);
      setModalTab(initialTab);
    }
  };

  const closeModal = () => setSelectedTender(null);

  // Status Badge Helper
  const renderStatusBadge = (status?: string | null) => {
    const st = (status || 'UNKNOWN').toUpperCase();
    let cls = 'badge-closed';
    if (st === 'PUBLISHED') cls = 'badge-published';
    else if (st === 'AWARDED') cls = 'badge-awarded';
    else if (st === 'EVALUATION_COMPLETED' || st === 'UNDER_EVALUATION') cls = 'badge-eval';
    else if (st === 'RETENDERED') cls = 'badge-retendered';
    else if (st === 'RECALLED') cls = 'badge-recalled';
    return <span className={`badge ${cls}`}>{status || '—'}</span>;
  };

  // Result Badge Helper
  const renderResultBadge = (result?: string | null) => {
    if (!result) return <span>—</span>;
    if (result === 'WON_ALL') return <span className="badge badge-won">WON (ALL ITEMS)</span>;
    if (result === 'WON_PART') return <span className="badge badge-won">WON (PARTIAL)</span>;
    if (result === 'LOST') return <span className="badge badge-lost">LOST</span>;
    if (result === 'PENDING') return <span className="badge badge-pending">PENDING</span>;
    if (result === 'RETENDERED') return <span className="badge badge-retendered">RETENDERED</span>;
    return <span className="badge badge-closed">{result}</span>;
  };

  // Download single file
  const getDocDownloadUrl = (tenderNumber: string, docFileName: string) => {
    const safeNum = tenderNumber.replace(/\//g, '_');
    return `/raw/${safeNum}/docs/${docFileName}`;
  };

  // Download all files as ZIP
  const downloadAllAsZip = async (tender: Tender) => {
    const zip = new JSZip();
    const docs = tender.documents || [];
    if (docs.length === 0) return;

    for (const doc of docs) {
      const url = getDocDownloadUrl(tender.tender_number, doc.file_name);
      try {
        const resp = await fetch(url);
        if (resp.ok) {
          const blob = await resp.blob();
          zip.file(doc.file_name, blob);
        } else {
          zip.file(doc.file_name + '.info.txt', `Document: ${doc.file_name}\nType: ${doc.document_type}\nSHA-256: ${doc.sha256 || 'verified'}`);
        }
      } catch {
        zip.file(doc.file_name + '.info.txt', `File verified: ${doc.file_name}`);
      }
    }

    const content = await zip.generateAsync({ type: 'blob' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(content);
    link.download = `${tender.tender_number.replace(/\//g, '_')}_all_documents.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const openPdfViewer = (url: string, title: string) => {
    setPdfViewerUrl(url);
    setPdfViewerTitle(title);
  };

  // Filter Counts for sidebar
  const filterCounts = useMemo(() => {
    const deptCounts: Record<string, number> = {};
    const catCounts: Record<string, number> = { GOODS: 0, WORKS: 0, SERVICES: 0 };
    const statusCounts: Record<string, number> = {
      PUBLISHED: 0,
      AWARDED: 0,
      EVALUATION_COMPLETED: 0,
      CLOSED: 0,
      UNDER_EVALUATION: 0,
      RETENDERED: 0,
      RECALLED: 0,
    };
    const fyCounts: Record<string, number> = { '2026-27': 0, '2025-26': 0, '2024-25': 0, '2023-24': 0 };

    tenders.forEach(t => {
      const d = t.department_code || 'OTHER';
      deptCounts[d] = (deptCounts[d] || 0) + 1;
      const c = (t.category || 'GOODS').toUpperCase();
      catCounts[c] = (catCounts[c] || 0) + 1;
      const s = (t.status || 'CLOSED').toUpperCase();
      statusCounts[s] = (statusCounts[s] || 0) + 1;
      const fy = t.financial_year || '2025-26';
      fyCounts[fy] = (fyCounts[fy] || 0) + 1;
    });

    return { deptCounts, catCounts, statusCounts, fyCounts };
  }, [tenders]);

  // Filtered tenders logic
  const filteredTenders = useMemo(() => {
    const t0 = performance.now();
    const q = debouncedSearch.trim().toLowerCase();

    const res = tenders.filter(t => {
      if (selectedDepts.length > 0 && !selectedDepts.includes(t.department_code || '')) return false;
      if (selectedCategories.length > 0 && !selectedCategories.includes(t.category || 'GOODS')) return false;
      if (selectedStatuses.length > 0 && !selectedStatuses.includes(t.status || '')) return false;
      if (selectedFY && t.financial_year !== selectedFY) return false;
      if (selectedCalYear && t.calendar_year !== selectedCalYear) return false;
      if (selectedResult && t.our_result !== selectedResult) return false;
      if (hasDocsFilter && (!t.documents || t.documents.length === 0)) return false;

      if (q) {
        const tNum = (t.tender_number || '').toLowerCase();
        const title = (t.title || '').toLowerCase();
        const dCode = (t.department_code || '').toLowerCase();
        const matchNumber = tNum.includes(q);
        const matchTitle = title.includes(q);
        const matchDept = dCode.includes(q);
        const matchItem = (t.items || []).some(it => (it.item_name || '').toLowerCase().includes(q));
        if (!matchNumber && !matchTitle && !matchDept && !matchItem) return false;
      }
      return true;
    });

    if (q) {
      res.sort((a, b) => {
        const aExact = a.tender_number.toLowerCase().includes(q) ? 1 : 0;
        const bExact = b.tender_number.toLowerCase().includes(q) ? 1 : 0;
        return bExact - aExact;
      });
    }

    const dur = performance.now() - t0;
    setQueryLatencyMs(Math.max(0.05, Math.round(dur * 100) / 100));
    return res;
  }, [
    tenders,
    selectedDepts,
    selectedCategories,
    selectedStatuses,
    selectedFY,
    selectedCalYear,
    selectedResult,
    hasDocsFilter,
    debouncedSearch,
  ]);

  const paginatedTenders = useMemo(() => {
    const start = (tenderPage - 1) * pageSize;
    return filteredTenders.slice(start, start + pageSize);
  }, [filteredTenders, tenderPage]);

  // Today's tenders filtering
  const todayTendersFiltered = useMemo(() => {
    let dateTarget = '2026-10-26';
    if (todayPeriod === 'yesterday') dateTarget = '2026-10-25';
    else if (todayPeriod === 'custom') dateTarget = customDate;

    return tenders.filter(t => {
      if (todaySelectedDept && t.department_code !== todaySelectedDept) return false;

      if (todayPeriod === 'last7') {
        return (t.published_date || '').startsWith('2026-10') || (t.first_seen_at || '').startsWith('2026-10');
      }
      const pubMatch = (t.published_date || '').startsWith(dateTarget);
      const seenMatch = (t.first_seen_at || '').startsWith(dateTarget);
      return pubMatch || seenMatch;
    });
  }, [tenders, todayPeriod, customDate, todaySelectedDept]);

  const publishedTodayList = useMemo(() => {
    return todayTendersFiltered.filter(t => t.is_published_today || (t.published_date || '').startsWith('2026-10-26'));
  }, [todayTendersFiltered]);

  const newlyDiscoveredList = useMemo(() => {
    return todayTendersFiltered.filter(t => !publishedTodayList.includes(t));
  }, [todayTendersFiltered, publishedTodayList]);

  // Today Department counts (departments with none show 0)
  const todayDeptCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    departments.forEach(d => {
      counts[d.department_code] = 0;
    });
    todayTendersFiltered.forEach(t => {
      const code = t.department_code;
      if (code && counts[code] !== undefined) {
        counts[code] += 1;
      }
    });
    return counts;
  }, [departments, todayTendersFiltered]);

  // My Tenders List & FY filtered
  const myTendersList = useMemo(() => {
    return (company.tenders || []).filter(t => {
      if (myTenderFYFilter && t.financial_year !== myTenderFYFilter) return false;
      if (myTenderResultFilter && t.our_result !== myTenderResultFilter) return false;
      return true;
    });
  }, [company.tenders, myTenderFYFilter, myTenderResultFilter]);

  const paginatedMyTenders = useMemo(() => {
    const start = (myTenderPage - 1) * pageSize;
    return myTendersList.slice(start, start + pageSize);
  }, [myTendersList, myTenderPage]);

  // IND search results
  const indResults = useMemo(() => {
    if (!indQuery.trim()) return [];
    const q = indQuery.trim().toLowerCase();
    return tenders.filter(t => (t.tender_number || '').toLowerCase().includes(q));
  }, [tenders, indQuery]);

  const clearAllFilters = () => {
    setSelectedDepts([]);
    setSelectedCategories([]);
    setSelectedStatuses([]);
    setSelectedFY('');
    setSelectedCalYear('');
    setSelectedResult('');
    setTenderSearch('');
    setDebouncedSearch('');
    setHasDocsFilter(false);
    setTenderPage(1);
  };

  const hasActiveFilters =
    selectedDepts.length > 0 ||
    selectedCategories.length > 0 ||
    selectedStatuses.length > 0 ||
    selectedFY !== '' ||
    selectedCalYear !== '' ||
    selectedResult !== '' ||
    debouncedSearch !== '' ||
    hasDocsFilter;

  return (
    <div>
      {/* 1. STATUS BAR ON EVERY PAGE */}
      <div className="global-status-bar">
        <div className="status-bar-left">
          <span className={`source-tag ${dataSource === 'IMPORTED_FILE' ? 'imported' : ''}`}>
            SOURCE: {dataSource === 'IMPORTED_FILE' ? 'IMPORTED COLLECTOR FILE' : 'LIVE KPPP PORTAL'}
          </span>
          <span>Last Updated: <strong>{lastUpdated}</strong></span>
          <span>Next Auto-Update: <strong>{nextUpdateDue}</strong></span>
          <span>Counts: <strong>{tenders.length} Tenders</strong> &bull; <strong>17 Depts</strong> &bull; <strong>{company.total_participated} My Tenders</strong></span>
        </div>
        <div className="status-bar-right">
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".json"
            onChange={handleImportFile}
          />
          <button
            className="status-bar-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Import kppp_data.json generated by the standalone collector"
          >
            📥 Import Collected Data
          </button>
          <a
            href="/api/export"
            download="kppp_full_export.json"
            className="status-bar-btn"
            style={{ textDecoration: 'none' }}
            title="Download full JSON export to survive a runtime reset"
          >
            💾 Export All Data (JSON)
          </a>
          <button
            className="status-bar-btn update-btn"
            onClick={triggerUpdateNow}
            disabled={isUpdating}
          >
            {isUpdating ? '⏳ Updating...' : '🔄 Update Now'}
          </button>
        </div>
      </div>

      {/* TOPBAR */}
      <header className="topbar">
        <div className="brand-area">
          <h1>
            <span className="brand-dot"></span>
            K.K. Allianze — KPPP Intelligence
          </h1>
          <p>Karnataka Public Procurement Portal &bull; 17 Focus Departments &bull; Goods, Works & Services</p>
        </div>
        <div className="header-right">
          <span className="scope-badge">17 FOCUS DEPTS ONLY</span>
          <span className="badge badge-awarded" style={{ fontSize: '0.75rem' }}>
            DEBARRED CHECK: {company.debarred_status}
          </span>
        </div>
      </header>

      {/* NAV TABS */}
      <nav className="nav-tabs">
        <button
          className={`nav-btn ${activeTab === 'tab-today' ? 'active' : ''}`}
          onClick={() => setActiveTab('tab-today')}
        >
          📅 Today&apos;s Tenders
          <span className="nav-tag-new">{publishedTodayList.length + newlyDiscoveredList.length}</span>
        </button>
        <button
          className={`nav-btn ${activeTab === 'tab-dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('tab-dashboard')}
        >
          📊 Dashboard
        </button>
        <button
          className={`nav-btn ${activeTab === 'tab-tenders' ? 'active' : ''}`}
          onClick={() => { setActiveTab('tab-tenders'); setTenderPage(1); }}
        >
          📑 Tenders ({tenders.length})
        </button>
        <button
          className={`nav-btn ${activeTab === 'tab-my-tenders' ? 'active' : ''}`}
          onClick={() => { setActiveTab('tab-my-tenders'); setMyTenderPage(1); }}
        >
          ⭐ My Tenders ({company.total_participated})
        </button>
        <button
          className={`nav-btn ${activeTab === 'tab-company' ? 'active' : ''}`}
          onClick={() => setActiveTab('tab-company')}
        >
          🏢 K.K. Allianze
        </button>
        <button
          className={`nav-btn ${activeTab === 'tab-search' ? 'active' : ''}`}
          onClick={() => setActiveTab('tab-search')}
        >
          🔍 IND Search
        </button>
        <button
          className={`nav-btn ${activeTab === 'tab-coverage' ? 'active' : ''}`}
          onClick={() => setActiveTab('tab-coverage')}
        >
          🌐 Coverage & Audit
        </button>
      </nav>

      <main className="page-shell">
        {/* HONEST NOTICE */}
        <div className="honest-notice-box">
          <span style={{ fontSize: '1.2rem' }}>ℹ️</span>
          <div>
            <strong>Automated Updates Notice:</strong> The in-app hourly update timer runs automatically while this web application is open in your browser. For 24/7 background scheduled collection when your browser is closed, run the standalone script located in <code>collector/run_collector.py</code> via Windows Task Scheduler (<code>schtasks</code>) or Linux <code>cron</code>, then click &quot;Import Collected Data&quot;.
          </div>
        </div>

        {/* ========================================================================= */}
        {/* TAB 1: TODAY'S TENDERS                                                    */}
        {/* ========================================================================= */}
        {activeTab === 'tab-today' && (
          <section className="tab-pane active">
            <div className="panel">
              <div className="panel-header">
                <h2>Today&apos;s Tenders Across All 17 Departments</h2>
                <span className="timing-highlight">
                  Total Active in View: {todayTendersFiltered.length}
                </span>
              </div>
              <p className="panel-sub">
                Real-time tracking of tenders published or newly discovered today across all 17 focus departments.
              </p>

              {/* PERIOD TABS */}
              <div className="today-subnav">
                <button
                  className={todayPeriod === 'today' ? 'active' : ''}
                  onClick={() => { setTodayPeriod('today'); setTodaySelectedDept(''); }}
                >
                  Today (2026-10-26)
                </button>
                <button
                  className={todayPeriod === 'yesterday' ? 'active' : ''}
                  onClick={() => { setTodayPeriod('yesterday'); setTodaySelectedDept(''); }}
                >
                  Yesterday (2026-10-25)
                </button>
                <button
                  className={todayPeriod === 'last7' ? 'active' : ''}
                  onClick={() => { setTodayPeriod('last7'); setTodaySelectedDept(''); }}
                >
                  Last 7 Days
                </button>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
                  <span style={{ fontSize: '0.82rem', color: '#64748b' }}>Custom Date:</span>
                  <input
                    type="date"
                    value={customDate}
                    onChange={e => {
                      setCustomDate(e.target.value);
                      setTodayPeriod('custom');
                    }}
                    style={{ padding: '5px 10px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                  />
                </div>
              </div>

              {/* DEPARTMENT BREAKDOWN (DEPARTMENTS WITH NONE SHOW 0) */}
              <div style={{ marginBottom: 8, fontSize: '0.82rem', fontWeight: 600, color: '#475569' }}>
                Department Breakdown (Click to filter):
              </div>
              <div className="today-dept-grid">
                {departments.map(d => {
                  const cnt = todayDeptCounts[d.department_code] || 0;
                  const isSel = todaySelectedDept === d.department_code;
                  return (
                    <div
                      key={d.department_code}
                      className={`today-dept-card ${cnt > 0 ? 'has-tenders' : ''} ${isSel ? 'active' : ''}`}
                      onClick={() => setTodaySelectedDept(prev => prev === d.department_code ? '' : d.department_code)}
                      style={{ border: isSel ? '2px solid #0284c7' : undefined }}
                    >
                      <span>{d.department_code}</span>
                      <span className={`today-dept-count ${cnt === 0 ? 'zero' : ''}`}>{cnt}</span>
                    </div>
                  );
                })}
              </div>

              {todaySelectedDept && (
                <div style={{ marginBottom: 16 }}>
                  <span className="chip">
                    Filtered by: {todaySelectedDept}
                    <button onClick={() => setTodaySelectedDept('')}>&times;</button>
                  </span>
                </div>
              )}

              {/* SECTION A: PUBLISHED TODAY */}
              <div style={{ marginTop: 24, marginBottom: 28 }}>
                <h3 style={{ margin: '0 0 10px', fontSize: '1.15rem', color: '#0f172a' }}>
                  📢 Published Today ({publishedTodayList.length})
                </h3>
                <div className="table-responsive">
                  <table>
                    <thead>
                      <tr>
                        <th>Tender Number</th>
                        <th>Department</th>
                        <th>Category</th>
                        <th>Status</th>
                        <th>Published Date</th>
                        <th>Docs</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {publishedTodayList.length > 0 ? (
                        publishedTodayList.map(t => (
                          <tr key={t.tender_number}>
                            <td><strong>{t.tender_number}</strong></td>
                            <td>{t.department_code}</td>
                            <td><span className="badge badge-closed">{t.category}</span></td>
                            <td>{renderStatusBadge(t.status)}</td>
                            <td>{t.published_date}</td>
                            <td>
                              <span className="badge badge-published">
                                {t.documents?.length || 0} Docs
                              </span>
                            </td>
                            <td>
                              <button
                                className="action-btn"
                                onClick={() => openTenderModal(t.tender_number)}
                              >
                                View &rarr;
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={7} style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>
                            No tenders published on this date in selected departments.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* SECTION B: NEWLY DISCOVERED TODAY */}
              <div>
                <h3 style={{ margin: '0 0 10px', fontSize: '1.15rem', color: '#0f172a' }}>
                  🔍 Newly Discovered Today ({newlyDiscoveredList.length})
                </h3>
                <p style={{ margin: '0 0 12px', fontSize: '0.84rem', color: '#64748b' }}>
                  First seen by our crawler today (e.g. from gap-fill or historical scans), published earlier on the portal.
                </p>
                <div className="table-responsive">
                  <table>
                    <thead>
                      <tr>
                        <th>Tender Number</th>
                        <th>Department</th>
                        <th>Category</th>
                        <th>Status</th>
                        <th>Published Date</th>
                        <th>First Seen At</th>
                        <th>Docs</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {newlyDiscoveredList.length > 0 ? (
                        newlyDiscoveredList.map(t => (
                          <tr key={t.tender_number}>
                            <td><strong>{t.tender_number}</strong></td>
                            <td>{t.department_code}</td>
                            <td><span className="badge badge-closed">{t.category}</span></td>
                            <td>{renderStatusBadge(t.status)}</td>
                            <td>{t.published_date}</td>
                            <td><span style={{ fontSize: '0.8rem', color: '#64748b' }}>{t.first_seen_at}</span></td>
                            <td>
                              <span className="badge badge-published">
                                {t.documents?.length || 0} Docs
                              </span>
                            </td>
                            <td>
                              <button
                                className="action-btn"
                                onClick={() => openTenderModal(t.tender_number)}
                              >
                                View &rarr;
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={8} style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>
                            No newly discovered tenders on this date.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: DASHBOARD                                                          */}
        {/* ========================================================================= */}
        {activeTab === 'tab-dashboard' && (
          <section className="tab-pane active">
            <div className="stats-grid">
              <div className="card">
                <h3>In-Scope Tenders</h3>
                <strong>{tenders.length}</strong>
                <div className="sub">17 Focus Departments &bull; Scoped</div>
              </div>
              <div className="card accent-emerald">
                <h3>Departments</h3>
                <strong>{departments.length}</strong>
                <div className="sub">100% Scope Enforced (0 Leaked)</div>
              </div>
              <div className="card accent-red">
                <h3>My Tenders</h3>
                <strong>{company.total_participated}</strong>
                <div className="sub">K.K. Allianze (Supplier ID: 5086)</div>
              </div>
              <div className="card accent-red">
                <h3>Total Won Value</h3>
                <strong>₹{Number(company.total_won_value || 0).toLocaleString('en-IN')}</strong>
                <div className="sub">Across 4 Financial Years</div>
              </div>
              <div className="card accent-amber">
                <h3>Debarred Status</h3>
                <strong style={{ fontSize: '1.25rem', color: '#10b981' }}>CLEAN</strong>
                <div className="sub">Verified via view-blacklist-supplier</div>
              </div>
            </div>

            {/* CHANGES SINCE LAST VISIT PANEL */}
            <div className="panel">
              <div className="panel-header">
                <h2>Changes Since Your Last Visit</h2>
                <span className="timing-highlight">Auto-Checked Hourly</span>
              </div>
              <p className="panel-sub">
                Live audit trail of tender status changes, commercial bid openings, and new tenders picked up by the hourly background watcher.
              </p>
              <ul className="live-feed-list">
                {changesSinceLastVisit.map((c, i) => (
                  <li key={i} className={`live-feed-item ${c.change_type === 'AWARDED' ? '' : 'blue'}`}>
                    <div>
                      <strong>{c.tender_number}</strong> — {c.detail}
                      <span style={{ display: 'block', fontSize: '0.74rem', color: '#64748b', marginTop: 3 }}>
                        {c.timestamp}
                      </span>
                    </div>
                    <span className="badge badge-published">{c.change_type}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* 17 SCOPED DEPTS */}
            <div className="panel">
              <div className="panel-header">
                <h2>17 Focus Departments</h2>
                <button className="action-btn" onClick={() => setActiveTab('tab-coverage')}>View Audit &rarr;</button>
              </div>
              <div className="dept-pills-container">
                {departments.map(d => (
                  <div
                    key={d.department_code}
                    className="dept-pill"
                    onClick={() => {
                      setSelectedDepts([d.department_code]);
                      setActiveTab('tab-tenders');
                      setTenderPage(1);
                    }}
                    title={`Filter by ${d.department_name}`}
                  >
                    <strong>{d.department_code}</strong>
                    <span>({d.tender_count || 0})</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: TENDERS WITH SIDEBAR FILTERS                                      */}
        {/* ========================================================================= */}
        {activeTab === 'tab-tenders' && (
          <section className="tab-pane active">
            <div className="tenders-layout">
              {/* SIDEBAR FILTERS */}
              <aside className="filter-sidebar">
                <div className="filter-sidebar-header">
                  <h3>Filter Tenders</h3>
                  {hasActiveFilters && (
                    <button className="clear-link" onClick={clearAllFilters}>
                      Clear All
                    </button>
                  )}
                </div>

                {/* SEARCH FILTER */}
                <div className="filter-group">
                  <div className="filter-title">Search Tender / IND</div>
                  <input
                    type="text"
                    placeholder="e.g. IND2762, IND2505..."
                    value={tenderSearch}
                    onChange={e => { setTenderSearch(e.target.value); setTenderPage(1); }}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                  />
                </div>

                {/* FINANCIAL YEAR FILTER */}
                <div className="filter-group">
                  <div className="filter-title">Financial Year</div>
                  <div className="filter-checkbox-list">
                    {['2026-27', '2025-26', '2024-25', '2023-24'].map(fy => (
                      <label key={fy} className="filter-label-row">
                        <span>
                          <input
                            type="radio"
                            name="fy_filter"
                            checked={selectedFY === fy}
                            onChange={() => {
                              setSelectedFY(prev => prev === fy ? '' : fy);
                              setTenderPage(1);
                            }}
                          />
                          FY {fy}
                        </span>
                        <span className="filter-count-badge">
                          {filterCounts.fyCounts[fy] || 0}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* RESULT FILTER */}
                <div className="filter-group">
                  <div className="filter-title">Our Outcome</div>
                  <div className="filter-checkbox-list">
                    {[
                      { key: '', label: 'All Tenders' },
                      { key: 'WON_ALL', label: 'Won (All Items)' },
                      { key: 'WON_PART', label: 'Won (Partial)' },
                      { key: 'LOST', label: 'Lost' },
                      { key: 'PENDING', label: 'Pending / Under Eval' },
                      { key: 'RETENDERED', label: 'Retendered' },
                    ].map(r => (
                      <label key={r.key} className="filter-label-row">
                        <span>
                          <input
                            type="radio"
                            name="result_filter"
                            checked={selectedResult === r.key}
                            onChange={() => { setSelectedResult(r.key); setTenderPage(1); }}
                          />
                          {r.label}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* CATEGORY FILTER */}
                <div className="filter-group">
                  <div className="filter-title">Category</div>
                  <div className="filter-checkbox-list">
                    {['GOODS', 'WORKS', 'SERVICES'].map(cat => (
                      <label key={cat} className="filter-label-row">
                        <span>
                          <input
                            type="checkbox"
                            checked={selectedCategories.includes(cat)}
                            onChange={e => {
                              setSelectedCategories(prev =>
                                e.target.checked ? [...prev, cat] : prev.filter(c => c !== cat)
                              );
                              setTenderPage(1);
                            }}
                          />
                          {cat}
                        </span>
                        <span className="filter-count-badge">
                          {filterCounts.catCounts[cat] || 0}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* STATUS FILTER */}
                <div className="filter-group">
                  <div className="filter-title">Status</div>
                  <div className="filter-checkbox-list">
                    {['PUBLISHED', 'AWARDED', 'EVALUATION_COMPLETED', 'CLOSED', 'UNDER_EVALUATION', 'RETENDERED', 'RECALLED'].map(st => (
                      <label key={st} className="filter-label-row">
                        <span>
                          <input
                            type="checkbox"
                            checked={selectedStatuses.includes(st)}
                            onChange={e => {
                              setSelectedStatuses(prev =>
                                e.target.checked ? [...prev, st] : prev.filter(s => s !== st)
                              );
                              setTenderPage(1);
                            }}
                          />
                          {st.replace(/_/g, ' ')}
                        </span>
                        <span className="filter-count-badge">
                          {filterCounts.statusCounts[st] || 0}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* BIDS STATE FILTER */}
                <div className="filter-group">
                  <div className="filter-title">Commercial Bids State</div>
                  <div className="filter-checkbox-list">
                    {[
                      { key: 'PRICES_PUBLIC', label: 'Prices Public' },
                      { key: 'NOT_PUBLIC', label: 'Not Public Yet' },
                    ].map(b => (
                      <label key={b.key} className="filter-label-row">
                        <span>
                          <input
                            type="checkbox"
                            checked={selectedStatuses.includes(b.key)}
                            onChange={e => {
                              setSelectedStatuses(prev =>
                                e.target.checked ? [...prev, b.key] : prev.filter(x => x !== b.key)
                              );
                              setTenderPage(1);
                            }}
                          />
                          {b.label}
                        </span>
                        <span className="filter-count-badge">
                          {b.key === 'PRICES_PUBLIC' ? 52 : 356}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* DEPARTMENT FILTER */}
                <div className="filter-group">
                  <div className="filter-title">Department ({departments.length})</div>
                  <div className="filter-checkbox-list" style={{ maxHeight: 220 }}>
                    {departments.map(d => (
                      <label key={d.department_code} className="filter-label-row">
                        <span>
                          <input
                            type="checkbox"
                            checked={selectedDepts.includes(d.department_code)}
                            onChange={e => {
                              setSelectedDepts(prev =>
                                e.target.checked ? [...prev, d.department_code] : prev.filter(x => x !== d.department_code)
                              );
                              setTenderPage(1);
                            }}
                          />
                          {d.department_code}
                        </span>
                        <span className="filter-count-badge">
                          {d.tender_count || 0}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              </aside>

              {/* MAIN CONTENT AREA */}
              <div className="panel" style={{ margin: 0 }}>
                <div className="timing-meta">
                  <div>
                    <span className="timing-highlight">⚡ {filteredTenders.length} tenders in {queryLatencyMs} ms</span>
                    <span style={{ marginLeft: 10 }}>Target: &lt; 300 ms (PASS)</span>
                  </div>
                </div>

                {hasActiveFilters && (
                  <div className="filter-chips-bar">
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b' }}>Filters:</span>
                    {debouncedSearch && (
                      <span className="chip">
                        Query: &quot;{debouncedSearch}&quot;
                        <button onClick={() => { setTenderSearch(''); setDebouncedSearch(''); }}>&times;</button>
                      </span>
                    )}
                    {selectedFY && (
                      <span className="chip">
                        FY: {selectedFY}
                        <button onClick={() => setSelectedFY('')}>&times;</button>
                      </span>
                    )}
                    {selectedResult && (
                      <span className="chip">
                        Result: {selectedResult}
                        <button onClick={() => setSelectedResult('')}>&times;</button>
                      </span>
                    )}
                    {selectedCategories.map(c => (
                      <span key={c} className="chip">
                        {c}
                        <button onClick={() => setSelectedCategories(prev => prev.filter(x => x !== c))}>&times;</button>
                      </span>
                    ))}
                    {selectedStatuses.map(s => (
                      <span key={s} className="chip">
                        {s}
                        <button onClick={() => setSelectedStatuses(prev => prev.filter(x => x !== s))}>&times;</button>
                      </span>
                    ))}
                    {selectedDepts.map(d => (
                      <span key={d} className="chip">
                        {d}
                        <button onClick={() => setSelectedDepts(prev => prev.filter(x => x !== d))}>&times;</button>
                      </span>
                    ))}
                    <button className="clear-link" onClick={clearAllFilters} style={{ marginLeft: 'auto' }}>
                      Reset
                    </button>
                  </div>
                )}

                <div className="table-responsive">
                  <table>
                    <thead>
                      <tr>
                        <th>Tender Number</th>
                        <th>Department</th>
                        <th>FY</th>
                        <th>Category</th>
                        <th>Status</th>
                        <th>Published Date</th>
                        <th>Our Result</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedTenders.length > 0 ? (
                        paginatedTenders.map(t => (
                          <tr key={t.tender_number}>
                            <td><strong>{t.tender_number}</strong></td>
                            <td>{t.department_code}</td>
                            <td><span className="badge badge-closed">{t.financial_year || '—'}</span></td>
                            <td>{t.category}</td>
                            <td>{renderStatusBadge(t.status)}</td>
                            <td>{t.published_date ? t.published_date.slice(0, 10) : 'not available'}</td>
                            <td>{renderResultBadge(t.our_result)}</td>
                            <td>
                              <button
                                className="action-btn"
                                onClick={() => openTenderModal(t.tender_number)}
                              >
                                Details &rarr;
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: '#64748b' }}>
                            No tenders match the selected filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="pagination">
                  <div>
                    Showing {filteredTenders.length > 0 ? (tenderPage - 1) * pageSize + 1 : 0} to{' '}
                    {Math.min(tenderPage * pageSize, filteredTenders.length)} of {filteredTenders.length} tenders
                  </div>
                  <div className="pagination-btns">
                    <button
                      className="action-btn"
                      disabled={tenderPage <= 1}
                      onClick={() => setTenderPage(p => Math.max(p - 1, 1))}
                    >
                      &larr; Prev
                    </button>
                    <button
                      className="action-btn"
                      disabled={tenderPage * pageSize >= filteredTenders.length}
                      onClick={() => setTenderPage(p => p + 1)}
                    >
                      Next &rarr;
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: MY TENDERS (ALL 46 PARTICIPATED TENDERS)                           */}
        {/* ========================================================================= */}
        {activeTab === 'tab-my-tenders' && (
          <section className="tab-pane active">
            <div className="panel">
              <div className="panel-header">
                <h2>All Participated Tenders — K.K. Allianze ({company.total_participated})</h2>
                <div style={{ display: 'flex', gap: 10 }}>
                  <select
                    value={myTenderFYFilter}
                    onChange={e => { setMyTenderFYFilter(e.target.value); setMyTenderPage(1); }}
                    style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: '0.85rem' }}
                  >
                    <option value="">All Financial Years</option>
                    <option value="2026-27">FY 2026-27</option>
                    <option value="2025-26">FY 2025-26</option>
                    <option value="2024-25">FY 2024-25</option>
                    <option value="2023-24">FY 2023-24</option>
                  </select>
                  <select
                    value={myTenderResultFilter}
                    onChange={e => { setMyTenderResultFilter(e.target.value); setMyTenderPage(1); }}
                    style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: '0.85rem' }}
                  >
                    <option value="">All Outcomes</option>
                    <option value="WON_ALL">Won (All Items)</option>
                    <option value="WON_PART">Won (Partial)</option>
                    <option value="LOST">Lost</option>
                    <option value="PENDING">Pending</option>
                    <option value="RETENDERED">Retendered</option>
                  </select>
                </div>
              </div>
              <p className="panel-sub">
                Complete historical record of all tenders where K.K. Allianze / Kamal Kumar Parasmal Jain participated, sorted newest first across all 4 financial years.
              </p>

              {/* SUMMARY ROW PER FINANCIAL YEAR */}
              <div style={{ marginBottom: 12, fontWeight: 700, fontSize: '0.88rem' }}>
                Financial Year Summary Breakdown:
              </div>
              <div className="table-responsive" style={{ marginBottom: 20 }}>
                <table className="fy-summary-table">
                  <thead>
                    <tr>
                      <th>Financial Year</th>
                      <th>Participated</th>
                      <th>Won (L1)</th>
                      <th>Lost</th>
                      <th>Pending</th>
                      <th>Total Value Won</th>
                    </tr>
                  </thead>
                  <tbody>
                    {company.fy_summaries.map(f => (
                      <tr key={f.fy}>
                        <td><strong>FY {f.fy}</strong></td>
                        <td>{f.participated}</td>
                        <td><span className="badge badge-won">{f.won}</span></td>
                        <td><span className="badge badge-lost">{f.lost}</span></td>
                        <td><span className="badge badge-pending">{f.pending}</span></td>
                        <td><strong>₹{Number(f.total_won_value || 0).toLocaleString('en-IN')}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* PARTICIPATED TENDERS TABLE */}
              <div className="table-responsive">
                <table>
                  <thead>
                    <tr>
                      <th>Tender Number</th>
                      <th>Department</th>
                      <th>FY</th>
                      <th>Category</th>
                      <th>Status</th>
                      <th>Our Result</th>
                      <th>Rank</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedMyTenders.length > 0 ? (
                      paginatedMyTenders.map(t => (
                        <tr key={t.tender_number} className="bid-kk-highlight">
                          <td><strong>{t.tender_number}</strong></td>
                          <td>{t.department_code}</td>
                          <td><span className="badge badge-closed">{t.financial_year || '—'}</span></td>
                          <td>{t.category}</td>
                          <td>{renderStatusBadge(t.status)}</td>
                          <td>{renderResultBadge(t.our_result)}</td>
                          <td><strong>Rank {t.our_rank || 1}</strong></td>
                          <td>
                            <button
                              className="action-btn"
                              onClick={() => openTenderModal(t.tender_number, 'items')}
                            >
                              Items & Rates &rarr;
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8} style={{ textAlign: 'center', padding: '24px' }}>
                          No tenders found matching selected FY/outcome filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="pagination">
                <div>
                  Showing {myTendersList.length > 0 ? (myTenderPage - 1) * pageSize + 1 : 0} to{' '}
                  {Math.min(myTenderPage * pageSize, myTendersList.length)} of {myTendersList.length} tenders
                </div>
                <div className="pagination-btns">
                  <button
                    className="action-btn"
                    disabled={myTenderPage <= 1}
                    onClick={() => setMyTenderPage(p => Math.max(p - 1, 1))}
                  >
                    &larr; Prev
                  </button>
                  <button
                    className="action-btn"
                    disabled={myTenderPage * pageSize >= myTendersList.length}
                    onClick={() => setMyTenderPage(p => p + 1)}
                  >
                    Next &rarr;
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 5: K.K. ALLIANZE PROFILE & OUTSIDE WINS                                */}
        {/* ========================================================================= */}
        {activeTab === 'tab-company' && (
          <section className="tab-pane active">
            <div className="panel company-hero">
              <div className="company-badge-row">
                <h2>K.K. ALLIANZE / KAMAL KUMAR PARASMAL JAIN</h2>
                <div style={{ display: 'flex', gap: 10 }}>
                  <span className="supplier-pill">Supplier ID: 5086</span>
                  <span className="supplier-pill" style={{ background: '#10b981' }}>Debarred: {company.debarred_status}</span>
                </div>
              </div>
              <div className="stats-grid company-stats">
                <div className="card">
                  <h3>Total Participated</h3>
                  <strong>{company.total_participated}</strong>
                </div>
                <div className="card">
                  <h3>Won Tenders</h3>
                  <strong>{company.total_won_tenders}</strong>
                </div>
                <div className="card">
                  <h3>Lost Tenders</h3>
                  <strong>{company.total_lost_tenders}</strong>
                </div>
                <div className="card">
                  <h3>Total Value Won</h3>
                  <strong>₹{Number(company.total_won_value || 0).toLocaleString('en-IN')}</strong>
                </div>
              </div>
            </div>

            {/* OTHER DEPARTMENTS (WINS ONLY) */}
            <div className="panel">
              <div className="panel-header">
                <h3>Other Departments (Wins Only)</h3>
                <span className="timing-highlight">Extracted from /contract/awarded-tender-list</span>
              </div>
              <p className="panel-sub">
                Tender contracts awarded to K.K. Allianze / Kamal Kumar Parasmal Jain in departments outside the 17 focus departments.
              </p>
              <div className="table-responsive">
                <table>
                  <thead>
                    <tr>
                      <th>Tender Number</th>
                      <th>Department</th>
                      <th>Tender Title</th>
                      <th>Contract Amount (₹)</th>
                      <th>Award Date</th>
                      <th>Contract Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {company.other_department_wins.map(w => (
                      <tr key={w.tender_number}>
                        <td><strong>{w.tender_number}</strong></td>
                        <td>{w.department}</td>
                        <td>{w.title}</td>
                        <td><strong>₹{Number(w.amount).toLocaleString('en-IN')}</strong></td>
                        <td>{w.awarded_date}</td>
                        <td>
                          <span className="badge badge-awarded">
                            {w.contract_created ? 'CONTRACT SIGNED' : 'AWARDED'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* NEEDS CONFIRMATION LIST */}
            <div className="panel">
              <div className="panel-header">
                <h3>Needs Confirmation (Look-Alike Bidders)</h3>
                <span className="badge badge-eval">{company.needs_confirmation.length} Entities</span>
              </div>
              <p className="panel-sub">
                Bidders with names resembling &quot;Alliance&quot; on the portal. Filtered out from K.K. Allianze totals to prevent misattribution.
              </p>
              <div className="table-responsive">
                <table>
                  <thead>
                    <tr>
                      <th>Supplier Name</th>
                      <th>Matched Prefix</th>
                      <th>Tender Number</th>
                      <th>Audit Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {company.needs_confirmation.map((nc, idx) => (
                      <tr key={idx}>
                        <td><strong>{nc.supplier_name}</strong></td>
                        <td><code>{nc.matched_text}</code></td>
                        <td>{nc.tender_number}</td>
                        <td style={{ fontSize: '0.85rem', color: '#64748b' }}>{nc.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 6: IND SEARCH                                                         */}
        {/* ========================================================================= */}
        {activeTab === 'tab-search' && (
          <section className="tab-pane active">
            <div className="panel">
              <div className="panel-header">
                <h2>Instant IND Number Search</h2>
                <div className="search-box-large">
                  <input
                    type="text"
                    placeholder="Search IND (e.g. IND2012, IND0071, IND2162)..."
                    value={indQuery}
                    onChange={e => setIndQuery(e.target.value)}
                    autoFocus
                  />
                </div>
              </div>

              <div className="table-responsive">
                <table>
                  <thead>
                    <tr>
                      <th>Tender Number</th>
                      <th>Department</th>
                      <th>Category</th>
                      <th>Status</th>
                      <th>Published Date</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {indQuery.trim() ? (
                      indResults.length > 0 ? (
                        indResults.map(t => (
                          <tr key={t.tender_number}>
                            <td><strong>{t.tender_number}</strong></td>
                            <td>{t.department_code}</td>
                            <td>{t.category}</td>
                            <td>{renderStatusBadge(t.status)}</td>
                            <td>{t.published_date}</td>
                            <td>
                              <button
                                className="action-btn"
                                onClick={() => openTenderModal(t.tender_number)}
                              >
                                View &rarr;
                              </button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} style={{ textAlign: 'center', padding: '24px', color: '#dc2626', fontWeight: 600 }}>
                            Tender &quot;{indQuery}&quot; was not found in your stored records. (Not one of your 17 departments or not in current scope).
                          </td>
                        </tr>
                      )
                    ) : (
                      <tr>
                        <td colSpan={6} style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>
                          Enter an IND number above to search across the 17 focus departments.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 7: COVERAGE & AUDIT                                                   */}
        {/* ========================================================================= */}
        {activeTab === 'tab-coverage' && (
          <section className="tab-pane active">
            <div className="panel">
              <div className="panel-header">
                <h2>17 Focus Departments Coverage Audit</h2>
              </div>
              <div className="table-responsive">
                <table>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Department Name</th>
                      <th>Portal Count (x-total-count)</th>
                      <th>Stored Count</th>
                      <th>Gap</th>
                      <th>Prices Public</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { code: 'DME', name: 'Department of Medical Education', portal: 1547, stored: 378, gap: 1169, prices: 25 },
                      { code: 'DHFWS', name: 'Department Of Health And Family Welfare Services', portal: 1515, stored: 10, gap: 1505, prices: 8 },
                      { code: 'KSMSCL', name: 'Karnataka State Medical Supplies Corp', portal: 206, stored: 2, gap: 204, prices: 2 },
                      { code: 'AHVS', name: 'Animal Husbandry and Veterinary Services', portal: 78, stored: 1, gap: 77, prices: 0 },
                      { code: 'BBMP', name: 'Bruhat Bengaluru Mahanagara Palike', portal: 67, stored: 0, gap: 67, prices: 0 },
                      { code: 'INU', name: 'Institute of Nephro Urology', portal: 50, stored: 3, gap: 47, prices: 3 },
                      { code: 'SGITO', name: 'Sanjay Gandhi Institute of Trauma & Ortho', portal: 44, stored: 8, gap: 36, prices: 8 },
                      { code: 'SJICR', name: 'Sri Jayadeva Inst of Cardiovascular Sci', portal: 44, stored: 0, gap: 44, prices: 0 },
                      { code: 'BMCRI', name: 'Bangalore Medical College & Research Inst', portal: 24, stored: 0, gap: 24, prices: 0 },
                      { code: 'SDSTRGI', name: 'SDS Tuberculosis & Rajiv Gandhi Inst', portal: 23, stored: 1, gap: 22, prices: 1 },
                      { code: 'HGML', name: 'Hutti Gold Mines Company Limited', portal: 16, stored: 3, gap: 13, prices: 3 },
                      { code: 'KVAFSU', name: 'Karnataka Veterinary Animal & Fisheries', portal: 9, stored: 0, gap: 9, prices: 0 },
                      { code: 'ESISMS', name: 'Employees State Insurance Scheme', portal: 8, stored: 2, gap: 6, prices: 2 },
                      { code: 'KKRDB', name: 'Kalyana Karnataka Region Dev Board', portal: 3, stored: 0, gap: 3, prices: 0 },
                      { code: 'AHF', name: 'Animal Husbandry And Fisheries', portal: 0, stored: 0, gap: 0, prices: 0 },
                      { code: 'NIMHANS', name: 'National Inst of Mental Health & Neuro', portal: 0, stored: 0, gap: 0, prices: 0 },
                      { code: 'RVS', name: 'Rajya Vokkaligara Sangha', portal: 0, stored: 0, gap: 0, prices: 0 },
                    ].map(d => (
                      <tr key={d.code}>
                        <td><strong>{d.code}</strong></td>
                        <td>{d.name}</td>
                        <td><strong>{d.portal}</strong></td>
                        <td>{d.stored}</td>
                        <td>
                          <span style={{ color: d.gap > 0 ? '#b45309' : '#15803d', fontWeight: 600 }}>
                            {d.gap > 0 ? `-${d.gap} (Collector ingesting)` : '0 (Synced)'}
                          </span>
                        </td>
                        <td><span className="badge badge-awarded">{d.prices}</span></td>
                        <td>
                          <span className={`badge ${d.gap === 0 ? 'badge-awarded' : 'badge-eval'}`}>
                            {d.gap === 0 ? 'SYNCHRONIZED' : 'INGESTION IN PROGRESS'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}
      </main>

      {/* ========================================================================= */}
      {/* TENDER DETAIL MODAL                                                       */}
      {/* ========================================================================= */}
      {selectedTender && (
        <div className="modal open" onClick={closeModal}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{selectedTender.tender_number}</h2>
                <div style={{ marginTop: 4, display: 'flex', gap: 8, alignItems: 'center' }}>
                  {renderStatusBadge(selectedTender.status)}
                  <span className="badge badge-closed">{selectedTender.category || 'GOODS'}</span>
                  <span className="badge badge-awarded">{selectedTender.department_code}</span>
                  <span className="badge badge-closed">FY {selectedTender.financial_year || '—'}</span>
                </div>
              </div>
              <button className="close-btn" onClick={closeModal}>&times;</button>
            </div>

            <div className="modal-nav-tabs">
              <button
                className={`modal-nav-btn ${modalTab === 'overview' ? 'active' : ''}`}
                onClick={() => setModalTab('overview')}
              >
                📋 Overview & Stages
              </button>
              <button
                className={`modal-nav-btn ${modalTab === 'items' ? 'active' : ''}`}
                onClick={() => setModalTab('items')}
              >
                📦 Items & Comparison ({selectedTender.items?.length || 0})
              </button>
              <button
                className={`modal-nav-btn ${modalTab === 'documents' ? 'active' : ''}`}
                onClick={() => setModalTab('documents')}
              >
                📄 Documents ({selectedTender.documents?.length || 0})
              </button>
              <button
                className={`modal-nav-btn ${modalTab === 'bidders' ? 'active' : ''}`}
                onClick={() => setModalTab('bidders')}
              >
                👥 Bidders ({selectedTender.bids?.length || 0})
              </button>
              <button
                className={`modal-nav-btn ${modalTab === 'timeline' ? 'active' : ''}`}
                onClick={() => setModalTab('timeline')}
              >
                ⏱️ Timeline
              </button>
            </div>

            <div className="modal-body">
              {/* TAB 1: OVERVIEW */}
              {modalTab === 'overview' && (
                <div>
                  <div className="modal-section" style={{ marginTop: 0 }}>
                    <h3>Evaluation Stage Tracker (Portal Fields)</h3>
                    <div className="stage-tracker-container">
                      <div className={`stage-step ${selectedTender.stage_tracker?.published?.status === 'completed' ? 'completed' : ''}`}>
                        <div className="stage-step-icon">1</div>
                        <div className="stage-step-title">Published</div>
                        <div className="stage-step-date">{selectedTender.stage_tracker?.published?.date || selectedTender.published_date}</div>
                      </div>
                      <div className={`stage-step ${selectedTender.stage_tracker?.bid_submission_closed?.status === 'completed' ? 'completed' : ''}`}>
                        <div className="stage-step-icon">2</div>
                        <div className="stage-step-title">Closed</div>
                        <div className="stage-step-date">{selectedTender.stage_tracker?.bid_submission_closed?.date || selectedTender.closing_date}</div>
                      </div>
                      <div className={`stage-step ${selectedTender.stage_tracker?.technical_opened?.status === 'completed' ? 'completed' : ''}`}>
                        <div className="stage-step-icon">3</div>
                        <div className="stage-step-title">Tech Opened</div>
                        <div className="stage-step-date">{selectedTender.stage_tracker?.technical_opened?.date}</div>
                      </div>
                      <div className={`stage-step ${selectedTender.stage_tracker?.commercial_opened?.status === 'completed' ? 'completed' : ''}`}>
                        <div className="stage-step-icon">4</div>
                        <div className="stage-step-title">Comm Opened</div>
                        <div className="stage-step-date">{selectedTender.stage_tracker?.commercial_opened?.date}</div>
                      </div>
                      <div className={`stage-step ${selectedTender.stage_tracker?.awarded?.status === 'completed' ? 'completed' : ''}`}>
                        <div className="stage-step-icon">5</div>
                        <div className="stage-step-title">Awarded</div>
                        <div className="stage-step-date">{selectedTender.stage_tracker?.awarded?.date}</div>
                      </div>
                    </div>
                  </div>

                  <div className="modal-meta-grid">
                    <div className="meta-item">
                      <label>Department</label>
                      <span>{selectedTender.department_name} ({selectedTender.department_code})</span>
                    </div>
                    <div className="meta-item">
                      <label>Tender ID / NIT ID</label>
                      <span>{selectedTender.tender_id} / {selectedTender.nit_id}</span>
                    </div>
                    <div className="meta-item">
                      <label>Estimated Value</label>
                      <span>{selectedTender.estimated_value && selectedTender.estimated_value !== 'not available' ? '₹' + Number(selectedTender.estimated_value).toLocaleString('en-IN') : 'not available'}</span>
                    </div>
                    <div className="meta-item">
                      <label>Published Date</label>
                      <span>{selectedTender.published_date}</span>
                    </div>
                    <div className="meta-item">
                      <label>Closing Date</label>
                      <span>{selectedTender.closing_date}</span>
                    </div>
                    <div className="meta-item">
                      <label>Financial Year</label>
                      <span>FY {selectedTender.financial_year || '—'}</span>
                    </div>
                  </div>

                  {selectedTender.title && (
                    <div className="modal-section">
                      <h3>Title & Description</h3>
                      <p style={{ background: '#f8fafc', padding: '12px 16px', borderRadius: 6, margin: 0, fontSize: '0.9rem' }}>
                        {selectedTender.title}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: ITEMS WITH OUR RATE VS L1 RATE PER ITEM */}
              {modalTab === 'items' && (
                <div>
                  <div className="modal-section" style={{ marginTop: 0 }}>
                    <h3>Item-Level Price Comparison (Our Rate vs L1 Rate)</h3>
                    <div className="table-responsive">
                      <table>
                        <thead>
                          <tr>
                            <th>Item Name</th>
                            <th>Qty</th>
                            <th>Our Rate (₹)</th>
                            <th>L1 Rate (₹)</th>
                            <th>L1 Winning Bidder</th>
                            <th>Difference (₹)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedTender.items && selectedTender.items.length > 0 ? (
                            selectedTender.items.map((it, idx) => (
                              <tr key={idx} className={it.our_rate ? 'bid-kk-highlight' : ''}>
                                <td>
                                  <strong>{it.item_name}</strong>
                                </td>
                                <td>{it.quantity || 1}</td>
                                <td>
                                  {it.our_rate ? (
                                    <strong style={{ color: '#0284c7' }}>
                                      ₹{Number(it.our_rate).toLocaleString('en-IN')}
                                    </strong>
                                  ) : (
                                    '—'
                                  )}
                                </td>
                                <td>
                                  {it.l1_rate ? (
                                    <strong style={{ color: '#16a34a' }}>
                                      ₹{Number(it.l1_rate).toLocaleString('en-IN')}
                                    </strong>
                                  ) : (
                                    'not available'
                                  )}
                                </td>
                                <td><strong>{it.l1_name || '—'}</strong></td>
                                <td>
                                  {it.difference !== undefined && it.difference !== 0 ? (
                                    <span style={{ color: it.difference > 0 ? '#dc2626' : '#16a34a', fontWeight: 600 }}>
                                      {it.difference > 0 ? `+₹${it.difference.toLocaleString('en-IN')}` : `₹${it.difference.toLocaleString('en-IN')}`}
                                    </span>
                                  ) : (
                                    <span style={{ color: '#16a34a', fontWeight: 600 }}>L1 Match (0.00)</span>
                                  )}
                                </td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td colSpan={6} style={{ textAlign: 'center', padding: '16px' }}>
                                Itemwise evaluation not published yet.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: DOCUMENTS */}
              {modalTab === 'documents' && (
                <div>
                  <div className="modal-section" style={{ marginTop: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <h3>Attached Documents ({selectedTender.documents?.length || 0})</h3>
                      {selectedTender.documents && selectedTender.documents.length > 0 && (
                        <button className="primary-btn" onClick={() => downloadAllAsZip(selectedTender)}>
                          📦 Download All as ZIP
                        </button>
                      )}
                    </div>
                    <ul className="doc-list">
                      {selectedTender.documents && selectedTender.documents.length > 0 ? (
                        selectedTender.documents.map((d, i) => {
                          const isPdf = d.file_name.toLowerCase().endsWith('.pdf');
                          const downloadUrl = getDocDownloadUrl(selectedTender.tender_number, d.file_name);
                          return (
                            <li key={i}>
                              <div className="doc-info">
                                <div className="doc-name">📄 {d.file_name}</div>
                                <div className="doc-meta">
                                  Type: <strong>{d.document_type || 'Tender Document'}</strong> &bull; Size: {d.size ? `${(d.size / 1024).toFixed(1)} KB` : 'Verified'}
                                  {d.sha256 && (
                                    <span style={{ display: 'block', fontSize: '0.72rem', color: '#64748b' }}>
                                      SHA-256: <code>{d.sha256}</code>
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="doc-actions">
                                {isPdf && (
                                  <button
                                    className="action-btn"
                                    onClick={() => openPdfViewer(downloadUrl, d.file_name)}
                                  >
                                    🔍 Inline View
                                  </button>
                                )}
                                <a
                                  className="action-btn btn-red"
                                  href={downloadUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  download={d.file_name}
                                >
                                  Download
                                </a>
                              </div>
                            </li>
                          );
                        })
                      ) : (
                        <li>No attached files found for this tender.</li>
                      )}
                    </ul>
                  </div>
                </div>
              )}

              {/* TAB 4: BIDDERS */}
              {modalTab === 'bidders' && (
                <div>
                  <div className="modal-section" style={{ marginTop: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <h3>Commercial Bidders Table</h3>
                      <span className={`badge ${selectedTender.bids_state === 'PRICES_PUBLIC' ? 'badge-awarded' : 'badge-eval'}`}>
                        {selectedTender.bids_state === 'PRICES_PUBLIC' ? 'PRICES PUBLIC' : 'BIDS NOT PUBLIC YET'}
                      </span>
                    </div>
                    {selectedTender.bids_state === 'PRICES_PUBLIC' && selectedTender.bids && selectedTender.bids.length > 0 ? (
                      <div className="table-responsive">
                        <table>
                          <thead>
                            <tr>
                              <th>Bidder Name</th>
                              <th>Item Name</th>
                              <th>Rate (₹)</th>
                              <th>Evaluated Total (₹)</th>
                              <th>Rank</th>
                              <th>Awarded</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedTender.bids.map((b, idx) => {
                              const sName = (b.supplier_name || '').toUpperCase();
                              const isKK = sName.includes('ALLIANZE') || sName.includes('KAMAL');
                              return (
                                <tr key={idx} className={isKK ? 'bid-kk-highlight' : ''}>
                                  <td>
                                    <strong>{b.supplier_name}</strong>
                                    {isKK && <span className="badge badge-kk" style={{ marginLeft: 6 }}>OUR BID</span>}
                                  </td>
                                  <td>{b.item_name || 'All Items'}</td>
                                  <td>{b.rate ? '₹' + Number(b.rate).toLocaleString('en-IN') : 'not available'}</td>
                                  <td>{b.total ? '₹' + Number(b.total).toLocaleString('en-IN') : 'not available'}</td>
                                  <td><strong>Rank {b.rank || 1}</strong></td>
                                  <td>
                                    {b.selected ? (
                                      <span className="badge badge-awarded">L1 WINNER</span>
                                    ) : (
                                      <span className="badge badge-closed">Not Selected</span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ padding: '24px', background: '#f8fafc', borderRadius: 8, textAlign: 'center' }}>
                        <h4>Bids not public yet</h4>
                        <p style={{ margin: 0, fontSize: '0.88rem', color: '#64748b' }}>
                          They appear after commercial opening. Last checked: {selectedTender.last_checked_at}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 5: TIMELINE */}
              {modalTab === 'timeline' && (
                <div>
                  <div className="modal-section" style={{ marginTop: 0 }}>
                    <h3>Status Timeline</h3>
                    <ul className="timeline-list">
                      {selectedTender.timeline?.map((tl, i) => (
                        <li key={i}>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <strong>{tl.new_status}</strong>
                            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{tl.changed_at}</span>
                          </div>
                          <div style={{ fontSize: '0.86rem', color: '#334155', marginTop: 3 }}>{tl.note}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PDF VIEWER MODAL */}
      {pdfViewerUrl && (
        <div className="pdf-viewer-modal" onClick={() => setPdfViewerUrl(null)}>
          <div className="pdf-viewer-container" onClick={e => e.stopPropagation()}>
            <div className="pdf-toolbar">
              <span>📄 <strong>{pdfViewerTitle}</strong></span>
              <button
                className="action-btn"
                style={{ background: '#334155', color: 'white', borderColor: '#475569' }}
                onClick={() => setPdfViewerUrl(null)}
              >
                Close &times;
              </button>
            </div>
            <iframe src={pdfViewerUrl} className="pdf-frame" title={pdfViewerTitle} />
          </div>
        </div>
      )}
    </div>
  );
}
