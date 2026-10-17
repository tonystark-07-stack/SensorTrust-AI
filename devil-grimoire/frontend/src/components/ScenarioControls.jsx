/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  ScenarioControls — Dual-Theme Active Fault Injection Console           ║
 * ║  ──────────────────────────────────────────────────────────────────────  ║
 * ║  Infrastructure-grade fault injection and CSV evaluation module.        ║
 * ║  - Distinct Reset action vs. fault injection matrix                      ║
 * ║  - Seamless Light and Dark theme compatibility                           ║
 * ║  - Professional CSV upload zone and segmented speed selector             ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 */

import React, { useState, useRef, useEffect } from 'react';
import {
  Zap, TrendingUp, Thermometer, Lock, Activity,
  RotateCcw, Upload, Square, Loader2, Play, FileSpreadsheet,
  CheckCircle2, AlertCircle
} from 'lucide-react';

/** Fault injection scenarios (excluding reset) */
const FAULT_SCENARIOS = [
  {
    id: 'spike',
    label: 'Spike',
    icon: Zap,
    target: 'TEMP-02',
    desc: '+12.0°C thermal impulse',
  },
  {
    id: 'drift',
    label: 'Drift',
    icon: TrendingUp,
    target: 'TEMP-04',
    desc: '+0.025°C/tick slow bias',
  },
  {
    id: 'env_event',
    label: 'Env Event',
    icon: Thermometer,
    target: 'Cohort (4)',
    desc: '+4.5°C multi-node ramp',
  },
  {
    id: 'stuck_at',
    label: 'Stuck-At',
    icon: Lock,
    target: 'TEMP-03',
    desc: 'Frozen reading at 25°C',
  },
  {
    id: 'excessive_noise',
    label: 'Noise ×10',
    icon: Activity,
    target: 'TEMP-05',
    desc: '10× variance degradation',
  },
];

/** Playback speed multiplier options */
const SPEEDS = [
  { value: 1, label: '1×' },
  { value: 5, label: '5×' },
  { value: 10, label: '10×' },
];

