export type AnalyzeRequest = {
  tickers: string[];
  lookback_months: number;
  decline_threshold_pct: number;
  min_market_cap_musd: number;
};

export type RecoveryDistribution = {
  p25: number | null;
  median: number | null;
  p75: number | null;
};

export type StockResult = {
  ticker: string;
  decline_pct: number;
  threshold_pct: number;
  beta: number;
  peak_date: string;
  trough_date: string;
  peak_price: number;
  trough_price: number;
  market_cap_musd: number | null;
  recovered: boolean;
  recovery_date: string | null;
  recovery_price: number | null;
  recovery_days: number | null;
  qualifying_events: number;
  recovered_events: number;
};

export type AnalyzeResponse = {
  run_id: string;
  session_id: string;
  generated_at: string;
  params: {
    tickers: string[];
    lookback_months: number;
    decline_threshold_pct: number;
    min_market_cap_musd: number;
    used_default_universe: boolean;
  };
  universe_size: number;
  evaluated_ticker_count: number;
  declined_stock_count: number;
  recovered_stock_count: number;
  stock_bluff_rate_pct: number;
  declined_event_count: number;
  recovered_event_count: number;
  event_bluff_rate_pct: number;
  recovery_days_distribution: RecoveryDistribution;
  declined_stocks: StockResult[];
  recovered_stocks: StockResult[];
};

export type RunSummary = {
  run_id: string;
  created_at: string;
  lookback_months: number;
  decline_threshold_pct: number;
  min_market_cap_musd: number;
  declined_stock_count: number;
  recovered_stock_count: number;
  stock_bluff_rate_pct: number;
};

export type RunsResponse = {
  session_id: string;
  runs: RunSummary[];
};

export type TickerSearchResponse = {
  query: string;
  tickers: string[];
};
