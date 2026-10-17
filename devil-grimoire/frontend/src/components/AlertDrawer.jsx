/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  AlertDrawer — Dual-Theme Alert Lifecycle Console                        ║
 * ║  ──────────────────────────────────────────────────────────────────────  ║
 * ║  Structured enterprise monitoring table for tracking active and          ║
 * ║  suppressed faults, with filter controls and inline ACK verification.    ║
 * ║  Fully adapted for Light and Dark modes.                                 ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 */

import React, { useState, useMemo } from 'react';
import {
  Bell, BellOff, CheckCircle2, AlertTriangle, ShieldCheck,
  ChevronDown, ChevronUp, Check
} from 'lucide-react';

/** Map severity & suppression to restrained technical status badges */
const getAlertStyle = (severity, isSuppressed, isDark) => {
  if (isSuppressed) {
    return {
      border: isDark ? 'border-[#3B82F6]/30' : 'border-[#BFDBFE]',
      bg: isDark ? 'bg-[#3B82F6]/15' : 'bg-[#EFF6FF]',
      textColor: isDark ? 'text-[#60A5FA]' : 'text-[#1D4ED8]',
      label: 'SUPPRESSED',
      sublabel: 'Environmental Cohort Filtered',
      icon: ShieldCheck,
    };
  }
  if (severity === 'critical') {
    return {
      border: isDark ? 'border-[#EF4444]/30' : 'border-[#FECACA]',
      bg: isDark ? 'bg-[#EF4444]/15' : 'bg-[#FEF2F2]',
      textColor: isDark ? 'text-[#F87171]' : 'text-[#DC2626]',
      label: 'CRITICAL',
      sublabel: 'Immediate Intervention',
      icon: AlertTriangle,
    };
  }
  return {
    border: isDark ? 'border-[#F59E0B]/30' : 'border-[#FDE68A]',
    bg: isDark ? 'bg-[#F59E0B]/15' : 'bg-[#FEF3C7]',
    textColor: isDark ? 'text-[#FBBF24]' : 'text-[#D97706]',
    label: 'WARNING',
    sublabel: 'Threshold Deviated',
    icon: AlertTriangle,
  };
};

