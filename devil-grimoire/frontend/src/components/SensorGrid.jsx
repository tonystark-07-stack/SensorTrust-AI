/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  SensorGrid — Dual-Theme Infrastructure Diagnostic Console               ║
 * ║  ──────────────────────────────────────────────────────────────────────  ║
 * ║  - Responsive full-width hardware node telemetry                         ║
 * ║  - Light & Dark mode support with high-contrast semantic tokens          ║
 * ║  - Dynamic section summary: "X active · Y healthy · Z attention"         ║
 * ║  - Unclipped 6-dimension telemetry features & XAI plain-text report      ║
 * ║  - Theme-aware circular trust gauge and discrete status tags             ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 */

import React, { useMemo } from 'react';
import {
  Thermometer, AlertTriangle, CheckCircle, Lock,
  Activity, Zap, TrendingUp, Cpu, ShieldCheck
} from 'lucide-react';

/** Color token mapper based on trust score */
const getTrustMetrics = (score, isDark) => {
  if (score >= 80) {
    return {
      textColor: isDark ? 'text-[#34D399]' : 'text-[#10B981]',
      strokeColor: isDark ? '#34D399' : '#10B981',
      badgeBg: isDark
        ? 'bg-[#10B981]/15 text-[#34D399] border-[#10B981]/30'
        : 'bg-[#EDFDF2] text-[#047857] border-[#A7F3D0]',
      label: 'Optimal',
    };
  }
  if (score >= 40) {
    return {
      textColor: isDark ? 'text-[#FBBF24]' : 'text-[#D97706]',
      strokeColor: isDark ? '#FBBF24' : '#D97706',
      badgeBg: isDark
        ? 'bg-[#F59E0B]/15 text-[#FBBF24] border-[#F59E0B]/30'
        : 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]',
      label: 'Degraded',
    };
  }
  return {
    textColor: isDark ? 'text-[#F87171]' : 'text-[#DC2626]',
    strokeColor: isDark ? '#F87171' : '#DC2626',
    badgeBg: isDark
      ? 'bg-[#EF4444]/15 text-[#F87171] border-[#EF4444]/30'
      : 'bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]',
    label: 'Critical',
  };
};

/** Class badge configuration for discrete health states */
const getClassBadgeConfig = (className, isDark) => {
  switch (className) {
    case 'Normal':
      return {
        icon: CheckCircle,
        label: 'NORMAL',
        classes: isDark
          ? 'bg-[#10B981]/15 text-[#34D399] border-[#10B981]/30'
          : 'bg-[#EDFDF2] text-[#065F46] border-[#A7F3D0]',
      };
    case 'Spike':
      return {
        icon: Zap,
        label: 'SPIKE',
        classes: isDark
          ? 'bg-[#F59E0B]/15 text-[#FBBF24] border-[#F59E0B]/30'
          : 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
      };
    case 'Drift':
      return {
        icon: TrendingUp,
        label: 'DRIFT',
        classes: isDark
          ? 'bg-[#F97316]/15 text-[#FB923C] border-[#F97316]/30'
          : 'bg-[#FFF7ED] text-[#C2410C] border-[#FFEDD5]',
      };
    case 'Env Event':
      return {
        icon: Thermometer,
        label: 'ENV EVENT',
        classes: isDark
          ? 'bg-[#3B82F6]/15 text-[#60A5FA] border-[#3B82F6]/30'
          : 'bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]',
      };
    case 'Stuck-At':
      return {
        icon: Lock,
        label: 'STUCK-AT',
        classes: isDark
          ? 'bg-[#EF4444]/15 text-[#F87171] border-[#EF4444]/30'
          : 'bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]',
      };
    case 'Excessive Noise':
      return {
        icon: Activity,
        label: 'NOISE ×10',
        classes: isDark
          ? 'bg-[#A855F7]/15 text-[#C084FC] border-[#A855F7]/30'
          : 'bg-[#F5F3FF] text-[#6D28D9] border-[#DDD6FE]',
      };
    default:
      return {
        icon: AlertTriangle,
        label: className?.toUpperCase() || 'UNKNOWN',
        classes: isDark
          ? 'bg-[#374151]/30 text-[#9CA3AF] border-[#4B5569]'
          : 'bg-[#F4F4F5] text-[#3F3F46] border-[#E4E4E7]',
      };
  }
};

