"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";

import { analyze, fetchRunById, fetchRuns, searchTickers } from "../lib/api";
import { getOrCreateSessionId, saveSessionId } from "../lib/session";
import { AnalyzeResponse, RunSummary } from "../lib/types";

type FormState = {
  lookbackMonths: number;
  declineThresholdPct: number;
  minMarketCapMusd: number;
};

const initialForm: FormState = {
  lookbackMonths: 6,
  declineThresholdPct: 20,
  minMarketCapMusd: 300,
};

function normalizeTicker(value: string): string {
  return value.trim().toUpperCase().replace(/\./g, "-");
}

function formatPrice(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return `${value.toFixed(2)}%`;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  return value;
}

function formatDays(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "-";
  }
  return `${Math.round(value)}일`;
}

function rateLabel(rate: number): string {
  if (rate >= 70) {
    return "블러프 강함";
  }
  if (rate >= 40) {
    return "중립 구간";
  }
  return "실제 악재 우세";
}

function rateTone(rate: number): "high" | "mid" | "low" {
  if (rate >= 70) {
    return "high";
  }
  if (rate >= 40) {
    return "mid";
  }
  return "low";
}

export default function Page() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [tickerInput, setTickerInput] = useState<string>("");
  const [tickerSuggestions, setTickerSuggestions] = useState<string[]>([]);
  const [tickerSuggestLoading, setTickerSuggestLoading] = useState(false);

  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [sessionId, setSessionId] = useState<string>("");

  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const sid = getOrCreateSessionId();
    setSessionId(sid);

    setHistoryLoading(true);
    fetchRuns(sid)
      .then(({ data, sessionId: responseSessionId }) => {
        if (responseSessionId) {
          setSessionId(responseSessionId);
          saveSessionId(responseSessionId);
        }
        setRuns(data.runs);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load run history");
      })
      .finally(() => {
        setHistoryLoading(false);
      });
  }, []);

  useEffect(() => {
    const query = normalizeTicker(tickerInput);
    if (!query) {
      setTickerSuggestions([]);
      setTickerSuggestLoading(false);
      return;
    }

    let cancelled = false;
    setTickerSuggestLoading(true);

    const timer = window.setTimeout(() => {
      searchTickers(query)
        .then((data) => {
          if (cancelled) {
            return;
          }

          const options = data.tickers.filter((ticker) => !selectedTickers.includes(ticker)).slice(0, 8);
          setTickerSuggestions(options);
        })
        .catch(() => {
          if (!cancelled) {
            setTickerSuggestions([]);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setTickerSuggestLoading(false);
          }
        });
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [tickerInput, selectedTickers]);

  const universeLabel = useMemo(() => {
    if (!result) {
      return "-";
    }

    return result.params.used_default_universe ? "S&P 500 기본 유니버스" : "사용자 선택 종목";
  }, [result]);

  const declineTitle = useMemo(() => {
    if (!result) {
      return "m% 이상 하락 종목";
    }
    return `${result.params.decline_threshold_pct}% 이상 하락 종목`;
  }, [result]);

  const tone = useMemo(() => {
    if (!result) {
      return "mid" as const;
    }
    return rateTone(result.stock_bluff_rate_pct);
  }, [result]);

  const recoveryBars = useMemo(() => {
    if (!result) {
      return [] as { key: string; value: number | null; widthPct: number }[];
    }

    const rows = [
      { key: "P25", value: result.recovery_days_distribution.p25 },
      { key: "Median", value: result.recovery_days_distribution.median },
      { key: "P75", value: result.recovery_days_distribution.p75 },
    ];

    const max = Math.max(
      ...rows.map((item) => (typeof item.value === "number" ? item.value : 0)),
      1,
    );

    return rows.map((item) => ({
      ...item,
      widthPct: typeof item.value === "number" ? Math.max(6, (item.value / max) * 100) : 0,
    }));
  }, [result]);

  async function refreshRuns(targetSessionId: string) {
    const { data, sessionId: responseSessionId } = await fetchRuns(targetSessionId);
    if (responseSessionId) {
      setSessionId(responseSessionId);
      saveSessionId(responseSessionId);
    }
    setRuns(data.runs);
  }

  function addTicker(rawValue: string) {
    const ticker = normalizeTicker(rawValue);
    if (!ticker) {
      return;
    }

    setSelectedTickers((prev) => {
      if (prev.includes(ticker)) {
        return prev;
      }
      return [...prev, ticker];
    });
  }

  function removeTicker(ticker: string) {
    setSelectedTickers((prev) => prev.filter((item) => item !== ticker));
  }

  function addFromInput() {
    const query = normalizeTicker(tickerInput);
    if (!query) {
      return;
    }

    const firstSuggestion = tickerSuggestions.find((ticker) => ticker.startsWith(query));
    addTicker(firstSuggestion ?? query);

    setTickerInput("");
    setTickerSuggestions([]);
  }

  function onTickerInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addFromInput();
      return;
    }

    if (event.key === "Backspace" && !tickerInput.trim() && selectedTickers.length > 0) {
      setSelectedTickers((prev) => prev.slice(0, -1));
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setLoading(true);
    setError("");
    try {
      const sid = sessionId || getOrCreateSessionId();
      const payload = {
        tickers: selectedTickers,
        lookback_months: form.lookbackMonths,
        decline_threshold_pct: form.declineThresholdPct,
        min_market_cap_musd: form.minMarketCapMusd,
      };

      const { data, sessionId: responseSessionId } = await analyze(payload, sid);
      setResult(data);

      const nextSessionId = responseSessionId || sid;
      if (nextSessionId) {
        setSessionId(nextSessionId);
        saveSessionId(nextSessionId);
      }

      await refreshRuns(nextSessionId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analyze request failed");
    } finally {
      setLoading(false);
    }
  }

  async function onOpenRun(runId: string) {
    if (!sessionId) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const { data, sessionId: responseSessionId } = await fetchRunById(runId, sessionId);
      setResult(data);
      setSelectedTickers(data.params.tickers ?? []);
      setTickerInput("");
      setTickerSuggestions([]);
      setForm({
        lookbackMonths: data.params.lookback_months,
        declineThresholdPct: data.params.decline_threshold_pct,
        minMarketCapMusd: data.params.min_market_cap_musd,
      });

      if (responseSessionId) {
        setSessionId(responseSessionId);
        saveSessionId(responseSessionId);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load run detail");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="panel hero-panel">
        <div className="hero-top">
          <div>
            <p className="eyebrow">Market Bluff Monitor</p>
            <h1>시장 과민반응 회복 확률 대시보드</h1>
            <p className="subtitle">
              n개월 내 고점 대비 하락 후 회복 패턴을 집계해, 하락이 실제 악재인지 블러프인지 확률로 보여줍니다.
            </p>
          </div>
          <div className="hero-tags" aria-label="analysis assumptions">
            <span>High/Low 기준</span>
            <span>Beta x m 임계치</span>
            <span>회복 판정: 현재까지</span>
          </div>
        </div>

        {result && (
          <div className="hero-kpi-strip">
            <article>
              <p>종목 기준 블러프율</p>
              <strong>{formatPercent(result.stock_bluff_rate_pct)}</strong>
            </article>
            <article>
              <p>이벤트 기준 블러프율</p>
              <strong>{formatPercent(result.event_bluff_rate_pct)}</strong>
            </article>
            <article>
              <p>평가 종목 수</p>
              <strong>{result.evaluated_ticker_count.toLocaleString("en-US")}</strong>
            </article>
            <article>
              <p>중앙 회복일수</p>
              <strong>{formatDays(result.recovery_days_distribution.median)}</strong>
            </article>
          </div>
        )}
      </section>

      <section className="workspace-grid">
        <aside className="sidebar-stack">
          <section className="panel controls-panel">
            <div className="section-head">
              <h2>분석 조건</h2>
              <p>티커를 비우면 S&P 500 기본 300종목이 사용됩니다.</p>
            </div>

            <form onSubmit={onSubmit} className="form-stack">
              <label className="field-group">
                <span className="field-label">티커 선택</span>

                <div className="ticker-chip-list">
                  {selectedTickers.map((ticker) => (
                    <span className="ticker-chip" key={ticker}>
                      {ticker}
                      <button type="button" className="chip-remove" onClick={() => removeTicker(ticker)} aria-label={`${ticker} 삭제`}>
                        ×
                      </button>
                    </span>
                  ))}
                  {!selectedTickers.length && <span className="chip-placeholder">선택된 티커 없음 (기본 300종목)</span>}
                </div>

                <div className="ticker-input-row">
                  <input
                    type="text"
                    value={tickerInput}
                    onChange={(event) => setTickerInput(event.target.value)}
                    onKeyDown={onTickerInputKeyDown}
                    placeholder="티커 입력 후 Enter"
                  />
                  <button type="button" className="secondary-button" onClick={addFromInput}>
                    추가
                  </button>
                  {!!selectedTickers.length && (
                    <button type="button" className="ghost-button" onClick={() => setSelectedTickers([])}>
                      전체 삭제
                    </button>
                  )}
                </div>

                {(tickerSuggestLoading || tickerSuggestions.length > 0) && (
                  <div className="ticker-suggestions">
                    {tickerSuggestLoading && <span className="suggest-empty">검색 중...</span>}
                    {!tickerSuggestLoading &&
                      tickerSuggestions.map((ticker) => (
                        <button
                          type="button"
                          className="suggest-item"
                          key={ticker}
                          onClick={() => {
                            addTicker(ticker);
                            setTickerInput("");
                            setTickerSuggestions([]);
                          }}
                        >
                          {ticker}
                        </button>
                      ))}
                  </div>
                )}
              </label>

              <div className="number-fields-grid">
                <label className="field-group">
                  <span className="field-label">관측 기간 n (개월)</span>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={form.lookbackMonths}
                    onChange={(event) => setForm((prev) => ({ ...prev, lookbackMonths: Number(event.target.value) }))}
                  />
                </label>

                <label className="field-group">
                  <span className="field-label">기준 하락률 m (%)</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    step={0.1}
                    value={form.declineThresholdPct}
                    onChange={(event) => setForm((prev) => ({ ...prev, declineThresholdPct: Number(event.target.value) }))}
                  />
                </label>

                <label className="field-group">
                  <span className="field-label">최소 시가총액 i (백만$)</span>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={form.minMarketCapMusd}
                    onChange={(event) => setForm((prev) => ({ ...prev, minMarketCapMusd: Number(event.target.value) }))}
                  />
                </label>
              </div>

              <button type="submit" className="primary-button" disabled={loading}>
                {loading ? "분석 중..." : "분석 실행"}
              </button>
            </form>
          </section>

          <section className="panel history-panel">
            <div className="section-head inline">
              <h2>세션 실행 이력</h2>
              <span>{historyLoading ? "불러오는 중..." : `${runs.length}건`}</span>
            </div>
            <div className="history-list">
              {runs.map((run) => (
                <button key={run.run_id} className="history-item" onClick={() => onOpenRun(run.run_id)}>
                  <strong>{new Date(run.created_at).toLocaleString()}</strong>
                  <span>
                    n={run.lookback_months}, m={run.decline_threshold_pct}%, i={run.min_market_cap_musd}M
                  </span>
                  <span>
                    종목 블러프율 {run.stock_bluff_rate_pct.toFixed(2)}% ({run.recovered_stock_count}/{run.declined_stock_count})
                  </span>
                </button>
              ))}
              {!runs.length && <p className="empty">아직 실행 이력이 없습니다.</p>}
            </div>
          </section>
        </aside>

        <section className="content-stack">
          {error && (
            <section className="panel alert-panel alert-error">
              <p>{error}</p>
            </section>
          )}

          {result && result.failed_ticker_count > 0 && (
            <section className="panel alert-panel alert-warn">
              <p>
                데이터 조회 실패 티커 {result.failed_ticker_count}개는 제외하고 계산했습니다: {result.failed_tickers.join(", ")}
              </p>
            </section>
          )}

          {!result && (
            <section className="panel placeholder-panel">
              <h2>결과 대시보드</h2>
              <p>
                분석을 실행하면 블러프율, 회복 분포, {declineTitle}, 회복 완료 종목 리스트가 순서대로 표시됩니다.
              </p>
            </section>
          )}

          {result && (
            <>
              <section className={`panel outcome-panel tone-panel-${tone}`}>
                <div className="outcome-head">
                  <div>
                    <h2>시장 블러프 신호</h2>
                    <p className="meta-line">
                      유니버스: {universeLabel} | 전체 {result.universe_size}종목 중 {result.evaluated_ticker_count}종목 평가
                    </p>
                  </div>
                  <span className={`tone-badge tone-badge-${tone}`}>{rateLabel(result.stock_bluff_rate_pct)}</span>
                </div>

                <div className="bluff-meter">
                  <div className="meter-track">
                    <div className="meter-fill" style={{ width: `${Math.min(100, Math.max(0, result.stock_bluff_rate_pct))}%` }} />
                  </div>
                  <div className="meter-scale">
                    <span>0%</span>
                    <strong>{formatPercent(result.stock_bluff_rate_pct)}</strong>
                    <span>100%</span>
                  </div>
                </div>

                <div className="metric-grid">
                  <article>
                    <p>종목 기준</p>
                    <strong>
                      {result.recovered_stock_count} / {result.declined_stock_count}
                    </strong>
                    <span>{formatPercent(result.stock_bluff_rate_pct)}</span>
                  </article>
                  <article>
                    <p>이벤트 기준</p>
                    <strong>
                      {result.recovered_event_count} / {result.declined_event_count}
                    </strong>
                    <span>{formatPercent(result.event_bluff_rate_pct)}</span>
                  </article>
                  <article>
                    <p>회복일수 분위수</p>
                    <strong>
                      P25 {result.recovery_days_distribution.p25 ?? "-"} / Median {result.recovery_days_distribution.median ?? "-"} /
                      P75 {result.recovery_days_distribution.p75 ?? "-"}
                    </strong>
                    <span>단위: 거래일</span>
                  </article>
                </div>
              </section>

              <section className="panel distribution-panel">
                <div className="section-head inline">
                  <h2>회복일수 분포</h2>
                  <span>숫자 상대비로 표시</span>
                </div>
                <div className="distribution-bars">
                  {recoveryBars.map((item) => (
                    <div key={item.key} className="bar-row">
                      <span>{item.key}</span>
                      <div className="bar-track">
                        <div className="bar-fill" style={{ width: `${item.widthPct}%` }} />
                      </div>
                      <strong>{item.value ?? "-"}</strong>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel table-panel">
                <div className="section-head inline">
                  <h2>{declineTitle}</h2>
                  <span>{result.declined_stocks.length}개 종목</span>
                </div>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>티커</th>
                        <th>기간내 최고가</th>
                        <th>최고가대비 하락률</th>
                        <th>하락 종료일</th>
                        <th>하락 종료가</th>
                        <th>회복 종료일</th>
                        <th>회복 종료가</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.declined_stocks.map((stock) => (
                        <tr key={stock.ticker}>
                          <td className="ticker-col">{stock.ticker}</td>
                          <td className="mono">{formatPrice(stock.peak_price)}</td>
                          <td className="mono decline-col">{formatPercent(stock.decline_pct)}</td>
                          <td className="mono">{formatDate(stock.trough_date)}</td>
                          <td className="mono">{formatPrice(stock.trough_price)}</td>
                          <td className="mono">{formatDate(stock.recovery_date)}</td>
                          <td className="mono">{formatPrice(stock.recovery_price)}</td>
                        </tr>
                      ))}
                      {!result.declined_stocks.length && (
                        <tr>
                          <td colSpan={7} className="empty-row">
                            조건을 만족한 종목이 없습니다.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="panel table-panel">
                <div className="section-head inline">
                  <h2>회복 완료 종목</h2>
                  <span>{result.recovered_stocks.length}개 종목</span>
                </div>
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>티커</th>
                        <th>기간내 최고가</th>
                        <th>최고가대비 하락률</th>
                        <th>하락 종료일</th>
                        <th>하락 종료가</th>
                        <th>회복 종료일</th>
                        <th>회복 종료가</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.recovered_stocks.map((stock) => (
                        <tr key={`${stock.ticker}-recovered`}>
                          <td className="ticker-col">{stock.ticker}</td>
                          <td className="mono">{formatPrice(stock.peak_price)}</td>
                          <td className="mono decline-col">{formatPercent(stock.decline_pct)}</td>
                          <td className="mono">{formatDate(stock.trough_date)}</td>
                          <td className="mono">{formatPrice(stock.trough_price)}</td>
                          <td className="mono">{formatDate(stock.recovery_date)}</td>
                          <td className="mono">{formatPrice(stock.recovery_price)}</td>
                        </tr>
                      ))}
                      {!result.recovered_stocks.length && (
                        <tr>
                          <td colSpan={7} className="empty-row">
                            회복 완료 종목이 없습니다.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </section>
      </section>
    </main>
  );
}
