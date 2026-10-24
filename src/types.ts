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
}

export interface TenderBid {
  item_name?: string;
  supplier_id?: string;
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

export interface TenderFlag {
  flag_name?: string;
  detail?: string;
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
  in_scope?: number | boolean;
  found_automatically?: number | boolean;
  unknown_to_us?: number | boolean;
  we_bid?: boolean;
  we_won?: boolean;
  we_lost?: boolean;
  has_documents?: boolean;
  new_document?: boolean;
  is_published_today?: boolean;
  is_newly_discovered_today?: boolean;
  is_published_yesterday?: boolean;
  completeness_score?: number;
  present_fields?: string[];
  missing_fields?: string[];
  stage_tracker?: StageTracker;
  documents?: TenderDocument[];
  items?: TenderItem[];
  technical_parameters?: TechnicalParameter[];
  bids?: TenderBid[];
  flags?: TenderFlag[];
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

export interface CompetitorWin {
  name: string;
  times_beat_us: number;
}

export interface LostItemComparison {
  tender_number: string;
  item_name?: string;
  our_rate?: number;
  our_total?: number;
  our_rank?: number;
  winner_name?: string;
  winner_rate?: number;
  winner_total?: number;
}

export interface CompanyAnalysis {
  total_participated: number;
  total_won_tenders: number;
  total_lost_tenders: number;
  total_won_value: number;
  tenders: Array<{
    tender_number: string;
    department_code?: string;
    department_name?: string;
    category?: string;
    status?: string;
    published_date?: string;
    unknown_to_us?: number | boolean;
  }>;
  won_items: Array<{
    tender_number: string;
    item_name?: string;
    rate?: number;
    total?: number;
    rank?: number;
  }>;
  lost_items: LostItemComparison[];
  competitors_who_beat_us: CompetitorWin[];
}

export interface DashboardStats {
  tender_count: number;
  department_count: number;
  my_tenders_count: number;
  unknown_count: number;
  total_won_val: number;
  last_run?: { id: number; started_at: string; status: string } | null;
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
  tender_details: Record<string, Tender>;
}
