export interface TenderDocument {
  file_name: string;
  document_type?: string;
  size?: number;
  size_bytes?: number;
  is_comp?: boolean;
  uuid?: string;
  sha256?: string;
  status?: string;
  verified?: boolean;
  entity_id?: number | string;
}

export interface TenderBid {
  item_name?: string;
  supplier_id?: string | number;
  supplier_name?: string;
  rate?: number | string;
  total?: number | string;
  rank?: number;
  selected?: number | boolean;
}

export interface TenderItem {
  item_code?: string;
  item_name?: string;
  quantity?: string | number;
  unit?: string;
  rate?: string | number;
  total?: string | number;
  our_rate?: number;
  l1_rate?: number;
  l1_name?: string;
  difference?: number;
  specifications?: string;
}

export interface TechnicalParameter {
  parameter_name: string;
  evaluation_method: string;
  requirement: string;
}

export interface StageInfo {
  date: string;
  status: string;
  approver?: string;
}

export interface StageTracker {
  published: StageInfo;
  bid_submission_closed: StageInfo;
  technical_opened: StageInfo;
  commercial_opened: StageInfo;
  awarded: StageInfo;
}

export interface TenderTimeline {
  old_status?: string;
  new_status?: string;
  changed_at?: string;
  note?: string;
}

export interface Tender {
  id?: number;
  tender_number: string;
  tender_id?: number | string;
  nit_id?: number | string;
  department_code?: string | null;
  department_name?: string | null;
  category?: 'GOODS' | 'WORKS' | 'SERVICES' | string | null;
  status?: string | null;
  title?: string | null;
  estimated_value?: number | string | null;
  emd_amount?: number | string | null;
  tender_fee?: number | string | null;
  bid_validity?: number | string | null;
  published_date?: string | null;
  closing_date?: string | null;
  officer_name?: string | null;
  contact_number?: string | null;
  financial_year?: string;
  calendar_year?: string;
  in_scope?: number | boolean;
  we_bid?: boolean;
  our_result?: 'WON_ALL' | 'WON_PART' | 'LOST' | 'PENDING' | 'RETENDERED';
  our_rank?: number;
  bids_state?: 'PRICES_PUBLIC' | 'BIDDERS_ONLY' | 'NOT_PUBLIC' | 'ERROR';
  has_documents?: boolean;
  is_published_today?: boolean;
  is_published_yesterday?: boolean;
  is_newly_discovered_today?: boolean;
  first_seen_at?: string;
  completeness_score?: number;
  present_fields?: string[];
  missing_fields?: string[];
  stage_tracker?: StageTracker;
  documents?: TenderDocument[];
  items?: TenderItem[];
  technical_parameters?: TechnicalParameter[];
  bids?: TenderBid[];
  timeline?: TenderTimeline[];
  last_checked_at?: string;
  updated_at?: string;
}

export interface Department {
  department_code: string;
  department_name: string;
  status: string;
  tender_count: number;
}

export interface FYSummary {
  fy: string;
  participated: number;
  won: number;
  lost: number;
  pending: number;
  total_won_value: number;
}

export interface OtherDeptWin {
  tender_number: string;
  department: string;
  title: string;
  amount: number;
  awarded_date: string;
  contract_created: boolean;
}

export interface NeedsConfirmationBidder {
  supplier_name: string;
  matched_text: string;
  tender_number: string;
  reason: string;
}

export interface ChangeLogEntry {
  tender_number: string;
  change_type: 'STATUS_CHANGE' | 'BIDS_OPENED' | 'L1_CHANGED' | 'AWARDED' | 'NEW_TENDER';
  detail: string;
  timestamp: string;
}

export interface CompanyAnalysis {
  supplier_id: number;
  legal_names: string[];
  debarred_status: 'CLEAN' | 'DEBARRED';
  total_participated: number;
  total_won_tenders: number;
  total_lost_tenders: number;
  total_pending_tenders: number;
  total_won_value: number;
  fy_summaries: FYSummary[];
  tenders: Tender[];
  other_department_wins: OtherDeptWin[];
  needs_confirmation: NeedsConfirmationBidder[];
}

export interface DashboardStats {
  tender_count: number;
  department_count: number;
  my_tenders_count: number;
  total_won_val: number;
  last_successful_scan_date?: string | null;
}

export interface ScanRun {
  id: number;
  source_name: string;
  started_at: string;
  status: string;
  notes?: string;
}

export interface KPPPDataset {
  stats: DashboardStats;
  departments: Department[];
  tenders: Tender[];
  company: CompanyAnalysis;
  scan_runs: ScanRun[];
  changes_since_last_visit: ChangeLogEntry[];
  tender_details: Record<string, Tender>;
  data_source: 'LIVE_KPPP' | 'IMPORTED_FILE';
  last_updated: string;
  next_update_due: string;
}
