"use client";

import React from "react";

export default function Dashboard() {
  return (
    <div className="dashboard-grid">
      {/* Header */}
      <header className="header glass-panel">
        <div className="title-glow">❄️ 키오네 (KHIONE) 터미널</div>
        <div style={{ color: "var(--text-secondary)" }}>
          마지막 동기화: 2026.04.23 13:58:22 | 시장 레짐: <strong style={{ color: "var(--accent-blue)" }}>변동장 (Volatility)</strong>
        </div>
      </header>

      {/* Left Sidebar: Agent Stream */}
      <aside className="sidebar">
        <div className="glass-panel agent-list">
          <h3 style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "10px" }}>🧠 에이전트 가중치 (실시간)</h3>
          
          <div className="agent-item">
            <div className="agent-header">
              <span>Agent 1 (단타/모멘텀)</span>
              <span>70%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill" style={{ width: "70%" }}></div>
            </div>
          </div>

          <div className="agent-item">
            <div className="agent-header">
              <span>Agent 2 (데이/외인)</span>
              <span>20%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill" style={{ width: "20%" }}></div>
            </div>
          </div>

          <div className="agent-item">
            <div className="agent-header">
              <span>Agent 3 (스윙/안전)</span>
              <span>10%</span>
            </div>
            <div className="progress-bg">
              <div className="progress-fill" style={{ width: "10%" }}></div>
            </div>
          </div>
          
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "10px" }}>
            * Agent 3의 판단에 따라 단기 변동성 수익 극대화 중
          </p>
        </div>

        <div className="glass-panel log-panel">
          <h3 style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "10px", marginBottom: "10px" }}>📡 의사결정 스트림</h3>
          <div className="log-entry">
            <span className="log-time">13:55:12</span>
            <span className="badge buy">매수</span>
            <span>삼성전자 500주 (신호: A1, RSI 30)</span>
          </div>
          <div className="log-entry">
            <span className="log-time">13:52:05</span>
            <span className="badge sell">익절</span>
            <span>SK하이닉스 200주 (+1.2%)</span>
          </div>
          <div className="log-entry">
            <span className="log-time">13:45:00</span>
            <span style={{ color: "var(--text-secondary)" }}>[Agent 3]</span>
            <span>시장 변동성 증가 감지. 단타 비중 10% 상향 조정.</span>
          </div>
          <div className="log-entry">
            <span className="log-time">13:30:00</span>
            <span style={{ color: "var(--text-secondary)" }}>[뉴스감지]</span>
            <span>반도체 섹터 긍정적 기사 다수 (감성: +0.72)</span>
          </div>
        </div>
      </aside>

      {/* Main Content: Chart & KPI */}
      <main style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <div className="kpi-row">
          <div className="glass-panel kpi-card">
            <span className="kpi-label">총 운용 자산 (KRW)</span>
            <span className="kpi-value">₩ 124,530,000</span>
          </div>
          <div className="glass-panel kpi-card">
            <span className="kpi-label">당일 실현 손익</span>
            <span className="kpi-value kpi-up">+ ₩ 1,250,000 (1.02%)</span>
          </div>
          <div className="glass-panel kpi-card">
            <span className="kpi-label">최대 낙폭 (MDD)</span>
            <span className="kpi-value kpi-down">- 1.2% (안전)</span>
          </div>
        </div>

        <div className="glass-panel main-chart">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3>📈 종합 전략 차트 (KOSPI 200)</h3>
            <span className="badge" style={{ background: "rgba(255,255,255,0.1)", border: "1px solid var(--accent-blue)" }}>
              실시간 동기화 중
            </span>
          </div>
          <div className="chart-placeholder">
            [ TradingView 라이브러리 차트 렌더링 영역 ]<br/>
            (AI 매수/매도 시그널 오버레이 표시)
          </div>
        </div>
      </main>

      {/* Right Sidebar: Risk & Settings */}
      <aside className="sidebar">
        <div className="glass-panel kill-switch-panel">
          <h2 style={{ color: "var(--up-color)" }}>🚨 비상 정지 시스템</h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            시장 급락 또는 돌발 변수(Black Swan) 발생 시 모든 신규 진입을 중단하고 즉시 포지션을 청산합니다.
          </p>
          <button className="kill-btn">KILL SWITCH (전량 청산)</button>
        </div>

        <div className="glass-panel" style={{ padding: "20px", flex: 1 }}>
          <h3 style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "10px", marginBottom: "15px" }}>⚙️ 운영 상태</h3>
          
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
            <span>API 연결 상태:</span>
            <strong style={{ color: "#22c55e" }}>정상 (8ms)</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
            <span>남은 호출 횟수:</span>
            <strong>194 / 200 (분)</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
            <span>강화학습 모델:</span>
            <strong style={{ color: "var(--accent-blue)" }}>PPO_v4.2 (Active)</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
            <span>돌발변수 스캐너:</span>
            <strong style={{ color: "#22c55e" }}>작동 중 (Level 0)</strong>
          </div>
        </div>
      </aside>
    </div>
  );
}
