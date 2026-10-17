/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  DEVIL GRIMOIRE — Dual-Theme Production Observability Dashboard          ║
 * ║  ──────────────────────────────────────────────────────────────────────  ║
 * ║  Layout Order:                                                           ║
 * ║  1. Telemetry Observability + Scenario Injector (Side-by-side row)       ║
 * ║     - Analytical KPI Strips (Raw, Trust Score %, Anomaly Penalty %)      ║
 * ║     - Predictive Decision-Support Insight Box                            ║
 * ║     - Recharts Line Time-Series with Threshold Reference Lines           ║
 * ║  2. Sensor Diagnostics (Full width, dynamic status count, XAI reports)   ║
 * ║  3. Alert Observability / Alert Lifecycle (Full width, ACK actions)      ║
 * ║  4. Editorial Footer                                                     ║
 * ║                                                                          ║
 * ║  Features:                                                               ║
 * ║  - Premium 3D Sun/Moon pill theme switch in header                       ║
 * ║  - Complete Light & Dark modes with semantic CSS custom properties       ║
 * ║  - LocalStorage persistence with system-preference detection fallback     ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 */

import React, { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine
} from 'recharts';
import {
  Wifi, WifiOff, Radio, Activity, Shield, Eye,
  BarChart3, TrendingUp, Cpu, Terminal
} from 'lucide-react';

import { useWebSocket, WS_STATES } from './hooks/useWebSocket';
import SensorGrid from './components/SensorGrid';
import AlertDrawer from './components/AlertDrawer';
import ScenarioControls from './components/ScenarioControls';
import ThemeSwitch from './components/ThemeSwitch';

const RING_BUFFER_SIZE = 60; // 60-tick rolling buffer for charts
const getWsUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  if (window.location.port === '5173') {
    return `${protocol}//${window.location.hostname || '127.0.0.1'}:8000/ws/live`;
  }
  return `${protocol}//${window.location.host}/ws/live`;
};
const WS_URL = getWsUrl();

/** Sensor color palette — high contrast colors adapted for both light and dark themes */
const getSensorColors = (isDark) => ({
  'TEMP-01': '#10B981',                         // Emerald Green
  'TEMP-02': isDark ? '#60A5FA' : '#2563EB',     // Blue
  'TEMP-03': isDark ? '#FBBF24' : '#D97706',     // Amber
  'TEMP-04': isDark ? '#F87171' : '#DC2626',     // Crimson Red
  'TEMP-05': isDark ? '#C084FC' : '#7C3AED',     // Technical Violet
});

/** Chart tabs */
const CHART_TABS = [
  { id: 'raw', label: 'Raw Telemetry', icon: Activity },
  { id: 'trust', label: 'Trust Score', icon: Shield },
  { id: 'penalty', label: 'Anomaly Penalty', icon: TrendingUp },
];

