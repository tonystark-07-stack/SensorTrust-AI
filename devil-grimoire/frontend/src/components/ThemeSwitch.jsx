/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  ThemeSwitch — Tactile 3D Sun/Moon Theme Toggle                          ║
 * ║  ──────────────────────────────────────────────────────────────────────  ║
 * ║  Faithful implementation of the reference sun/moon pill switch:          ║
 * ║  - Recessed pill-shaped track with realistic inset bevel & shadows       ║
 * ║  - Raised 3D circular thumb with realistic multi-layer drop shadows      ║
 * ║  - Golden sun icon for light mode, royal blue crescent moon + stars for  ║
 * ║    dark mode, and subtle inactive outline icons in the track             ║
 * ║  - Smooth 250ms transitions, keyboard accessibility & ARIA support       ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 */

import React from 'react';

/** Pixel-perfect Sun Icon matching reference */
const SunIcon = ({ color = '#F59E0B', size = 17, strokeWidth = 2.2 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="transition-colors duration-200"
  >
    <circle cx="12" cy="12" r="4.3" />
    <line x1="12" y1="2" x2="12" y2="4.5" />
    <line x1="12" y1="19.5" x2="12" y2="22" />
    <line x1="2" y1="12" x2="4.5" y2="12" />
    <line x1="19.5" y1="12" x2="22" y2="12" />
    <line x1="4.93" y1="4.93" x2="6.7" y2="6.7" />
    <line x1="17.3" y1="17.3" x2="19.07" y2="19.07" />
    <line x1="4.93" y1="19.07" x2="6.7" y2="17.3" />
    <line x1="17.3" y1="6.7" x2="19.07" y2="4.93" />
  </svg>
);

/** Pixel-perfect Crescent Moon with Two 4-point Stars matching reference */
const MoonIcon = ({ color = '#2563EB', size = 17, strokeWidth = 2.2 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="transition-colors duration-200"
  >
    {/* Crescent Moon */}
    <path
      d="M13.8 3.6 C9.2 4.6 5.8 8.7 5.8 13.6 C5.8 18.6 9.8 22.2 14.8 22.2 C16.6 22.2 18.2 21.6 19.5 20.6 C12.8 19.9 9.5 12.8 13.8 3.6 Z"
      stroke={color}
      strokeWidth={strokeWidth}
    />
    {/* Upper 4-pointed Star */}
    <path
      d="M18.8 4.2 L19.3 5.6 L20.7 6.1 L19.3 6.6 L18.8 8 L18.3 6.6 L16.9 6.1 L18.3 5.6 Z"
      fill={color}
      stroke={color}
      strokeWidth="0.4"
    />
    {/* Lower 4-pointed Star */}
    <path
      d="M17.4 9.8 L17.7 10.7 L18.7 11 L17.7 11.3 L17.4 12.2 L17.1 11.3 L16.1 11 L17.1 10.7 Z"
      fill={color}
      stroke={color}
      strokeWidth="0.4"
    />
  </svg>
);

const ThemeSwitch = ({ theme, toggleTheme }) => {
  const isDark = theme === 'dark';

  const handleKeyDown = (e) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      toggleTheme();
    }
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      tabIndex={0}
      onClick={toggleTheme}
      onKeyDown={handleKeyDown}
      className={`
        relative inline-flex items-center w-[68px] h-[34px] p-[3px] rounded-full
        cursor-pointer select-none outline-none transition-colors duration-300
        focus-visible:ring-2 focus-visible:ring-[#39E75F] focus-visible:ring-offset-2
        dark:focus-visible:ring-offset-[#111318] flex-shrink-0
        ${
          isDark
            ? 'bg-[#475569]'
            : 'bg-[#DCE1E8]'
        }
      `}
      style={{
        boxShadow: isDark
          ? 'inset 0 2px 4px rgba(0, 0, 0, 0.45), inset 0 1px 2px rgba(0, 0, 0, 0.3), 0 1px 1px rgba(255, 255, 255, 0.08)'
          : 'inset 0 2px 4px rgba(0, 0, 0, 0.15), inset 0 1px 2px rgba(0, 0, 0, 0.08), 0 1px 1px rgba(255, 255, 255, 0.9)',
      }}
      id="theme-switch"
    >
      {/* ── Background Inactive Icons in Track ─────────────────────────── */}
      {/* Left side inactive icon (Sun, visible when dark mode thumb is on right) */}
      <div className="absolute left-[8px] top-0 bottom-0 flex items-center justify-center pointer-events-none">
        <SunIcon
          color={isDark ? '#7E8B9E' : 'transparent'}
          size={16}
          strokeWidth={2.0}
        />
      </div>

      {/* Right side inactive icon (Moon, visible when light mode thumb is on left) */}
      <div className="absolute right-[8px] top-0 bottom-0 flex items-center justify-center pointer-events-none">
        <MoonIcon
          color={!isDark ? '#9CA3AF' : 'transparent'}
          size={16}
          strokeWidth={2.0}
        />
      </div>

      {/* ── Raised 3D Circular Thumb ──────────────────────────────────── */}
      <div
        className={`
          relative z-10 w-[28px] h-[28px] rounded-full flex items-center justify-center
          bg-gradient-to-b from-[#FFFFFF] to-[#F1F3F6] border border-white/80
          transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]
          motion-reduce:transition-none
        `}
        style={{
          transform: isDark ? 'translateX(34px)' : 'translateX(0px)',
          boxShadow: isDark
            ? '0 3px 10px rgba(0, 0, 0, 0.45), 0 1px 3px rgba(0, 0, 0, 0.25), inset 0 1px 1px #FFFFFF'
            : '0 3px 8px rgba(0, 0, 0, 0.18), 0 1px 3px rgba(0, 0, 0, 0.12), inset 0 1px 1px #FFFFFF',
        }}
      >
        {isDark ? (
          <MoonIcon color="#2563EB" size={17} strokeWidth={2.3} />
        ) : (
          <SunIcon color="#F59E0B" size={17} strokeWidth={2.3} />
        )}
      </div>
    </button>
  );
};

export default ThemeSwitch;