/** Precise Circular Trust Gauge */
const CircularTrustGauge = ({ score, size = 56, strokeWidth = 4, isDark }) => {
  const metrics = getTrustMetrics(score, isDark);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedScore = Math.min(100, Math.max(0, score || 0));
  const offset = circumference - (clampedScore / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center flex-shrink-0">
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Track circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={isDark ? '#262B37' : '#E5E5E2'}
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Progress arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={metrics.strokeColor}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="square"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-500 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[14px] font-bold font-mono tracking-tight text-[var(--text-main)] leading-none">
          {Math.round(clampedScore)}
        </span>
        <span className="text-[8px] font-mono text-[var(--text-dim)] uppercase leading-none mt-0.5">
          PCT
        </span>
      </div>
    </div>
  );
};

/** Format feature names for clean technical readability without truncating */
const formatFeatureLabel = (key) => {
  const mapping = {
    noise_level: 'Noise (σ)',
    variance_ratio: 'Var Ratio',
    missing_rate: 'Missing Rate',
    z_score: 'Z-Score',
    rolling_mean: 'Roll Mean',
    rate_of_change: 'Δ Rate',
  };
  return mapping[key] || key.replace(/_/g, ' ');
};

/** Individual Sensor Card */
const SensorCard = ({ sensorId, data, isDark }) => {
  if (!data) return null;

  const { value, predicted_class, trust_score, xai_reason, features } = data;
  const badgeConfig = getClassBadgeConfig(predicted_class, isDark);
  const BadgeIcon = badgeConfig.icon;
  const trustMetrics = getTrustMetrics(trust_score, isDark);

  // Severe anomaly / degraded states
  const isAnomalous = predicted_class !== 'Normal' || (trust_score < 80);
  const isCritical = trust_score < 40;
  const isHighNoise = predicted_class === 'Excessive Noise';

  return (
    <div
      className={`bg-[var(--bg-surface)] border rounded-[4px] p-4 flex flex-col justify-between transition-all duration-150 ${
        isCritical
          ? 'border-[#DC2626] ring-1 ring-[#DC2626]/20'
          : isHighNoise
          ? 'border-[#8B5CF6]/40 hover:border-[#8B5CF6]'
          : isAnomalous
          ? 'border-[#EF4444]/40 hover:border-[#EF4444]'
          : 'border-[var(--border-color)] hover:border-[var(--border-hover)]'
      }`}
      id={`sensor-card-${sensorId}`}
    >
      <div>
        {/* Top Header: Sensor ID + Health Status Badge */}
        <div className="flex items-center justify-between pb-3 border-b border-[var(--border-light)]">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-[2px] ${
                isCritical
                  ? 'bg-[#DC2626] animate-pulse'
                  : isAnomalous
                  ? 'bg-[#D97706]'
                  : 'bg-[var(--text-main)]'
              }`}
            />
            <h3 className="font-mono text-sm font-bold tracking-tight text-[var(--text-main)]">
              {sensorId}
            </h3>
            {isAnomalous && (
              <span className={`text-[9px] font-mono px-1 py-0.2 rounded-[2px] font-semibold border ${
                isDark
                  ? 'bg-[#EF4444]/20 text-[#F87171] border-[#EF4444]/30'
                  : 'bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]'
              }`}>
                ATTN
              </span>
            )}
          </div>
          <div
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-[3px] border text-[11px] font-mono font-medium tracking-tight ${badgeConfig.classes}`}
          >
            <BadgeIcon className="w-3 h-3" />
            <span>{badgeConfig.label}</span>
          </div>
        </div>

        {/* Readings Row: Temperature Value + Circular Trust Score */}
        <div className="flex items-center justify-between py-3">
          <div>
            <span className="block text-[11px] font-mono text-[var(--text-muted)] uppercase tracking-wider mb-0.5">
              Temperature
            </span>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold font-mono tracking-tight text-[var(--text-main)]">
                {typeof value === 'number' ? value.toFixed(2) : value}
              </span>
              <span className="text-xs font-mono font-medium text-[var(--text-muted)]">°C</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="text-[11px] font-mono text-[var(--text-muted)]">Trust:</span>
              <span className={`text-[11px] font-mono font-bold ${trustMetrics.textColor}`}>
                {typeof trust_score === 'number' ? trust_score.toFixed(1) : trust_score}%
              </span>
            </div>
          </div>
          <CircularTrustGauge score={trust_score} isDark={isDark} />
        </div>

        {/* Diagnostic Telemetry Grid */}
        <div className="my-2 bg-[var(--bg-nested)] border border-[var(--border-light)] rounded-[3px] p-2">
          <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] font-semibold mb-1.5 flex items-center justify-between">
            <span>Diagnostics</span>
            <span className="text-[var(--text-dim)] font-normal">6-dim telemetry</span>
          </div>
          <div className="grid grid-cols-3 gap-x-2 gap-y-1.5">
            {features &&
              Object.entries(features).slice(0, 6).map(([key, val]) => (
                <div key={key} className="flex flex-col min-w-0">
                  <span className="text-[9px] font-mono text-[var(--text-muted)] leading-tight truncate">
                    {formatFeatureLabel(key)}
                  </span>
                  <span className="text-[11px] font-mono font-medium text-[var(--text-main)] tabular-nums leading-tight">
                    {typeof val === 'number' ? val.toFixed(2) : val}
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* XAI Diagnostic Analysis Box */}
      <div className="mt-3 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-[3px] p-2.5">
        <div className="flex items-center gap-1.5 mb-1">
          <ShieldCheck className="w-3.5 h-3.5 text-[var(--text-main)]" />
          <span className="text-[10px] font-mono uppercase tracking-wider font-bold text-[var(--text-main)]">
            XAI Diagnostic Explanation
          </span>
        </div>
        <p className="text-[12px] font-sans text-[var(--text-muted)] leading-relaxed break-words">
          {xai_reason || 'Nominal behavior within calibrated statistical envelope.'}
        </p>
      </div>
    </div>
  );
};

