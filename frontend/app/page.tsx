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
  minMarketCapMusd: 0,
};

function normalizeTicker(value: string): string {
  return value.trim().toUpperCase().replace(/\./g, "-");
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
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Market Bluff Monitor</p>
        <h1>악재 과민반응 회복 확률 대시보드</h1>
        <p className="subtitle">
          선택한 미국 상장 종목에서 n개월 내 급락(베타 반영 임계치) 후 이전 가격 복귀 빈도를 계산합니다.
        </p>
      </section>

      <section className="panel form-panel">
        <h2>분석 조건</h2>
        <form onSubmit={onSubmit} className="form-grid">
          <label>
            티커 선택 (비우면 기본 300종목)
            <div className="ticker-chip-list">
              {selectedTickers.map((ticker) => (
                <span className="ticker-chip" key={ticker}>
                  {ticker}
                  <button type="button" className="chip-remove" onClick={() => removeTicker(ticker)} aria-label={`${ticker} 삭제`}>
                    ×
                  </button>
                </span>
              ))}
              {!selectedTickers.length && <span className="chip-placeholder">선택된 티커 없음 (기본 300종목 사용)</span>}
            </div>

            <div className="ticker-input-row">
              <input
                type="text"
                value={tickerInput}
                onChange={(event) => setTickerInput(event.target.value)}
                onKeyDown={onTickerInputKeyDown}
                placeholder="티커 입력 후 Enter 또는 ,"
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

          <label>
            관측 기간 n (개월)
            <input
              type="number"
              min={1}
              max={60}
              value={form.lookbackMonths}
              onChange={(event) => setForm((prev) => ({ ...prev, lookbackMonths: Number(event.target.value) }))}
            />
          </label>

          <label>
            기준 하락률 m (%)
            <input
              type="number"
              min={1}
              max={100}
              step={0.1}
              value={form.declineThresholdPct}
              onChange={(event) => setForm((prev) => ({ ...prev, declineThresholdPct: Number(event.target.value) }))}
            />
          </label>

          <label>
            최소 시가총액 i (백만 달러)
            <input
              type="number"
              min={0}
              step={1}
              value={form.minMarketCapMusd}
              onChange={(event) => setForm((prev) => ({ ...prev, minMarketCapMusd: Number(event.target.value) }))}
            />
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "분석 중..." : "분석 실행"}
          </button>
        </form>
      </section>

      {error && (
        <section className="panel error-panel">
          <p>{error}</p>
        </section>
      )}

      {result && result.failed_ticker_count > 0 && (
        <section className="panel error-panel">
          <p>
            데이터 조회 실패 티커 {result.failed_ticker_count}개는 제외하고 계산했습니다:{" "}
            {result.failed_tickers.join(", ")}
          </p>
        </section>
      )}

      <section className="panel history-panel">
        <div className="history-head">
          <h2>세션 실행 이력</h2>
          <span>{historyLoading ? "불러오는 중..." : `${runs.length}건`}</span>
        </div>
        <div className="history-list">
          {runs.map((run) => (
            <button key={run.run_id} className="history-item" onClick={() => onOpenRun(run.run_id)}>
              <strong>{new Date(run.created_at).toLocaleString()}</strong>
              <span>
                n={run.lookback_months}, m={run.decline_threshold_pct}% , i={run.min_market_cap_musd}M
              </span>
              <span>
                종목 블러프율 {run.stock_bluff_rate_pct.toFixed(2)}% ({run.recovered_stock_count}/{run.declined_stock_count})
              </span>
            </button>
          ))}
          {!runs.length && <p className="empty">아직 실행 이력이 없습니다.</p>}
        </div>
      </section>

      {result && (
        <>
          <section className="panel metrics-panel">
            <h2>결과 요약</h2>
            <p className="meta">
              유니버스: {universeLabel} | 전체 {result.universe_size}종목 중 {result.evaluated_ticker_count}종목 평가
            </p>
            <div className="metric-grid">
              <article>
                <p>종목 기준 블러프율</p>
                <strong>{result.stock_bluff_rate_pct.toFixed(2)}%</strong>
                <span>
                  {result.recovered_stock_count} / {result.declined_stock_count}
                </span>
              </article>
              <article>
                <p>이벤트 기준 블러프율</p>
                <strong>{result.event_bluff_rate_pct.toFixed(2)}%</strong>
                <span>
                  {result.recovered_event_count} / {result.declined_event_count}
                </span>
              </article>
              <article>
                <p>회복일수 분위수</p>
                <strong>
                  P25 {result.recovery_days_distribution.p25 ?? "-"} / Median {result.recovery_days_distribution.median ?? "-"} /
                  P75 {result.recovery_days_distribution.p75 ?? "-"}
                </strong>
                <span>단위: 일</span>
              </article>
            </div>
          </section>

          <section className="panel distribution-panel">
            <h2>회복일수 분포</h2>
            <div className="distribution-bars">
              {[
                { key: "P25", value: result.recovery_days_distribution.p25 },
                { key: "Median", value: result.recovery_days_distribution.median },
                { key: "P75", value: result.recovery_days_distribution.p75 },
              ].map((item) => {
                const bar = typeof item.value === "number" ? Math.min(100, item.value) : 0;
                return (
                  <div key={item.key} className="bar-row">
                    <span>{item.key}</span>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${bar}%` }} />
                    </div>
                    <strong>{item.value ?? "-"}</strong>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="panel table-panel">
            <h2>{declineTitle}</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>티커</th>
                    <th>기간내 최고가</th>
                    <th>최고가대비 하락률(%)</th>
                    <th>하락 종료일</th>
                    <th>하락 종료가</th>
                    <th>회복 종료일</th>
                    <th>회복 종료가</th>
                  </tr>
                </thead>
                <tbody>
                  {result.declined_stocks.map((stock) => (
                    <tr key={stock.ticker}>
                      <td>{stock.ticker}</td>
                      <td>{stock.peak_price.toFixed(2)}</td>
                      <td>{stock.decline_pct.toFixed(2)}</td>
                      <td>{stock.trough_date}</td>
                      <td>{stock.trough_price.toFixed(2)}</td>
                      <td>{stock.recovery_date ?? "-"}</td>
                      <td>{stock.recovery_price !== null ? stock.recovery_price.toFixed(2) : "-"}</td>
                    </tr>
                  ))}
                  {!result.declined_stocks.length && (
                    <tr>
                      <td colSpan={7}>조건을 만족한 종목이 없습니다.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel table-panel">
            <h2>회복 완료 종목</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>티커</th>
                    <th>기간내 최고가</th>
                    <th>최고가대비 하락률(%)</th>
                    <th>하락 종료일</th>
                    <th>하락 종료가</th>
                    <th>회복 종료일</th>
                    <th>회복 종료가</th>
                  </tr>
                </thead>
                <tbody>
                  {result.recovered_stocks.map((stock) => (
                    <tr key={`${stock.ticker}-recovered`}>
                      <td>{stock.ticker}</td>
                      <td>{stock.peak_price.toFixed(2)}</td>
                      <td>{stock.decline_pct.toFixed(2)}</td>
                      <td>{stock.trough_date}</td>
                      <td>{stock.trough_price.toFixed(2)}</td>
                      <td>{stock.recovery_date ?? "-"}</td>
                      <td>{stock.recovery_price !== null ? stock.recovery_price.toFixed(2) : "-"}</td>
                    </tr>
                  ))}
                  {!result.recovered_stocks.length && (
                    <tr>
                      <td colSpan={7}>회복 완료 종목이 없습니다.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
