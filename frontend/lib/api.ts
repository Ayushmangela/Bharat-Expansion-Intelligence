const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Overview {
  total_companies: number;
  states_covered: number;
  total_districts: number;
  districts_with_data: number;
  quarantined_rows: number;
  top_districts_by_company_count: { district_name: string; state_name: string; company_count: number }[];
  recent_ingestion_runs: {
    source: string;
    status: string;
    rows_fetched: number | null;
    rows_loaded: number | null;
    rows_quarantined: number | null;
    started_at: string;
  }[];
}

export interface DistrictListItem {
  lgd_district_code: number;
  district_name: string;
  state_name: string;
  lgd_state_code: number;
  company_count: number;
  active_company_count: number;
  msme_micro: number | null;
  msme_small: number | null;
  msme_medium: number | null;
  msme_manufacturing: number | null;
  msme_services: number | null;
}

export interface DistrictListResponse {
  items: DistrictListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DistrictDetail {
  geography: {
    lgd_district_code: number;
    district_name: string;
    state_name: string;
    lgd_state_code: number;
    area_sq_km: number | null;
  };
  company_status_breakdown: { status: string; count: number }[];
  msme: {
    micro: number;
    small: number;
    medium: number;
    manufacturing: number;
    services: number;
  } | null;
  monthly_incorporations: { month: string; count: number }[];
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json();
}

export function getOverview() {
  return getJson<Overview>("/api/v1/overview");
}

export function listDistricts(params: { state_code?: number; q?: string; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.state_code) search.set("state_code", String(params.state_code));
  if (params.q) search.set("q", params.q);
  search.set("limit", String(params.limit ?? 50));
  search.set("offset", String(params.offset ?? 0));
  return getJson<DistrictListResponse>(`/api/v1/districts?${search.toString()}`);
}

export function getDistrict(lgdDistrictCode: number) {
  return getJson<DistrictDetail>(`/api/v1/districts/${lgdDistrictCode}`);
}