/** SensorGrid — Main exported component */
const SensorGrid = ({ sensors, isDark = false }) => {
  const sensorIds = useMemo(() => {
    return sensors ? Object.keys(sensors).sort() : [];
  }, [sensors]);

  // Compute dynamic section summary
  const { healthyCount, attentionCount } = useMemo(() => {
    let healthy = 0;
    let attention = 0;
    sensorIds.forEach((sid) => {
      const s = sensors[sid];
      if (s && s.trust_score >= 80 && s.predicted_class === 'Normal') {
        healthy++;
      } else {
        attention++;
      }
    });
    return { healthyCount: healthy, attentionCount: attention };
  }, [sensorIds, sensors]);

  if (sensorIds.length === 0) {
    return (
      <div
        className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[4px] p-10 text-center bg-dot-grid-subtle"
        id="sensor-grid-empty"
      >
        <div className="inline-flex p-3 rounded-[4px] bg-[var(--bg-subtle)] border border-[var(--border-color)] mb-3">
          <Cpu className="w-6 h-6 text-[var(--text-muted)] animate-pulse" />
        </div>
        <h4 className="text-sm font-mono font-bold text-[var(--text-main)] uppercase tracking-wide">
          Waiting for Telemetry Stream
        </h4>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
          Establish connection to WebSocket endpoint to begin multi-sensor state estimation and trust calculation.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* ── Dynamic Section-Level Status Bar ──────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between text-xs font-mono text-[var(--text-muted)] px-3 py-1.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-[3px]">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[var(--text-main)]">{sensorIds.length} ACTIVE SENSORS</span>
          <span>·</span>
          <span className={isDark ? "text-[#34D399] font-semibold" : "text-[#047857] font-semibold"}>
            {healthyCount} HEALTHY
          </span>
          <span>·</span>
          <span className={attentionCount > 0 ? (isDark ? "text-[#F87171] font-bold" : "text-[#DC2626] font-bold") : "text-[var(--text-muted)]"}>
            {attentionCount} REQUIRING ATTENTION
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--text-dim)]">
          <span>CALIBRATED GAUSSIAN BOUNDS</span>
          <span>·</span>
          <span>MULTI-VARIATE RESIDUALS</span>
        </div>
      </div>

      {/* ── 5-Node Sensor Diagnostics Grid ────────────────────────────────── */}
      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3.5"
        id="sensor-grid"
      >
        {sensorIds.map((sid) => (
          <SensorCard key={sid} sensorId={sid} data={sensors[sid]} isDark={isDark} />
        ))}
      </div>
    </div>
  );
};

export default SensorGrid;
