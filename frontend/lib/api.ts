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
  sort: string;
  direction: string;
}

export interface StateSummary {
  state_name: string;
  lgd_state_code: number;
  total_districts: number;
  districts_with_data: number;
  company_count: number;
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

export interface RankingItem {
  lgd_district_code: number;
  district_name: string;
  state_name: string;
  lgd_state_code: number;
  opportunity_score: number;
  rank_national: number | null;
  rank_within_state: number | null;
  rank_ci_low: number | null;
  rank_ci_high: number | null;
  confidence_score: number;
  confidence_band: "High" | "Moderate" | "Low" | "Unknown";
  indicators_used: number;
  indicators_total: number;
}

export interface RankingsResponse {
  items: RankingItem[];
  total: number;
  limit: number;
  offset: number;
  profile_code: string;
  weight_version_id?: number;
  computed: boolean;
}

export interface RankingsMeta {
  active_versions: {
    profile_code: string;
    weight_version_id: number;
    method: string;
    weights: Record<string, number>;
    created_at: string;
  }[];
  scope_note: string;
}

export interface DistrictScorecard {
  geography: DistrictDetail["geography"] & { centroid: { lat: number; lon: number } | null };
  score: {
    opportunity_score: number;
    profile: string;
    rank_national: number | null;
    rank_within_state: number | null;
    rank_ci_low: number | null;
    rank_ci_high: number | null;
    confidence_score: number;
    confidence_band: "High" | "Moderate" | "Low" | "Unknown";
    indicators_used: number;
    indicators_total: number;
    weight_version_id: number;
    computed_at: string;
  } | null;
  pillars?: {
    economic: number | null;
    ecosystem: number | null;
    infrastructure: number | null;
    human_capital: number | null;
  };
  indicators?: {
    code: string;
    name: string;
    raw_value: number | null;
    unit: string;
    normalised_value: number | null;
    contribution: number;
    contribution_method: string;
    is_imputed: boolean;
    is_inherited: boolean;
    source_code: string;
  }[];
  warnings: string[];
}

export function listRankings(
  params: {
    profile?: string;
    state_code?: number;
    q?: string;
    min_score?: number;
    ranked_only?: boolean;
    limit?: number;
    offset?: number;
    sort?: string;
    direction?: string;
  } = {},
) {
  const search = new URLSearchParams();
  if (params.profile) search.set("profile", params.profile);
  if (params.state_code) search.set("state_code", String(params.state_code));
  if (params.q) search.set("q", params.q);
  if (params.min_score !== undefined) search.set("min_score", String(params.min_score));
  search.set("ranked_only", String(params.ranked_only ?? true));
  search.set("limit", String(params.limit ?? 50));
  search.set("offset", String(params.offset ?? 0));
  if (params.sort) search.set("sort", params.sort);
  if (params.direction) search.set("direction", params.direction);
  return getJson<RankingsResponse>(`/api/v1/rankings?${search.toString()}`);
}

export function getRankingsMeta() {
  return getJson<RankingsMeta>("/api/v1/rankings/meta");
}

export function getDistrictScore(lgdDistrictCode: number, profile?: string) {
  const search = profile ? `?profile=${encodeURIComponent(profile)}` : "";
  return getJson<DistrictScorecard>(`/api/v1/districts/${lgdDistrictCode}/score${search}`);
}

export interface PredictiveShap {
  model_version_id: number;
  target_variable: string;
  target_description: string;
  cv_r2: number | null;
  model_quality: string;
  n_train_districts: number;
  trained_at: string;
  base_value: number;
  predicted_value: number;
  contributions: { indicator_code: string; indicator_name: string; feature_value: number | null; shap_value: number }[];
}

export interface DistrictExplain {
  lgd_district_code: number;
  profile: string;
  final_score: number;
  contributions: {
    indicator_code: string;
    indicator_name: string;
    contribution: number;
    contribution_method: string;
    raw_value: number | null;
    is_imputed: boolean;
    is_inherited: boolean;
    source_code: string;
  }[];
  predictive_model: PredictiveShap | null;
  narrative: string | null;
  narrative_available: boolean;
  warnings: string[];
}

export function getDistrictExplain(lgdDistrictCode: number, profile?: string) {
  const search = profile ? `?profile=${encodeURIComponent(profile)}` : "";
  return getJson<DistrictExplain>(`/api/v1/districts/${lgdDistrictCode}/explain${search}`);
}

export interface CounterfactualLever {
  indicator_code: string;
  current_value: number;
  required_value: number;
  required_delta: number;
  feasible: boolean;
  description: string;
}

export interface CounterfactualResult {
  lgd_district_code: number;
  current_rank: number;
  target_rank: number;
  current_score?: number;
  target_score?: number;
  already_achieved: boolean;
  levers: CounterfactualLever[];
  infeasible: string[];
}

export async function getCounterfactual(lgdDistrictCode: number, targetRank: number, profile?: string) {
  const search = new URLSearchParams({ target_rank: String(targetRank) });
  if (profile) search.set("profile", profile);
  const res = await fetch(`${API_BASE}/api/v1/districts/${lgdDistrictCode}/counterfactual?${search.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(body.detail ?? `API counterfactual failed: ${res.status}`);
  }
  return res.json() as Promise<CounterfactualResult>;
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

export function listDistricts(
  params: {
    state_code?: number;
    q?: string;
    limit?: number;
    offset?: number;
    sort?: string;
    direction?: string;
  } = {},
) {
  const search = new URLSearchParams();
  if (params.state_code) search.set("state_code", String(params.state_code));
  if (params.q) search.set("q", params.q);
  search.set("limit", String(params.limit ?? 50));
  search.set("offset", String(params.offset ?? 0));
  if (params.sort) search.set("sort", params.sort);
  if (params.direction) search.set("direction", params.direction);
  return getJson<DistrictListResponse>(`/api/v1/districts?${search.toString()}`);
}

export function getDistrict(lgdDistrictCode: number) {
  return getJson<DistrictDetail>(`/api/v1/districts/${lgdDistrictCode}`);
}

export function listStates() {
  return getJson<{ items: StateSummary[] }>("/api/v1/states").then((r) => r.items);
}
