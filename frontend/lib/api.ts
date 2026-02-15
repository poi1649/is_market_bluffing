import { AnalyzeRequest, AnalyzeResponse, RunsResponse, TickerSearchResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const SESSION_HEADER = "x-anon-session-id";

async function handleJson<T>(response: Response): Promise<{ data: T; sessionId?: string }> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  const sessionId = response.headers.get(SESSION_HEADER) || undefined;
  const data = (await response.json()) as T;
  return { data, sessionId };
}

export async function analyze(payload: AnalyzeRequest, sessionId: string): Promise<{ data: AnalyzeResponse; sessionId?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      [SESSION_HEADER]: sessionId,
    },
    body: JSON.stringify(payload),
  });

  return handleJson<AnalyzeResponse>(response);
}

export async function fetchRuns(sessionId: string): Promise<{ data: RunsResponse; sessionId?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/runs`, {
    headers: {
      [SESSION_HEADER]: sessionId,
    },
    cache: "no-store",
  });

  return handleJson<RunsResponse>(response);
}

export async function fetchRunById(runId: string, sessionId: string): Promise<{ data: AnalyzeResponse; sessionId?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/runs/${runId}`, {
    headers: {
      [SESSION_HEADER]: sessionId,
    },
    cache: "no-store",
  });

  return handleJson<AnalyzeResponse>(response);
}

export async function searchTickers(query: string): Promise<TickerSearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/tickers/search?q=${encodeURIComponent(query)}`, {
    cache: "no-store",
  });

  const { data } = await handleJson<TickerSearchResponse>(response);
  return data;
}