/** Single Alert Table Row / Item */
const AlertRow = ({ alert, isAcked, onAcknowledge, isDark }) => {
  const style = getAlertStyle(alert.severity, alert.is_suppressed, isDark);
  const StatusIcon = style.icon;

  return (
    <div
      className={`px-4 py-3 border-b border-[var(--border-light)] transition-colors flex items-center justify-between gap-3 text-xs ${
        isAcked
          ? 'opacity-40 bg-[var(--bg-surface)]'
          : 'bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)]'
      }`}
      id={`alert-${alert.id || alert.tick}`}
    >
      {/* Left: Sensor ID + Status Badge + Message */}
      <div className="flex items-start sm:items-center gap-3 flex-1 min-w-0">
        {/* Status Badge */}
        <div
          className={`flex items-center gap-1 px-2 py-0.5 rounded-[2px] border font-mono text-[10px] font-semibold flex-shrink-0 ${style.bg} ${style.border} ${style.textColor}`}
        >
          <StatusIcon className="w-3 h-3 flex-shrink-0" />
          <span>{style.label}</span>
        </div>

        {/* Sensor Node ID */}
        <span className="font-mono font-bold text-[var(--text-main)] text-xs flex-shrink-0">
          {alert.sensor_id}
        </span>

        {/* Alert Type */}
        <span className="hidden md:inline-block px-1.5 py-0.2 rounded-[2px] bg-[var(--bg-subtle)] text-[var(--text-muted)] font-mono text-[10px] uppercase border border-[var(--border-color)] flex-shrink-0">
          {alert.type}
        </span>

        {/* Message */}
        <p className="text-[var(--text-muted)] truncate font-sans text-xs flex-1">
          {alert.message}
        </p>

        {/* Tick timestamp */}
        <span className="font-mono text-[11px] text-[var(--text-dim)] flex-shrink-0 hidden sm:inline-block">
          Tick #{alert.tick}
        </span>
      </div>

      {/* Right: Actions */}
      <div className="flex-shrink-0 ml-2">
        {!isAcked && !alert.is_suppressed && (
          <button
            onClick={() => onAcknowledge(alert)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-[3px] font-mono text-[11px] font-semibold
                       bg-[var(--bg-surface)] border border-[var(--text-main)] text-[var(--text-main)]
                       hover:bg-[var(--text-main)] hover:text-[var(--bg-surface)]
                       transition-all duration-150 cursor-pointer"
            id={`ack-btn-${alert.id || alert.tick}`}
          >
            <Check className="w-3 h-3" />
            <span>ACK</span>
          </button>
        )}

        {isAcked && (
          <span className="font-mono text-[11px] text-[#10B981] flex items-center gap-1 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>ACKED</span>
          </span>
        )}

        {alert.is_suppressed && (
          <span className="font-mono text-[10px] text-[var(--text-dim)] italic">
            Suppressed
          </span>
        )}
      </div>
    </div>
  );
};

/** AlertDrawer — Main exported component */
const AlertDrawer = ({ alerts, isDark = false }) => {
  const [filter, setFilter] = useState('all'); // 'all' | 'active' | 'suppressed'
  const [isExpanded, setIsExpanded] = useState(true);
  const [ackedKeys, setAckedKeys] = useState(new Set());

  const getAlertKey = (a) => (a.id ? `id-${a.id}` : `tick-${a.tick}-${a.sensor_id}`);
  const isAlertAcked = (a) => a.is_acknowledged || ackedKeys.has(getAlertKey(a));

  const handleAcknowledge = async (alert) => {
    const key = getAlertKey(alert);
    setAckedKeys((prev) => {
      const next = new Set(prev);
      next.add(key);
      return next;
    });

    if (alert.id) {
      try {
        await fetch(`/api/alerts/${alert.id}/acknowledge`, { method: 'POST' });
      } catch (e) {
        console.warn('Failed to acknowledge alert:', e);
      }
    }
  };

  const filteredAlerts = useMemo(() => {
    let filtered = alerts || [];
    if (filter === 'active') {
      filtered = filtered.filter((a) => !a.is_suppressed && !isAlertAcked(a));
    } else if (filter === 'suppressed') {
      filtered = filtered.filter((a) => a.is_suppressed);
    }
    return filtered.slice(0, 50);
  }, [alerts, filter, ackedKeys]);

  const activeCount = useMemo(() => {
    return (alerts || []).filter((a) => !a.is_suppressed && !isAlertAcked(a)).length;
  }, [alerts, ackedKeys]);

  const suppressedCount = useMemo(() => {
    return (alerts || []).filter((a) => a.is_suppressed).length;
  }, [alerts]);

  return (
    <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[4px] overflow-hidden" id="alert-drawer">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-4 py-3 bg-[var(--bg-subtle)] border-b border-[var(--border-color)] cursor-pointer hover:bg-[var(--bg-nested)] transition-colors select-none"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="editorial-label">// 03. ALERT OBSERVABILITY</span>
          </div>
          <div className="h-3 w-[1px] bg-[var(--border-color)]" />
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-mono font-bold text-[var(--text-main)] uppercase">
              Alert Lifecycle
            </h2>
            <div className="flex items-center gap-1.5">
              <span className={`px-1.5 py-0.2 rounded-[2px] border font-mono text-[11px] font-bold ${
                isDark
                  ? 'bg-[#EF4444]/15 border-[#EF4444]/30 text-[#F87171]'
                  : 'bg-[#FEF2F2] border-[#FECACA] text-[#DC2626]'
              }`}>
                {activeCount} ACTIVE
              </span>
              <span className={`px-1.5 py-0.2 rounded-[2px] border font-mono text-[11px] font-semibold ${
                isDark
                  ? 'bg-[#3B82F6]/15 border-[#3B82F6]/30 text-[#60A5FA]'
                  : 'bg-[#EFF6FF] border-[#BFDBFE] text-[#1D4ED8]'
              }`}>
                {suppressedCount} SUPPRESSED
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-[var(--text-muted)] hidden sm:inline">
            {isExpanded ? 'COLLAPSE PANEL' : 'EXPAND PANEL'}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-[var(--text-muted)]" />
          ) : (
            <ChevronDown className="w-4 h-4 text-[var(--text-muted)]" />
          )}
        </div>
      </div>

      {/* ── Content ───────────────────────────────────────────────────────── */}
      {isExpanded && (
        <div>
          {/* Filter Bar */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border-light)] bg-[var(--bg-surface)]">
            <div className="flex gap-1.5">
              {[
                { key: 'all', label: `ALL (${(alerts || []).length})` },
                { key: 'active', label: `ACTIVE UNRESOLVED (${activeCount})` },
                { key: 'suppressed', label: `SUPPRESSED COHORT (${suppressedCount})` },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={(e) => {
                    e.stopPropagation();
                    setFilter(key);
                  }}
                  className={`px-2.5 py-1 rounded-[2px] font-mono text-[11px] font-semibold transition-all cursor-pointer ${
                    filter === key
                      ? 'bg-[#242424] text-white dark:bg-[#303541] dark:text-[#ECEFF4] shadow-xs'
                      : 'bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-color)] hover:text-[var(--text-main)]'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="text-[10px] font-mono text-[var(--text-dim)] hidden md:inline">
              SHOWING RECENT {filteredAlerts.length} RECORDS
            </span>
          </div>

          {/* Table Rows */}
          <div className="divide-y divide-[var(--border-light)] max-h-72 overflow-y-auto">
            {filteredAlerts.length === 0 ? (
              <div className="text-center py-10 px-4">
                <BellOff className="w-8 h-8 text-[var(--text-dim)] mx-auto mb-2" />
                <h4 className="text-xs font-mono font-bold text-[var(--text-main)] uppercase">
                  No Alerts to Display
                </h4>
                <p className="text-[11px] font-sans text-[var(--text-muted)] mt-0.5">
                  Telemetry parameters across all monitored nodes are operating within established statistical confidence bounds.
                </p>
              </div>
            ) : (
              filteredAlerts.map((alert, idx) => (
                <AlertRow
                  key={`${alert.tick}-${alert.sensor_id}-${alert.id || idx}`}
                  alert={alert}
                  isAcked={isAlertAcked(alert)}
                  onAcknowledge={handleAcknowledge}
                  isDark={isDark}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AlertDrawer;