// ─────────────────────────────────────────────────────────────────────────────
// CUSTOM TOOLTIP (Theme-aware popover)
// ─────────────────────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="custom-tooltip-qn">
      <div className="text-[11px] font-mono font-bold pb-1 mb-1.5 border-b border-[var(--border-light)] flex items-center justify-between text-[var(--text-main)]">
        <span>TICK #{label}</span>
        <span className="text-[9px] text-[var(--text-dim)] uppercase tracking-wider">TELEMETRY</span>
      </div>
      <div className="space-y-1">
        {payload.map((entry, idx) => (
          <div key={idx} className="flex items-center justify-between gap-4 py-0.5">
            <div className="flex items-center gap-1.5">
              <span
                className="w-2 h-2 rounded-[1px]"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-[var(--text-muted)] font-mono text-[11px]">{entry.name}:</span>
            </div>
            <span className="text-[var(--text-main)] font-mono font-bold text-[11px]">
              {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// CONNECTION BADGE (Restrained Technical Indicator)
// ─────────────────────────────────────────────────────────────────────────────
const ConnectionBadge = ({ status, isDark }) => {
  const config = {
    [WS_STATES.LIVE]: {
      icon: Wifi,
      label: 'LIVE',
      sublabel: '1 Hz STREAM',
      dotClass: 'status-dot-live',
      className: isDark
        ? 'bg-[#10B981]/15 text-[#34D399] border-[#10B981]/30'
        : 'bg-[#EDFDF2] text-[#065F46] border-[#A7F3D0]',
    },
    [WS_STATES.CONNECTING]: {
      icon: Radio,
      label: 'CONNECTING',
      sublabel: 'INITIALIZING',
      dotClass: 'status-dot-warning',
      className: isDark
        ? 'bg-[#F59E0B]/15 text-[#FBBF24] border-[#F59E0B]/30'
        : 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
    },
    [WS_STATES.RECONNECTING]: {
      icon: Radio,
      label: 'RECONNECTING',
      sublabel: 'RETRYING',
      dotClass: 'status-dot-warning',
      className: isDark
        ? 'bg-[#F97316]/15 text-[#FB923C] border-[#F97316]/30'
        : 'bg-[#FFF7ED] text-[#C2410C] border-[#FFEDD5]',
    },
    [WS_STATES.OFFLINE]: {
      icon: WifiOff,
      label: 'OFFLINE',
      sublabel: 'DISCONNECTED',
      dotClass: 'status-dot-danger',
      className: isDark
        ? 'bg-[#EF4444]/15 text-[#F87171] border-[#EF4444]/30'
        : 'bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]',
    },
  };

  const current = config[status] || config[WS_STATES.OFFLINE];
  const { icon: Icon, label, sublabel, dotClass, className } = current;

  return (
    <div
      className={`flex items-center gap-2 px-2.5 py-1 rounded-[3px] border font-mono text-xs ${className}`}
      id="connection-badge"
    >
      <div className={dotClass} />
      <span className="font-bold tracking-tight">{label}</span>
      <span className="hidden sm:inline text-[10px] opacity-80">· {sublabel}</span>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN APP COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function App() {
  // ── Theme State Management ────────────────────────────────────────────────
  const [theme, setTheme] = useState(() => {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const urlTheme = urlParams.get('theme');
      if (urlTheme === 'dark' || urlTheme === 'light') {
        localStorage.setItem('devil_grimoire_theme', urlTheme);
        localStorage.setItem('theme', urlTheme);
        return urlTheme;
      }
      const saved = localStorage.getItem('devil_grimoire_theme') || localStorage.getItem('theme');
      if (saved === 'dark' || saved === 'light') return saved;
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
    } catch (e) {}
    return 'light';
  });

  const isDark = theme === 'dark';

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem('devil_grimoire_theme', next);
        localStorage.setItem('theme', next);
      } catch (e) {}
      return next;
    });
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.style.colorScheme = 'dark';
    } else {
      root.classList.remove('dark');
      root.style.colorScheme = 'light';
    }
  }, [theme]);

  // ── Telemetry State ───────────────────────────────────────────────────────
  const [chartData, setChartData] = useState([]);        // Ring buffer for charts
  const [latestSensors, setLatestSensors] = useState({}); // Latest sensor snapshot
  const [alerts, setAlerts] = useState([]);               // Alert accumulator
  const [activeTab, setActiveTab] = useState('raw');       // Chart tab ('raw' | 'trust' | 'penalty')
  const [tick, setTick] = useState(0);                     // Current tick
  const [cohortEvent, setCohortEvent] = useState(false);   // Cohort event flag
  const [activeScenario, setActiveScenario] = useState('normal'); // Active fault scenario

  // Use ref for ring buffer to avoid re-render cycles
  const chartDataRef = useRef([]);

  // ── WebSocket message handler ─────────────────────────────────────────────
  const handleMessage = useCallback((data) => {
    if (data.type === 'tick') {
      setTick(data.tick);
      setLatestSensors(data.sensors);
      setCohortEvent(data.cohort_event);

      // Build chart data point
      const point = { tick: data.tick };
      const trustPoint = { tick: data.tick };
      const penaltyPoint = { tick: data.tick };

      Object.entries(data.sensors).forEach(([sid, info]) => {
        point[sid] = info.value;
        trustPoint[sid] = info.trust_score;
        // Anomaly penalty = 100 - trust_score (higher = worse, 0-100 scale)
        penaltyPoint[sid] = Math.max(0, 100 - info.trust_score);
      });

      // Update ring buffer (keep last RING_BUFFER_SIZE entries)
      const newData = [...chartDataRef.current, { raw: point, trust: trustPoint, penalty: penaltyPoint }];
      if (newData.length > RING_BUFFER_SIZE) {
        newData.splice(0, newData.length - RING_BUFFER_SIZE);
      }
      chartDataRef.current = newData;

      // Update chart state
      setChartData(newData);

      // Accumulate alerts (keep last 100)
      if (data.alerts && data.alerts.length > 0) {
        setAlerts((prev) => {
          const updated = [...data.alerts, ...prev];
          return updated.slice(0, 100);
        });
      }
    }
  }, []);

  // ── WebSocket connection ──────────────────────────────────────────────────
  const { status } = useWebSocket(WS_URL, {
    onMessage: handleMessage,
  });

  // ── Derived chart data for current tab ────────────────────────────────────
  const currentChartData = useMemo(() => {
    return chartData.map((d) => d[activeTab] || d.raw);
  }, [chartData, activeTab]);

  // ── Sensor IDs from latest data ───────────────────────────────────────────
  const sensorIds = useMemo(() => {
    return Object.keys(latestSensors).sort();
  }, [latestSensors]);

  // ── Sensor Colors per theme ───────────────────────────────────────────────
  const sensorColors = useMemo(() => getSensorColors(isDark), [isDark]);

  // ── Chart Y-axis config per tab ───────────────────────────────────────────
  const yAxisConfig = useMemo(() => {
    switch (activeTab) {
      case 'trust': return { domain: [0, 100], label: 'Trust %', unit: '%' };
      case 'penalty': return { domain: [0, 100], label: 'Penalty', unit: '' };
      default: return { domain: ['auto', 'auto'], label: '°C', unit: '°C' };
    }
  }, [activeTab]);

  // ── Telemetry Intelligence Calculations ──────────────────────────────────
  const analyticsData = useMemo(() => {
    const sids = Object.keys(latestSensors).sort();
    const sensorCount = sids.length;

    // Default empty state before first tick
    if (sensorCount === 0) {
      return {
        raw: {
          avgTemp: null,
          maxTemp: null,
          maxSensor: '—',
          minTemp: null,
          minSensor: '—',
          activeCount: 0,
          status: 'NORMAL',
          headline: 'WAITING FOR DATA STREAM',
          finding: 'Awaiting telemetry packets from ingestion pipeline.',
          action: 'Ensure ingestion service is running and connected.',
        },
        trust: {
          avgTrust: null,
          lowestTrust: null,
          lowestSensor: '—',
          sensorsAtRisk: 0,
          trend: 'Insufficient history for trend assessment',
          delta: 0,
          status: 'NORMAL',
          headline: 'WAITING FOR TELEMETRY STREAM',
          finding: 'Sensor trust calculation will compute upon first telemetry tick.',
          action: 'Establish WebSocket link to stream live sensor metrics.',
        },
        penalty: {
          avgPenalty: null,
          maxPenalty: null,
          maxPenaltySensor: '—',
          sensorsWithAnomalies: 0,
          trend: 'Insufficient history for trend assessment',
          delta: 0,
          status: 'NORMAL',
          headline: 'WAITING FOR TELEMETRY STREAM',
          finding: 'Residual anomaly penalty will calculate upon live tick arrival.',
          action: 'Ensure model inference worker is active.',
        },
      };
    }

    // 1. Raw Telemetry Metrics
    let tempSum = 0;
    let maxTemp = -Infinity;
    let maxTempSensor = sids[0];
    let minTemp = Infinity;
    let minTempSensor = sids[0];
    let anomalousSensors = [];

    sids.forEach((sid) => {
      const val = latestSensors[sid]?.value ?? 0;
      tempSum += val;
      if (val > maxTemp) {
        maxTemp = val;
        maxTempSensor = sid;
      }
      if (val < minTemp) {
        minTemp = val;
        minTempSensor = sid;
      }
      if (latestSensors[sid]?.predicted_class && latestSensors[sid]?.predicted_class !== 'Normal') {
        anomalousSensors.push({
          id: sid,
          cls: latestSensors[sid].predicted_class,
          val,
          reason: latestSensors[sid].xai_reason,
        });
      }
    });

    const avgTemp = tempSum / sensorCount;

    // Check temperature excursions (Nominal baseline is ~25.0°C; excursion if > 28°C or < 22°C or anomalous)
    const hasExcursion = maxTemp > 28.0 || minTemp < 22.0 || anomalousSensors.length > 0;
    const isExtreme = maxTemp > 35.0 || minTemp < 15.0;

    let rawStatus = 'NORMAL';
    let rawHeadline = 'TEMPERATURE READINGS WITHIN NOMINAL BASELINE';
    let rawFinding = `All ${sensorCount} monitored nodes remain within nominal thermal envelope (24.0°C – 26.5°C). No temperature excursion detected.`;
    let rawAction = 'Maintain continuous 1 Hz ingestion; nominal baseline calibration active.';

    if (isExtreme) {
      rawStatus = 'CRITICAL';
      rawHeadline = `CRITICAL THERMAL OUTLIER ON ${maxTempSensor}`;
      rawFinding = `Severe temperature excursion on ${maxTempSensor} at ${maxTemp.toFixed(2)}°C (nominal: 25.0°C). Significant thermal divergence from cohort.`;
      rawAction = `Inspect physical thermal sink and verify thermocouple sensor wiring on ${maxTempSensor}.`;
    } else if (hasExcursion) {
      rawStatus = 'WARNING';
      rawHeadline = `TEMPERATURE EXCURSION DETECTED ON ${maxTempSensor}`;
      rawFinding = `Current reading of ${maxTemp.toFixed(2)}°C on ${maxTempSensor} exceeds standard operational deviation threshold.`;
      rawAction = `Verify localized airflow and compare with peer sensors (${sids.filter((s) => s !== maxTempSensor).join(', ')}).`;
    }

    // 2. Trend assessment from ring buffer
    const historyCount = chartData.length;
    let trustTrend = 'Insufficient history for trend assessment';
    let penaltyTrend = 'Insufficient history for trend assessment';
    let trustDelta = 0;
    let penaltyDelta = 0;

    if (historyCount >= 8) {
      const recentPoints = chartData.slice(-3);
      const pastWindowStart = Math.max(0, historyCount - 15);
      const pastWindowEnd = Math.max(1, historyCount - 8);
      const pastPoints = chartData.slice(pastWindowStart, pastWindowEnd);

      if (pastPoints.length > 0) {
        const getAvgFor = (points, key) => {
          let sum = 0;
          let count = 0;
          points.forEach((p) => {
            const dataObj = p[key] || {};
            sids.forEach((sid) => {
              if (typeof dataObj[sid] === 'number') {
                sum += dataObj[sid];
                count++;
              }
            });
          });
          return count > 0 ? sum / count : 0;
        };

        const recentTrustAvg = getAvgFor(recentPoints, 'trust');
        const pastTrustAvg = getAvgFor(pastPoints, 'trust');
        trustDelta = recentTrustAvg - pastTrustAvg;

        if (trustDelta > 1.0) trustTrend = 'Improving';
        else if (trustDelta < -1.0) trustTrend = 'Declining';
        else trustTrend = 'Stable';

        const recentPenaltyAvg = getAvgFor(recentPoints, 'penalty');
        const pastPenaltyAvg = getAvgFor(pastPoints, 'penalty');
        penaltyDelta = recentPenaltyAvg - pastPenaltyAvg;

        if (penaltyDelta > 1.0) penaltyTrend = 'Increasing';
        else if (penaltyDelta < -1.0) penaltyTrend = 'Decreasing';
        else penaltyTrend = 'Stable';
      }
    }

    // 3. Trust Score Tab Metrics & Insights
    let trustSum = 0;
    let lowestTrust = Infinity;
    let lowestTrustSensor = sids[0];
    let sensorsAtRisk = 0;

    sids.forEach((sid) => {
      const t = latestSensors[sid]?.trust_score ?? 100;
      trustSum += t;
      if (t < lowestTrust) {
        lowestTrust = t;
        lowestTrustSensor = sid;
      }
      if (t < 80.0) {
        sensorsAtRisk++;
      }
    });

    const avgTrust = trustSum / sensorCount;
    let trustStatus = 'NORMAL';
    let trustHeadline = 'TRUST STATUS NORMAL';
    let trustFinding = `Average sensor trust is ${avgTrust.toFixed(1)}%. No sensors currently fall below the configured trust threshold (80.0%).`;
    let trustAction = 'Consensus trust model operating optimally. Multi-sensor consensus verified.';

    if (lowestTrust < 40.0) {
      trustStatus = 'CRITICAL';
      trustHeadline = `CRITICAL TRUST DEGRADATION — ${lowestTrustSensor}`;
      trustFinding = `Trust on ${lowestTrustSensor} has collapsed to ${lowestTrust.toFixed(1)}% (Critical threshold: 40.0%). Diagnostic: ${latestSensors[lowestTrustSensor]?.xai_reason || 'Severe anomalous divergence'}.`;
      trustAction = `Quarantine ${lowestTrustSensor} from voting consensus immediately. Review alert lifecycle and inspect physical connections.`;
    } else if (lowestTrust < 80.0 || sensorsAtRisk > 0) {
      trustStatus = 'WARNING';
      trustHeadline = `TRUST DEGRADATION DETECTED — ${lowestTrustSensor}`;
      trustFinding = `${lowestTrustSensor} has the lowest trust score at ${lowestTrust.toFixed(1)}% (${sensorsAtRisk} of ${sensorCount} nodes at risk). Recent trend indicates ${trustTrend.toLowerCase()} sensor reliability.`;
      trustAction = `Inspect ${lowestTrustSensor}'s diagnostic metrics and verify probe physical contact and electromagnetic shielding.`;
    } else if (trustTrend === 'Declining') {
      trustStatus = 'WATCH';
      trustHeadline = 'SUBTLE TRUST DRIFT DETECTED';
      trustFinding = `Trust scores are trending downward over recent telemetry history (${trustDelta.toFixed(1)}% shift), though currently above warning threshold.`;
      trustAction = 'Monitor next 15-tick observation window for stabilization before applying filter adjustments.';
    }

    // 4. Anomaly Penalty Tab Metrics & Insights
    let penaltySum = 0;
    let maxPenalty = -Infinity;
    let maxPenaltySensor = sids[0];
    let sensorsWithAnomalies = 0;

    sids.forEach((sid) => {
      const pen = Math.max(0, 100 - (latestSensors[sid]?.trust_score ?? 100));
      penaltySum += pen;
      if (pen > maxPenalty) {
        maxPenalty = pen;
        maxPenaltySensor = sid;
      }
      if (pen > 20.0 || (latestSensors[sid]?.predicted_class && latestSensors[sid].predicted_class !== 'Normal')) {
        sensorsWithAnomalies++;
      }
    });

    const avgPenalty = penaltySum / sensorCount;
    let penaltyStatus = 'NORMAL';
    let penaltyHeadline = 'ANOMALY STATUS NORMAL';
    let penaltyFinding = `Average anomaly penalty across all sensors is ${avgPenalty.toFixed(1)}%. No current sensor exceeds the configured anomaly threshold (20.0%).`;
    let penaltyAction = 'Multi-sensor residual analysis within calibrated Gaussian noise floor.';

    if (maxPenalty >= 60.0) {
      penaltyStatus = 'CRITICAL';
      penaltyHeadline = `CRITICAL ANOMALY SURGE — ${maxPenaltySensor}`;
      penaltyFinding = `${maxPenaltySensor} has incurred a critical anomaly penalty of ${maxPenalty.toFixed(1)}% (Threshold: 60.0%). Classified as "${latestSensors[maxPenaltySensor]?.predicted_class || 'Fault'}".`;
      penaltyAction = `Trigger emergency isolation protocol for ${maxPenaltySensor}. Review alert drawer for unsuppressed alerts.`;
    } else if (maxPenalty >= 20.0 || sensorsWithAnomalies > 0) {
      penaltyStatus = 'WARNING';
      penaltyHeadline = `ANOMALY RISK ELEVATED — ${maxPenaltySensor}`;
      penaltyFinding = `${maxPenaltySensor} is showing an elevated anomaly penalty of ${maxPenalty.toFixed(1)}%. Latest diagnostics indicate "${latestSensors[maxPenaltySensor]?.predicted_class}" (${latestSensors[maxPenaltySensor]?.xai_reason || 'Deviation from consensus'}).`;
      penaltyAction = `Monitor subsequent readings and inspect sensor shielding. Check if cohort consistency indicates localized noise vs. environmental shock.`;
    } else if (penaltyTrend === 'Increasing') {
      penaltyStatus = 'WATCH';
      penaltyHeadline = 'INCREASING ANOMALY ACTIVITY';
      penaltyFinding = `Anomaly penalties have increased across recent telemetry window (+${penaltyDelta.toFixed(1)}%). Continue monitoring affected sensors.`;
      penaltyAction = 'Observe affected nodes for recurring noise patterns or early-stage drift.';
    }

    return {
      raw: {
        avgTemp,
        maxTemp,
        maxSensor: maxTempSensor,
        minTemp,
        minSensor: minTempSensor,
        activeCount: sensorCount,
        status: rawStatus,
        headline: rawHeadline,
        finding: rawFinding,
        action: rawAction,
      },
      trust: {
        avgTrust,
        lowestTrust,
        lowestSensor: lowestTrustSensor,
        sensorsAtRisk,
        trend: trustTrend,
        delta: trustDelta,
        status: trustStatus,
        headline: trustHeadline,
        finding: trustFinding,
        action: trustAction,
      },
      penalty: {
        avgPenalty,
        maxPenalty,
        maxPenaltySensor,
        sensorsWithAnomalies,
        trend: penaltyTrend,
        delta: penaltyDelta,
        status: penaltyStatus,
        headline: penaltyHeadline,
        finding: penaltyFinding,
        action: penaltyAction,
      },
    };
  }, [latestSensors, chartData]);

  const activeAnalytics = analyticsData[activeTab] || analyticsData.raw;

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-main)] font-sans antialiased transition-colors duration-200" id="app-root">
      {/* ── Top Header (Infrastructure Bar) ─────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-[var(--bg-surface)] border-b border-[var(--border-color)] transition-colors duration-200">
        <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-2.5">
          <div className="flex items-center justify-between gap-3">
            {/* Left: Brand Identity */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-[3px] bg-[#242424] dark:bg-[#20242D] border dark:border-[#303541] flex items-center justify-center text-white dark:text-[#ECEFF4] font-mono font-bold text-sm shadow-xs">
                DG
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-bold font-mono tracking-tight text-[var(--text-main)]">
                    DEVIL GRIMOIRE
                  </h1>
                  <span className="hidden sm:inline-block text-[10px] font-mono px-1.5 py-0.2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-[2px] text-[var(--text-muted)]">
                    v1.0.0
                  </span>
                </div>
                <p className="text-[11px] text-[var(--text-muted)] font-mono tracking-normal leading-tight">
                  SENSOR TRUST AI // XAI DASHBOARD
                </p>
              </div>
            </div>

            {/* Right: Environment, Theme Switch, Tick & Connection status */}
            <div className="flex items-center gap-3">
              {/* Cohort Event Notification Badge */}
              {cohortEvent && (
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] border text-xs font-mono font-semibold animate-pulse ${
                  isDark
                    ? 'bg-[#3B82F6]/15 border-[#3B82F6]/30 text-[#60A5FA]'
                    : 'bg-[#EFF6FF] border-[#BFDBFE] text-[#1D4ED8]'
                }`}>
                  <Eye className="w-3.5 h-3.5" />
                  <span>COHORT EVENT DETECTED</span>
                </div>
              )}

              {/* Monospace Telemetry Tick Counter */}
              <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] bg-[var(--bg-subtle)] border border-[var(--border-color)] text-xs font-mono text-[var(--text-main)]">
                <Terminal className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                <span className="text-[var(--text-muted)]">TICK:</span>
                <span className="font-bold">{String(tick).padStart(5, '0')}</span>
              </div>

              {/* Live Connection Badge */}
              <ConnectionBadge status={status} isDark={isDark} />

              {/* ── Sun/Moon Tactile Theme Switch ─────────────────────────── */}
              <ThemeSwitch theme={theme} toggleTheme={toggleTheme} />
            </div>
          </div>
        </div>
      </header>

      {/* ── Main Application Content ────────────────────────────────────────── */}
      <main className="max-w-[1720px] mx-auto px-4 sm:px-6 py-5 space-y-6">

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 1: TELEMETRY OBSERVABILITY + SCENARIO INJECTOR (75% / 25%)
            ═════════════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-5" id="telemetry-scenario-row">

          {/* ── Left Column: Telemetry Observability (3/4 width on desktop) ─── */}
          <div className="xl:col-span-3 space-y-3" id="chart-panel">
            {/* Section Header & Segmented Tab Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-1 border-b border-[var(--border-color)]">
              <div className="flex items-center gap-2">
                <span className="editorial-label">// 01. TELEMETRY OBSERVABILITY</span>
                <span className="text-[var(--border-color)] hidden sm:inline">/</span>
                <h2 className="text-sm font-mono font-bold text-[var(--text-main)] uppercase hidden sm:inline">
                  Streaming Time-Series &amp; Decision Intelligence
                </h2>
              </div>

              {/* Segmented Tab Buttons */}
              <div className="inline-flex p-0.5 rounded-[3px] bg-[var(--bg-subtle)] border border-[var(--border-color)]" id="chart-tabs">
                {CHART_TABS.map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    onClick={() => setActiveTab(id)}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-[2px] font-mono text-xs font-semibold transition-all cursor-pointer ${
                      activeTab === id
                        ? 'bg-[#242424] text-white dark:bg-[#303541] dark:text-[#ECEFF4] shadow-xs'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-main)]'
                    }`}
                    id={`tab-${id}`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* ── Tab-Specific KPI Metrics Strip ───────────────────────────── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-2.5" id="analytics-kpis">
              {activeTab === 'raw' && (
                <>
                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      AVG TEMPERATURE
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="text-lg font-mono font-bold text-[var(--text-main)]">
                        {analyticsData.raw.avgTemp !== null ? analyticsData.raw.avgTemp.toFixed(2) : '—'}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">°C</span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-dim)] block mt-0.5">
                      Nominal: ~25.00°C
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      HIGHEST READING
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="text-lg font-mono font-bold text-[var(--text-main)]">
                        {analyticsData.raw.maxTemp !== null ? analyticsData.raw.maxTemp.toFixed(2) : '—'}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">°C</span>
                    </div>
                    <span className={`text-[10px] font-mono font-semibold block mt-0.5 ${
                      isDark ? 'text-[#34D399]' : 'text-[#059669]'
                    }`}>
                      {analyticsData.raw.maxSensor}
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      LOWEST READING
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="text-lg font-mono font-bold text-[var(--text-main)]">
                        {analyticsData.raw.minTemp !== null ? analyticsData.raw.minTemp.toFixed(2) : '—'}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">°C</span>
                    </div>
                    <span className={`text-[10px] font-mono font-semibold block mt-0.5 ${
                      isDark ? 'text-[#60A5FA]' : 'text-[#2563EB]'
                    }`}>
                      {analyticsData.raw.minSensor}
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      ACTIVE SENSORS
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="text-lg font-mono font-bold text-[var(--text-main)]">
                        {analyticsData.raw.activeCount}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">Nodes</span>
                    </div>
                    <span className={`text-[10px] font-mono block mt-0.5 ${
                      isDark ? 'text-[#34D399]' : 'text-[#047857]'
                    }`}>
                      100% Ingesting
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5 col-span-2 sm:col-span-1">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      LATEST TELEMETRY
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className="text-lg font-mono font-bold text-[var(--text-main)]">
                        #{String(tick).padStart(5, '0')}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-muted)] block mt-0.5">
                      1.0 Hz Ingestion
                    </span>
                  </div>
                </>
              )}

              {activeTab === 'trust' && (
                <>
                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      AVG TRUST SCORE
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className={`text-lg font-mono font-bold ${
                        (analyticsData.trust.avgTrust ?? 100) >= 80
                          ? (isDark ? 'text-[#34D399]' : 'text-[#047857]')
                          : (isDark ? 'text-[#FBBF24]' : 'text-[#D97706]')
                      }`}>
                        {analyticsData.trust.avgTrust !== null ? `${analyticsData.trust.avgTrust.toFixed(1)}%` : '—'}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-dim)] block mt-0.5">
                      Target: ≥80.0%
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      LOWEST TRUST NODE
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className={`text-lg font-mono font-bold ${
                        (analyticsData.trust.lowestTrust ?? 100) < 40
                          ? (isDark ? 'text-[#F87171]' : 'text-[#DC2626]')
                          : (analyticsData.trust.lowestTrust ?? 100) < 80
                          ? (isDark ? 'text-[#FBBF24]' : 'text-[#D97706]')
                          : 'text-[var(--text-main)]'
                      }`}>
                        {analyticsData.trust.lowestTrust !== null ? `${analyticsData.trust.lowestTrust.toFixed(1)}%` : '—'}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-[var(--text-main)] block mt-0.5">
                      {analyticsData.trust.lowestSensor}
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      SENSORS AT RISK
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className={`text-lg font-mono font-bold ${
                        analyticsData.trust.sensorsAtRisk > 0
                          ? (isDark ? 'text-[#F87171]' : 'text-[#DC2626]')
                          : (isDark ? 'text-[#34D399]' : 'text-[#047857]')
                      }`}>
                        {analyticsData.trust.sensorsAtRisk}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">of {sensorIds.length}</span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-dim)] block mt-0.5">
                      Below 80.0% Trust
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5 col-span-2 sm:col-span-2">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      15-TICK TRUST TREND
                    </span>
                    <div className="flex items-baseline gap-1.5 mt-0.5">
                      <span className={`text-base font-mono font-bold ${
                        analyticsData.trust.trend === 'Improving'
                          ? (isDark ? 'text-[#34D399]' : 'text-[#047857]')
                          : analyticsData.trust.trend === 'Declining'
                          ? (isDark ? 'text-[#F87171]' : 'text-[#DC2626]')
                          : 'text-[var(--text-main)]'
                      }`}>
                        {analyticsData.trust.trend}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-muted)] block mt-0.5">
                      {analyticsData.trust.trend === 'Insufficient history for trend assessment'
                        ? 'Requires ≥8 ticks'
                        : `Window Delta: ${analyticsData.trust.delta > 0 ? '+' : ''}${analyticsData.trust.delta.toFixed(1)}%`}
                    </span>
                  </div>
                </>
              )}

              {activeTab === 'penalty' && (
                <>
                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      AVG ANOMALY PENALTY
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className={`text-lg font-mono font-bold ${
                        (analyticsData.penalty.avgPenalty ?? 0) > 20
                          ? (isDark ? 'text-[#F87171]' : 'text-[#DC2626]')
                          : 'text-[var(--text-main)]'
                      }`}>
                        {analyticsData.penalty.avgPenalty !== null ? `${analyticsData.penalty.avgPenalty.toFixed(1)}%` : '—'}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-dim)] block mt-0.5">
                      Scale: 0 – 100%
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      MAX NODE PENALTY
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className={`text-lg font-mono font-bold ${
                        (analyticsData.penalty.maxPenalty ?? 0) >= 60
                          ? (isDark ? 'text-[#F87171]' : 'text-[#DC2626]')
                          : (analyticsData.penalty.maxPenalty ?? 0) >= 20
                          ? (isDark ? 'text-[#FBBF24]' : 'text-[#D97706]')
                          : (isDark ? 'text-[#34D399]' : 'text-[#047857]')
                      }`}>
                        {analyticsData.penalty.maxPenalty !== null ? `${analyticsData.penalty.maxPenalty.toFixed(1)}%` : '—'}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-[var(--text-main)] block mt-0.5">
                      {analyticsData.penalty.maxPenaltySensor}
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      FLAGGED ANOMALIES
                    </span>
                    <div className="flex items-baseline gap-1 mt-0.5">
                      <span className={`text-lg font-mono font-bold ${
                        analyticsData.penalty.sensorsWithAnomalies > 0
                          ? (isDark ? 'text-[#FBBF24]' : 'text-[#D97706]')
                          : (isDark ? 'text-[#34D399]' : 'text-[#047857]')
                      }`}>
                        {analyticsData.penalty.sensorsWithAnomalies}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">of {sensorIds.length}</span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-dim)] block mt-0.5">
                      Penalty &gt; 20%
                    </span>
                  </div>

                  <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[3px] p-2.5 col-span-2 sm:col-span-2">
                    <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block">
                      15-TICK PENALTY TREND
                    </span>
                    <div className="flex items-baseline gap-1.5 mt-0.5">
                      <span className={`text-base font-mono font-bold ${
                        analyticsData.penalty.trend === 'Increasing'
                          ? (isDark ? 'text-[#F87171]' : 'text-[#DC2626]')
                          : analyticsData.penalty.trend === 'Decreasing'
                          ? (isDark ? 'text-[#34D399]' : 'text-[#047857]')
                          : 'text-[var(--text-main)]'
                      }`}>
                        {analyticsData.penalty.trend}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[var(--text-muted)] block mt-0.5">
                      {analyticsData.penalty.trend === 'Insufficient history for trend assessment'
                        ? 'Requires ≥8 ticks'
                        : `Window Delta: ${analyticsData.penalty.delta > 0 ? '+' : ''}${analyticsData.penalty.delta.toFixed(1)}%`}
                    </span>
                  </div>
                </>
              )}
            </div>

            {/* ── Predictive Decision-Support Intelligence Card ─────────────── */}
            <div
              className={`p-3 rounded-[3px] border transition-all ${
                activeAnalytics.status === 'CRITICAL'
                  ? isDark ? 'bg-[#EF4444]/10 border-[#EF4444]/30' : 'bg-[#FEF2F2] border-[#FECACA]'
                  : activeAnalytics.status === 'WARNING'
                  ? isDark ? 'bg-[#F59E0B]/10 border-[#F59E0B]/30' : 'bg-[#FFFBEB] border-[#FDE68A]'
                  : activeAnalytics.status === 'WATCH'
                  ? isDark ? 'bg-[#3B82F6]/10 border-[#3B82F6]/30' : 'bg-[#EFF6FF] border-[#BFDBFE]'
                  : 'bg-[var(--bg-subtle)] border border-[var(--border-color)]'
              }`}
              id="analytics-intelligence-card"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 mb-2 border-b border-black/5 dark:border-white/5">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded-[2px] font-mono text-[10px] font-bold border tracking-tight ${
                      activeAnalytics.status === 'CRITICAL'
                        ? 'bg-[#DC2626] text-white border-[#DC2626]'
                        : activeAnalytics.status === 'WARNING'
                        ? 'bg-[#D97706] text-white border-[#D97706]'
                        : activeAnalytics.status === 'WATCH'
                        ? 'bg-[#2563EB] text-white border-[#2563EB]'
                        : isDark
                        ? 'bg-[#10B981]/20 text-[#34D399] border-[#10B981]/40'
                        : 'bg-[#10B981] text-white border-[#10B981]'
                    }`}
                  >
                    {activeAnalytics.status}
                  </span>
                  <h4 className="font-mono text-xs font-bold text-[var(--text-main)] uppercase tracking-tight">
                    {activeAnalytics.headline}
                  </h4>
                </div>

                <div className="flex items-center gap-2">
                  {activeScenario && activeScenario !== 'normal' && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-[2px] bg-[#242424] dark:bg-[#303541] text-white dark:text-[#ECEFF4] font-semibold shadow-xs">
                      [SIMULATED FAULT: {activeScenario.toUpperCase()}]
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-[var(--text-muted)] hidden md:inline">
                    XAI DECISION ENGINE
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block font-semibold mb-0.5">
                    Observed Condition &amp; Evidence:
                  </span>
                  <p className="text-[var(--text-main)] leading-relaxed font-sans text-[12px]">
                    {activeAnalytics.finding}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase block font-semibold mb-0.5">
                    Recommended Operational Action:
                  </span>
                  <p className="text-[var(--text-main)] leading-relaxed font-sans text-[12px]">
                    {activeAnalytics.action}
                  </p>
                </div>
              </div>
            </div>

            {/* ── Recharts Surface with Theme-Aware Lines & Thresholds ─────── */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[4px] p-4 transition-colors duration-200" id="main-chart">
              <div className="h-[340px]">
                {currentChartData.length === 0 ? (
                  <div className="h-full flex items-center justify-center bg-dot-grid-subtle rounded-[2px]">
                    <div className="text-center p-6 bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[4px] max-w-sm">
                      <Activity className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2 animate-pulse" />
                      <h4 className="text-xs font-mono font-bold text-[var(--text-main)] uppercase">
                        Waiting for Telemetry Data
                      </h4>
                      <p className="text-[11px] font-sans text-[var(--text-muted)] mt-1">
                        Connect to backend stream at <span className="font-mono text-[var(--text-main)]">ws://127.0.0.1:8000/ws/live</span>
                      </p>
                    </div>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={currentChartData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="2 2" stroke={isDark ? '#242936' : '#EAEAE7'} />
                      <XAxis
                        dataKey="tick"
                        stroke={isDark ? '#444D5F' : '#C8C8C5'}
                        tick={{ fill: isDark ? '#A3ABB8' : '#666666', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                        axisLine={{ stroke: isDark ? '#303541' : '#D8D8D5' }}
                      />
                      <YAxis
                        domain={yAxisConfig.domain}
                        stroke={isDark ? '#444D5F' : '#C8C8C5'}
                        tick={{ fill: isDark ? '#A3ABB8' : '#666666', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                        axisLine={{ stroke: isDark ? '#303541' : '#D8D8D5' }}
                        width={45}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend
                        wrapperStyle={{ fontSize: '11px', fontFamily: 'JetBrains Mono', paddingTop: '8px', color: isDark ? '#A3ABB8' : '#666666' }}
                      />

                      {/* Threshold Reference Lines for Analytical Context */}
                      {activeTab === 'trust' && (
                        <>
                          <ReferenceLine
                            y={80}
                            stroke="#F59E0B"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{ value: 'Warning (80%)', fill: '#F59E0B', fontSize: 10, position: 'insideTopRight' }}
                          />
                          <ReferenceLine
                            y={40}
                            stroke="#EF4444"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{ value: 'Critical (40%)', fill: '#EF4444', fontSize: 10, position: 'insideTopRight' }}
                          />
                        </>
                      )}

                      {activeTab === 'penalty' && (
                        <>
                          <ReferenceLine
                            y={20}
                            stroke="#F59E0B"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{ value: 'Warning Threshold (20%)', fill: '#F59E0B', fontSize: 10, position: 'insideTopRight' }}
                          />
                          <ReferenceLine
                            y={60}
                            stroke="#EF4444"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{ value: 'Critical Threshold (60%)', fill: '#EF4444', fontSize: 10, position: 'insideTopRight' }}
                          />
                        </>
                      )}

                      {activeTab === 'raw' && (
                        <ReferenceLine
                          y={25.0}
                          stroke={isDark ? '#64748B' : '#8C8C89'}
                          strokeDasharray="2 2"
                          strokeWidth={1}
                          label={{ value: 'Nominal Baseline (25°C)', fill: isDark ? '#94A3B8' : '#666666', fontSize: 10, position: 'insideTopRight' }}
                        />
                      )}

                      {sensorIds.map((sid) => (
                        <Line
                          key={sid}
                          type="monotone"
                          dataKey={sid}
                          stroke={sensorColors[sid] || '#888'}
                          strokeWidth={2}
                          dot={false}
                          activeDot={{ r: 4, strokeWidth: 1, fill: isDark ? '#181B22' : '#FFFFFF', stroke: sensorColors[sid] }}
                          isAnimationActive={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>

          {/* ── Right Column: Scenario Injector (1/4 width on desktop) ─────── */}
          <div className="space-y-4" id="right-sidebar">
            <ScenarioControls
              activeScenario={activeScenario}
              onScenarioChange={setActiveScenario}
            />
          </div>
        </div>

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 2: SENSOR DIAGNOSTICS (Full Width below Telemetry row)
            ═════════════════════════════════════════════════════════════════════ */}
        <section id="sensor-diagnostics" className="space-y-2.5">
          <div className="flex items-center justify-between pb-1 border-b border-[var(--border-color)]">
            <div className="flex items-center gap-2">
              <span className="editorial-label">// 02. SENSOR DIAGNOSTICS</span>
              <span className="text-[var(--border-color)]">/</span>
              <h2 className="text-sm font-mono font-bold text-[var(--text-main)] uppercase">
                Hardware Node Telemetry &amp; Multi-Variate Analysis
              </h2>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-muted)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
              <span>{sensorIds.length} MONITORED NODES</span>
            </div>
          </div>
          <SensorGrid sensors={latestSensors} isDark={isDark} />
        </section>

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 3: ALERT OBSERVABILITY / ALERT LIFECYCLE (Below Diagnostics)
            ═════════════════════════════════════════════════════════════════════ */}
        <section id="alert-section" className="space-y-2.5">
          <AlertDrawer alerts={alerts} isDark={isDark} />
        </section>

        {/* ═════════════════════════════════════════════════════════════════════
            SECTION 4: EDITORIAL FOOTER
            ═════════════════════════════════════════════════════════════════════ */}
        <footer className="pt-4 pb-8 border-t border-[var(--border-color)] flex flex-col sm:flex-row items-center justify-between text-xs font-mono text-[var(--text-muted)] gap-2">
          <div>
            <span className="font-bold text-[var(--text-main)]">DEVIL GRIMOIRE</span> · PRODUCTION-GRADE SENSOR TRUST OBSERVABILITY
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>VIT CODE APEX 3.0</span>
            <span>·</span>
            <span>EXPLAINABLE AI ENGINE</span>
            <span>·</span>
            <span>STATUS: 200 OK</span>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;
