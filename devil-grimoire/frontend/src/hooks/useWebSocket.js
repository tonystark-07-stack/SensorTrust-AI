/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  DEVIL GRIMOIRE — Custom WebSocket Hook (Production Grade)              ║
 * ║  ──────────────────────────────────────────────────────────────────────  ║
 * ║  Auto-reconnecting WebSocket hook with connection state management.    ║
 * ║  Prevents React StrictMode teardown loops & unneeded re-connections.   ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 */

import { useEffect, useRef, useState, useCallback } from 'react';

/** Connection states for UI badges */
export const WS_STATES = {
  CONNECTING: 'connecting',
  LIVE: 'live',
  RECONNECTING: 'reconnecting',
  OFFLINE: 'offline',
};

/**
 * useWebSocket — Custom hook for auto-reconnecting WebSocket connection.
 */
export function useWebSocket(url, options = {}) {
  const {
    onMessage,
    maxRetries = 50,
    baseDelay = 1000,
    maxDelay = 10000,
  } = options;

  const [status, setStatus] = useState(WS_STATES.CONNECTING);
  const [lastMessage, setLastMessage] = useState(null);

  const wsRef = useRef(null);
  const retriesRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const mountedRef = useRef(true);

  // Store callbacks in refs so changes don't re-trigger connection effects
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const maxRetriesRef = useRef(maxRetries);
  const baseDelayRef = useRef(baseDelay);
  const maxDelayRef = useRef(maxDelay);

  useEffect(() => {
    maxRetriesRef.current = maxRetries;
    baseDelayRef.current = baseDelay;
    maxDelayRef.current = maxDelay;
  }, [maxRetries, baseDelay, maxDelay]);

  /** Establish WebSocket connection safely */
  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Detach and close any existing socket cleanly without triggering its onclose
    if (wsRef.current) {
      try {
        const oldWs = wsRef.current;
        wsRef.current = null;
        oldWs.onopen = null;
        oldWs.onmessage = null;
        oldWs.onerror = null;
        oldWs.onclose = null;
        oldWs.close();
      } catch (err) {
        console.warn('[GRIMOIRE WS] Cleanup warning:', err);
      }
    }

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    setStatus(retriesRef.current === 0 ? WS_STATES.CONNECTING : WS_STATES.RECONNECTING);

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current || wsRef.current !== ws) return;
        console.log('[GRIMOIRE WS] Connected to', url);
        setStatus(WS_STATES.LIVE);
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current || wsRef.current !== ws) return;
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          if (onMessageRef.current) {
            onMessageRef.current(data);
          }
        } catch (e) {
          console.warn('[GRIMOIRE WS] Failed to parse message:', e);
        }
      };

      ws.onclose = (event) => {
        if (!mountedRef.current || wsRef.current !== ws) return;
        console.log(`[GRIMOIRE WS] Disconnected (code: ${event.code})`);

        if (retriesRef.current < maxRetriesRef.current) {
          setStatus(WS_STATES.RECONNECTING);
          const delay = Math.min(
            baseDelayRef.current * Math.pow(1.5, retriesRef.current),
            maxDelayRef.current
          );
          console.log(`[GRIMOIRE WS] Reconnecting in ${Math.round(delay)}ms (attempt ${retriesRef.current + 1}/${maxRetriesRef.current})`);
          reconnectTimerRef.current = setTimeout(() => {
            retriesRef.current += 1;
            connect();
          }, delay);
        } else {
          setStatus(WS_STATES.OFFLINE);
          console.error('[GRIMOIRE WS] Max retries reached. Going offline.');
        }
      };

      ws.onerror = (error) => {
        if (!mountedRef.current || wsRef.current !== ws) return;
        console.warn('[GRIMOIRE WS] Socket error encountered');
      };
    } catch (e) {
      console.error('[GRIMOIRE WS] Failed to create WebSocket:', e);
      setStatus(WS_STATES.OFFLINE);
    }
  }, [url]);

  /** Send a message through the WebSocket */
  const send = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  /** Force reconnection */
  const reconnect = useCallback(() => {
    retriesRef.current = 0;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    connect();
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        const active = wsRef.current;
        wsRef.current = null;
        active.onopen = null;
        active.onmessage = null;
        active.onerror = null;
        active.onclose = null;
        active.close();
      }
    };
  }, [url, connect]);

  return { status, lastMessage, send, reconnect };
}

export default useWebSocket;
