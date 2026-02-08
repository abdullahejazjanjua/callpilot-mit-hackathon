/**
 * CallPilot — API Service Layer
 * ===============================
 * Centralized API calls to the FastAPI backend.
 */

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Helpers ─────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── Agent ───────────────────────────────────────────────

export async function getSignedUrl(): Promise<string> {
  const data = await request<{ signed_url: string }>("/agent/signed-url");
  return data.signed_url;
}

export async function getAgentInfo() {
  return request<Record<string, unknown>>("/agent/info");
}

// ── Swarm ───────────────────────────────────────────────

export interface SwarmRequest {
  category: string;
  date: string;
  user_location?: string;
  min_rating?: number;
  auto_book?: boolean;
  patient_name?: string;
}

export interface ScoredProvider {
  provider_id: string;
  provider_name: string;
  phone: string;
  address: string;
  rating: number;
  distance_km: number;
  travel_minutes: number;
  best_slot: string;
  compatible_slots: string[];
  call_sid: string;
  score: number;
  score_breakdown: {
    rating_score: number;
    distance_score: number;
    time_score: number;
  };
}

export interface SwarmResult {
  success: boolean;
  message: string;
  ranked_providers: ScoredProvider[];
  best_match: ScoredProvider | null;
  booking: Record<string, unknown> | null;
  calls_made: number;
  analysis: {
    providers_found: number;
    calls_made: number;
    providers_with_slots: number;
    providers_compatible: number;
    providers_skipped_no_slots: number;
    providers_skipped_conflicts: number;
    calendar_conflicts: number;
    best_match: {
      name: string;
      score: number;
      why: string;
    };
  };
  decision_trail: Array<Record<string, unknown>>;
}

export async function runSwarm(params: SwarmRequest): Promise<SwarmResult> {
  return request<SwarmResult>("/swarm/schedule", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ── Health ──────────────────────────────────────────────

export async function healthCheck() {
  return request<{ status: string }>("/health");
}

// ── SSE URL ─────────────────────────────────────────────

export function getEventStreamUrl(): string {
  return `${API_URL}/events/stream`;
}
