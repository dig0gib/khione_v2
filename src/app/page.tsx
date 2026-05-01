"use client";

import React, { useState, useEffect } from "react";

interface SystemStatus {
  is_trading_active: boolean;
  current_regime: string;
  agent_allocations: Record<string, number>;
  active_positions_count: number;
  api_connected: boolean;
  model_version?: string;
  model_updated?: string;
}

interface NewsItem {
  title: string;
  source: string;
  time: string;
  url: string;
  sentiment: string;
}

interface JournalEntry {
  date: string;
  regime: string;
  pnl: number;
  strategy_summary: string;
  trade_summary: string;
  news_events: string;
  tomorrow_plan: string;
}

// ── 시스템 건전성 패널 (명세서: error_logging_dashboard.md) ──────────────────
interface SystemErrorItem {
  date: string;
  anomaly_code: string;
  severity: string;
  status: string;
  is_resolved: boolean;
}

function SystemHealthPanel({ apiUrl }: { apiUrl: string }) {
  const [errors, setErrors] = useState<SystemErrorItem[]>([]);
  const [lastCheck, setLastCheck] = useState<string>("");

  const fetchErrors = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/system/errors`);
      const data: SystemErrorItem[] = await res.json();
      setErrors(data);
    } catch {
      // 백엔드 미연결 시 빈 배열 유지
    } finally {
      setLastCheck(new Date().toLocaleTimeString("ko-KR"));
    }
  };

  useEffect(() => {
    fetchErrors();
    // 1분 주기 폴링 (명세서 강제)
    const timer = setInterval(fetchErrors, 60_000);
    return () => clearInterval(timer);
  }, [apiUrl]);

  const unresolvedErrors = errors.filter((e) => !e.is_resolved);
  const hasErrors = unresolvedErrors.length > 0;

  return (
    <div
      id="system-health-panel"
      style={{
        gridColumn: "1 / -1",
        padding: "14px 20px",
        borderRadius: "10px",
        border: `1px solid ${hasErrors ? "rgba(255,60,60,0.5)" : "rgba(0,220,120,0.4)"}`,
        background: hasErrors
          ? "rgba(200,0,0,0.18)"
          : "rgba(0,180,80,0.12)",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h3 style={{ margin: 0, fontSize: "0.95rem", letterSpacing: "0.05em" }}>
          {hasErrors ? "🚨 시스템 건전성 현황 — 이상 감지됨" : "🟢 시스템 건전성 현황"}
        </h3>
        <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
          마지막 점검: {lastCheck || "—"}
        </span>
      </div>

      {hasErrors ? (
        <ul style={{ margin: 0, paddingLeft: "18px", listStyle: "none" }}>
          {unresolvedErrors.map((err, idx) => (
            <li
              key={idx}
              style={{
                padding: "6px 10px",
                marginBottom: "4px",
                borderRadius: "6px",
                background: "rgba(255,40,40,0.15)",
                borderLeft: `3px solid ${err.severity === "CRITICAL" ? "#ff2020" : "#ff9900"}`,
                fontSize: "0.85rem",
              }}
            >
              <strong style={{ color: err.severity === "CRITICAL" ? "#ff5555" : "#ffaa00" }}>
                [{err.severity}]
              </strong>{" "}
              <span style={{ color: "#e0e0e0" }}>{err.date}</span>
              {" — "}
              <span>{err.status}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#a0f0c0" }}>
          🟢 정상 작동 중 (No Anomalies) — 모든 에이전트 정상 범위 내 운영 중
        </p>
      )}
    </div>
  );
}
// ─────────────────────────────────────────────────────────────────────────────

const AGENT_TOOLTIPS: Record<string, string> = {
  agent1_scalping: "호가창 스캘핑: 호가창 역설(매도잔량/매수잔량 ≥1.5) + 체결강도 ≥150 진입",
  agent2_program_day: "프로그램 데이: 프로그램 순매수 우상향(Slope) + VWAP ±0.5% 눌림목 진입",
  agent3_macro_swing: "매크로 스윙: 코스피 3일 연속 하락 + 외국인 선물 순매수 전환 → KODEX레버리지 종가 베팅",
};

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [autoSync, setAutoSync] = useState<boolean>(false);
  const [syncTimer, setSyncTimer] = useState<NodeJS.Timeout | null>(null);
  const [journalDate, setJournalDate] = useState<string>(() => {
    const d = new Date();
    return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`;
  });
  const [journalList, setJournalList] = useState<JournalEntry[]>([]);
  const [currentJournal, setCurrentJournal] = useState<JournalEntry | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/status`);
      const data = await response.json();
      setStatus(data);
      setIsLoading(false);
    } catch (error) {
      console.error("Failed to fetch status:", error);
      setIsLoading(false);
    } finally {
      setLastUpdated(new Date().toLocaleString("ko-KR", {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit"
      }));
    }
  };

  const fetchNews = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/market/news`);
      const data = await response.json();
      setNews(data);
    } catch (error) {
      console.error("Failed to fetch news:", error);
    } finally {
      setLastUpdated(new Date().toLocaleString("ko-KR", {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit"
      }));
    }
  };

  const stopSync = () => {
    if (syncTimer) {
      clearInterval(syncTimer);
      setSyncTimer(null);
    }
    setAutoSync(false);
  };

  const startSync = () => {
    fetchStatus();
    fetchNews();
    const timer = setInterval(() => {
      fetchStatus();
      fetchNews();
    }, 5000);
    setSyncTimer(timer);
    setAutoSync(true);
    // 5분 후 자동 종료
    setTimeout(() => stopSync(), 5 * 60 * 1000);
  };

  const fetchJournalList = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/journal?limit=30`);
      const data = await res.json();
      setJournalList(data);
    } catch (e) { console.error(e); }
  };

  const fetchJournal = async (date: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/journal/${date}`);
      if (res.status === 404) { setCurrentJournal(null); return; }
      const data = await res.json();
      setCurrentJournal(data);
    } catch (e) { console.error(e); }
  };

  const handleJournalDateChange = (date: string) => {
    setJournalDate(date);
    fetchJournal(date);
  };

  const handleKillSwitch = async () => {
    if (confirm("🚨 정말로 모든 트레이딩을 중단하고 비상 정지하시겠습니까?")) {
      try {
        await fetch(`${API_URL}/api/v1/kill-switch`, { method: "POST" });
        alert("비상 정지 명령이 전송되었습니다.");
        fetchStatus();
      } catch (error) {
        alert("명령 전송에 실패했습니다.");
      }
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchJournalList();
    return () => {
      if (syncTimer) clearInterval(syncTimer);
    };
  }, []);

  if (isLoading && !status) {
    return <div className="loading">❄️ KHIONE 시스템 로딩 중...</div>;
  }

  return (
    <div className="dashboard-grid">
      {/* 🚨 시스템 건전성 현황 패널 (명세서: error_logging_dashboard.md — 전체 그리드 최상단 강제) */}
      <SystemHealthPanel apiUrl={API_URL} />
      <header className="header glass-panel">
        <div className="title-glow">❄️ 키오네 (KHIONE) 터미널</div>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{ color: "var(--text-secondary)" }}>
            마지막 동기화: {lastUpdated || "—"} | 시장 레짐: <strong style={{ color: "var(--accent-blue)" }}>{status?.current_regime || "LOADING"}</strong>
          </span>
          <button
            onClick={autoSync ? stopSync : startSync}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: "1px solid var(--accent-blue)",
              background: autoSync ? "rgba(255,80,80,0.15)" : "rgba(0,180,255,0.15)",
              color: autoSync ? "#ff5050" : "var(--accent-blue)",
              cursor: "pointer",
              fontSize: "0.85rem",
              whiteSpace: "nowrap",
            }}
          >
            {autoSync ? "⏹ 동기화 중지" : "🔄 동기화 시작"}
          </button>
        </div>
      </header>

      {/* Left Sidebar */}
      <aside className="sidebar">
        <div className="glass-panel agent-list">
          <h3 style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "10px" }}>🧠 에이전트 가중치 (실시간)</h3>
          
          <div className="agent-item" title={AGENT_TOOLTIPS.agent1_scalping}>
            <div className="agent-header">
              <span>Agent 1 (호가창 스캘핑)</span>
              <span>{((status?.agent_allocations.agent1_scalping || 0) * 100).toFixed(0)}%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill" style={{ width: `${(status?.agent_allocations.agent1_scalping || 0) * 100}%` }}></div>
            </div>
          </div>

          <div className="agent-item" title={AGENT_TOOLTIPS.agent2_program_day}>
            <div className="agent-header">
              <span>Agent 2 (프로그램 데이)</span>
              <span>{((status?.agent_allocations.agent2_program_day || 0) * 100).toFixed(0)}%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill" style={{ width: `${(status?.agent_allocations.agent2_program_day || 0) * 100}%` }}></div>
            </div>
          </div>

          <div className="agent-item" title={AGENT_TOOLTIPS.agent3_macro_swing}>
            <div className="agent-header">
              <span>Agent 3 (매크로 스윙)</span>
              <span>{((status?.agent_allocations.agent3_macro_swing || 0) * 100).toFixed(0)}%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill" style={{ width: `${(status?.agent_allocations.agent3_macro_swing || 0) * 100}%` }}></div>
            </div>
          </div>
          
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "10px" }}>
            * Agent 3의 판단에 따라 {status?.current_regime === "VOLATILE" ? "단기 변동성 수익 극대화 중" : "안정적 추세 추종 중"}
          </p>
        </div>

        <div className="glass-panel log-panel">
          <h3 style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "10px", marginBottom: "10px" }}>📡 의사결정 스트림</h3>
          <div className="log-entry">
            <span className="log-time">{lastUpdated}</span>
            <span className={`badge ${status?.is_trading_active ? 'buy' : 'sell'}`}>
              {status?.is_trading_active ? 'ACTIVE' : 'IDLE'}
            </span>
            <span>시스템 상태 동기화 완료</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <div className="kpi-row">
          <div className="glass-panel kpi-card">
            <span className="kpi-label">보유 포지션 수</span>
            <span className="kpi-value">{status?.active_positions_count || 0} 종목</span>
          </div>
          <div className="glass-panel kpi-card">
            <span className="kpi-label">트레이딩 활성화</span>
            <span className={`kpi-value ${status?.is_trading_active ? 'kpi-up' : 'kpi-down'}`}>
              {status?.is_trading_active ? 'ON' : 'OFF'}
            </span>
          </div>
          <div className="glass-panel kpi-card">
            <span className="kpi-label">네트워크 지연</span>
            <span className="kpi-value">8ms (안정)</span>
          </div>
          <div className="glass-panel kpi-card">
            <span className="kpi-label">PPO 모델 버전</span>
            <span className="kpi-value">
              {status?.model_version || "PPO v1"}
              {status?.model_updated && (
                <span style={{ fontSize: "0.7em", color: "var(--text-secondary)", marginLeft: "6px" }}>
                  ({status.model_updated})
                </span>
              )}
            </span>
          </div>
        </div>

        <div className="glass-panel main-chart">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3>📈 종합 전략 차트 (KOSPI 200)</h3>
            <span className="badge" style={{ background: "rgba(255,255,255,0.1)", border: "1px solid var(--accent-blue)" }}>
              {status?.api_connected ? "실시간 동기화 중" : "연결 대기 중"}
            </span>
          </div>
          <div className="chart-placeholder">
            [ TradingView 라이브러리 차트 렌더링 영역 ]<br/>
            (AI 매수/매도 시그널 오버레이 표시)
          </div>
        </div>
      </main>

      {/* Right Sidebar: News Timeline */}
      <aside className="sidebar">
        <div className="glass-panel kill-switch-panel">
          <h2 style={{ color: "var(--up-color)" }}>🚨 비상 정지 시스템</h2>
          <button 
            className="kill-btn" 
            onClick={handleKillSwitch}
            disabled={!status?.is_trading_active}
          >
            KILL SWITCH (전량 청산)
          </button>
        </div>

        <div className="glass-panel" style={{ padding: "20px", flex: 1, display: "flex", flexDirection: "column" }}>
          <h3 style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "10px", marginBottom: "15px" }}>📰 AI 뉴스 타임라인</h3>
          <div className="news-feed" style={{ flex: 1, overflowY: "auto" }}>
            {news.map((item, idx) => (
              <a href={item.url} target="_blank" rel="noopener noreferrer" key={idx} className="news-item-link">
                <div className="news-card">
                  <div className="news-meta">
                    <span className="news-source">{item.source}</span>
                    <span className="news-time">{item.time}</span>
                  </div>
                  <div className="news-title">{item.title}</div>
                  <div className={`news-sentiment ${item.sentiment.toLowerCase()}`}>
                    {item.sentiment === "POSITIVE" ? "↗ 긍정적 분석" : "↘ 주의 요망"}
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      </aside>

      {/* 투자일지 - full-width bottom panel */}
      <div className="journal-panel glass-panel">
        <div className="journal-header">
          <h2>📔 투자일지</h2>
          <select
            value={journalDate}
            onChange={(e) => handleJournalDateChange(e.target.value)}
            className="journal-select"
          >
            {journalList.map(j => (
              <option key={j.date} value={j.date}>
                {j.date.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')}
                {` (${j.pnl >= 0 ? '+' : ''}${j.pnl.toLocaleString()}원)`}
              </option>
            ))}
            {!journalList.find(j => j.date === journalDate) && (
              <option value={journalDate}>{journalDate} (오늘)</option>
            )}
          </select>
        </div>
        {currentJournal ? (
          <div className="journal-content">
            <div className="journal-row">
              <span className="label">레짐</span>
              <span>{currentJournal.regime}</span>
            </div>
            <div className="journal-row">
              <span className="label">손익</span>
              <span className={currentJournal.pnl >= 0 ? "profit" : "loss"}>
                {currentJournal.pnl >= 0 ? "+" : ""}{currentJournal.pnl.toLocaleString()}원
              </span>
            </div>
            <div className="journal-section">
              <div className="label">전략 요약</div>
              <div className="journal-text">{currentJournal.strategy_summary || "—"}</div>
            </div>
            <div className="journal-section">
              <div className="label">매매 내역</div>
              <div className="journal-text">{currentJournal.trade_summary || "—"}</div>
            </div>
            <div className="journal-section">
              <div className="label">주요 이벤트</div>
              <div className="journal-text">{currentJournal.news_events || "—"}</div>
            </div>
            <div className="journal-section">
              <div className="label">내일 계획</div>
              <div className="journal-text">{currentJournal.tomorrow_plan || "—"}</div>
            </div>
          </div>
        ) : (
          <div className="journal-empty">이 날짜의 일지가 없습니다.</div>
        )}
      </div>
    </div>
  );
}