const ScenarioControls = ({ activeScenario = 'normal', onScenarioChange }) => {
  const [currentScenario, setCurrentScenario] = useState(activeScenario);
  const [isUploading, setIsUploading] = useState(false);
  const [csvInfo, setCsvInfo] = useState(null);
  const [csvSpeed, setCsvSpeed] = useState(1);
  const [statusMsg, setStatusMsg] = useState('');
  const [statusType, setStatusType] = useState('info'); // 'info' | 'success' | 'error'
  const fileInputRef = useRef(null);

  // Keep internal state in sync with external prop
  useEffect(() => {
    if (activeScenario && activeScenario !== currentScenario) {
      setCurrentScenario(activeScenario);
    }
  }, [activeScenario]);

  /** Send scenario injection request to backend */
  const handleScenario = async (scenarioId) => {
    setCurrentScenario(scenarioId);
    if (onScenarioChange) onScenarioChange(scenarioId);

    if (scenarioId === 'spike') {
      setTimeout(() => {
        setCurrentScenario('normal');
        if (onScenarioChange) onScenarioChange('normal');
      }, 1500);
    }
    try {
      const res = await fetch('/api/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioId }),
      });
      const data = await res.json();
      setStatusType('success');
      setStatusMsg(data.message || `Scenario: ${scenarioId}`);

      setTimeout(() => setStatusMsg(''), 3500);
    } catch (e) {
      setStatusType('error');
      setStatusMsg(`Failed: ${e.message}`);
    }
  };

  /** Handle CSV file upload */
  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setStatusType('info');
    setStatusMsg(`Uploading ${file.name}...`);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`/api/upload-csv?speed=${csvSpeed}`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();

      if (data.status === 'ok') {
        setCsvInfo(data);
        setStatusType('success');
        setStatusMsg(data.message || 'CSV replay started.');
      } else {
        setStatusType('error');
        setStatusMsg(data.message || 'CSV processing failed.');
      }
    } catch (e) {
      setStatusType('error');
      setStatusMsg(`Upload failed: ${e.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  /** Stop CSV replay */
  const handleStopCsv = async () => {
    try {
      await fetch('/api/stop-csv', { method: 'POST' });
      setCsvInfo(null);
      setStatusType('info');
      setStatusMsg('CSV replay halted.');
      setTimeout(() => setStatusMsg(''), 3000);
    } catch (e) {
      setStatusType('error');
      setStatusMsg(`Stop failed: ${e.message}`);
    }
  };

  return (
    <div className="bg-[var(--bg-surface)] border border-[var(--border-color)] rounded-[4px] p-4 space-y-4" id="scenario-controls">
      {/* ── Section Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--border-light)]">
        <div>
          <span className="editorial-label block">// 01B. SCENARIO INJECTOR</span>
          <h2 className="text-sm font-mono font-bold text-[var(--text-main)] uppercase mt-0.5">
            Fault Injection Engine
          </h2>
        </div>
        <span className="text-[10px] font-mono text-[var(--text-muted)] px-1.5 py-0.5 rounded-[2px] bg-[var(--bg-subtle)] border border-[var(--border-color)]">
          STRESS ENGINE
        </span>
      </div>

      {/* ── Distinct Reset Action ───────────────────────────────────────────── */}
      <div>
        <button
          onClick={() => handleScenario('normal')}
          className={`w-full flex items-center justify-between px-3 py-2 rounded-[3px] border font-mono text-xs font-semibold transition-all duration-150 cursor-pointer ${
            currentScenario === 'normal'
              ? 'bg-[#242424] text-white border-[#242424] dark:bg-[#303541] dark:border-[#4B5569] dark:text-[#ECEFF4] shadow-sm'
              : 'bg-[var(--bg-subtle)] text-[var(--text-main)] border-[var(--border-color)] hover:bg-[var(--bg-nested)]'
          }`}
          id="scenario-btn-normal"
          title="Clear all active synthetic faults and revert to calibrated baseline"
        >
          <div className="flex items-center gap-2">
            <RotateCcw className="w-3.5 h-3.5 text-[#39E75F]" />
            <span>RESET SENSORS (NOMINAL)</span>
          </div>
          <span className={`text-[10px] px-1.5 py-0.2 rounded-[2px] ${
            currentScenario === 'normal' ? 'bg-[#39E75F] text-[#181818] font-bold' : 'text-[var(--text-muted)]'
          }`}>
            {currentScenario === 'normal' ? 'ACTIVE' : 'READY'}
          </span>
        </button>
      </div>

      {/* ── Anomaly Injection Grid ────────────────────────────────────────── */}
      <div>
        <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider block mb-1.5 font-semibold">
          Synthetic Fault Injections:
        </span>
        <div className="grid grid-cols-2 gap-2">
          {FAULT_SCENARIOS.map(({ id, label, icon: Icon, target, desc }) => {
            const isActive = currentScenario === id;
            return (
              <button
                key={id}
                onClick={() => handleScenario(id)}
                className={`flex flex-col text-left p-2.5 rounded-[3px] border transition-all duration-150 cursor-pointer select-none ${
                  isActive
                    ? 'bg-[#242424] text-white border-[#242424] dark:bg-[#303541] dark:border-[#4B5569] dark:text-[#ECEFF4] shadow-sm'
                    : 'bg-[var(--bg-surface)] text-[var(--text-main)] border-[var(--border-color)] hover:border-[var(--text-main)] hover:bg-[var(--bg-subtle)]'
                }`}
                id={`scenario-btn-${id}`}
                title={desc}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#39E75F]' : 'text-[var(--text-muted)]'}`} />
                  <span className={`text-[9px] font-mono uppercase px-1 rounded-[2px] ${
                    isActive
                      ? 'bg-[#39E75F]/20 text-[#39E75F]'
                      : 'bg-[var(--bg-subtle)] text-[var(--text-muted)]'
                  }`}>
                    {target}
                  </span>
                </div>
                <span className="text-xs font-mono font-bold tracking-tight">
                  {label}
                </span>
                <span className={`text-[10px] leading-tight truncate mt-0.5 ${
                  isActive ? 'text-[#D5D5D2] dark:text-[#A3ABB8]' : 'text-[var(--text-muted)]'
                }`}>
                  {desc}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Status Message Feedback ─────────────────────────────────────────── */}
      {statusMsg && (
        <div
          className={`flex items-center gap-2 p-2 rounded-[3px] border text-xs font-mono transition-all ${
            statusType === 'error'
              ? 'bg-[#FEF2F2] border-[#FECACA] text-[#DC2626] dark:bg-[#EF4444]/15 dark:border-[#EF4444]/30 dark:text-[#F87171]'
              : statusType === 'success'
              ? 'bg-[#EDFDF2] border-[#A7F3D0] text-[#047857] dark:bg-[#10B981]/15 dark:border-[#10B981]/30 dark:text-[#34D399]'
              : 'bg-[var(--bg-subtle)] border border-[var(--border-color)] text-[var(--text-main)]'
          }`}
        >
          {statusType === 'error' ? (
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 text-[#10B981]" />
          )}
          <span className="truncate">{statusMsg}</span>
        </div>
      )}

      {/* ── CSV Evaluation Mode ────────────────────────────────────────────── */}
      <div className="pt-2 border-t border-[var(--border-light)] space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="editorial-label block">// 01C. BENCHMARK</span>
            <h3 className="text-xs font-mono font-bold text-[var(--text-main)] uppercase">
              CSV Evaluation Mode
            </h3>
          </div>
          <FileSpreadsheet className="w-4 h-4 text-[var(--text-muted)]" />
        </div>

        {/* Playback speed selector */}
        <div className="flex items-center justify-between bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-[3px] p-1.5">
          <span className="text-[11px] font-mono text-[var(--text-muted)]">Replay Speed:</span>
          <div className="flex gap-1">
            {SPEEDS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setCsvSpeed(value)}
                className={`px-2 py-0.5 rounded-[2px] text-xs font-mono font-semibold transition-all cursor-pointer ${
                  csvSpeed === value
                    ? 'bg-[#242424] text-white dark:bg-[#303541] dark:text-[#ECEFF4] shadow-xs'
                    : 'bg-[var(--bg-surface)] text-[var(--text-muted)] border border-[var(--border-color)] hover:text-[var(--text-main)]'
                }`}
                id={`speed-btn-${value}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Upload & Stop controls */}
        <div className="flex gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-[3px]
                       bg-[var(--bg-surface)] border border-[var(--text-main)] text-[var(--text-main)]
                       hover:bg-[var(--text-main)] hover:text-[var(--bg-surface)]
                       transition-all duration-150 text-xs font-mono font-semibold
                       disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            id="csv-upload-btn"
          >
            {isUploading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Upload className="w-3.5 h-3.5" />
            )}
            <span>{isUploading ? 'PARSING CSV...' : 'UPLOAD CSV DATA'}</span>
          </button>

          {csvInfo && (
            <button
              onClick={handleStopCsv}
              className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-[3px]
                         bg-[#FEF2F2] border border-[#DC2626] text-[#DC2626]
                         dark:bg-[#EF4444]/15 dark:border-[#EF4444]/30 dark:text-[#F87171]
                         hover:bg-[#DC2626] hover:text-white
                         transition-all duration-150 text-xs font-mono font-semibold cursor-pointer"
              id="csv-stop-btn"
            >
              <Square className="w-3 h-3 fill-current" />
              <span>HALT</span>
            </button>
          )}
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          className="hidden"
          id="csv-file-input"
        />

        {/* CSV Status Card */}
        {csvInfo && (
          <div className="bg-[var(--bg-nested)] border border-[var(--border-color)] rounded-[3px] p-2.5 text-xs font-mono">
            <div className="flex items-center justify-between text-[var(--text-main)] font-semibold mb-1">
              <span className="flex items-center gap-1">
                <Play className="w-3 h-3 text-[#10B981] fill-[#10B981]" />
                REPLAY ACTIVE
              </span>
              <span className="text-[10px] text-[var(--text-muted)]">{csvSpeed}× Rate</span>
            </div>
            <div className="text-[11px] text-[var(--text-muted)] space-y-0.5">
              <div>Rows: <span className="font-bold text-[var(--text-main)]">{csvInfo.rows}</span></div>
              <div>Nodes: <span className="font-bold text-[var(--text-main)]">{csvInfo.sensors?.length || 5}</span></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScenarioControls;
