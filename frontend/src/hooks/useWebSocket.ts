import { useEffect, useRef, useCallback, useState } from 'react';
import type { WebSocketMessage } from '../types';

export function useWebSocket(meetingId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const listenersRef = useRef<((msg: WebSocketMessage) => void)[]>([]);

  const addListener = useCallback((fn: (msg: WebSocketMessage) => void) => {
    listenersRef.current.push(fn);
    return () => {
      listenersRef.current = listenersRef.current.filter(l => l !== fn);
    };
  }, []);

  useEffect(() => {
    if (!meetingId) {
      return;
    }

    const ws = new WebSocket(`ws://localhost:8000/ws/${meetingId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log(`[WS] Connected to meeting ${meetingId}`);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data);
        setLastMessage(msg);
        listenersRef.current.forEach(fn => fn(msg));
      } catch (e) {
        console.error('[WS] Failed to parse message:', e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log(`[WS] Disconnected from meeting ${meetingId}`);
    };

    ws.onerror = (err) => {
      console.error('[WS] Error:', err);
    };

    // Keep-alive ping
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
      wsRef.current = null;
      setIsConnected(false);
    };
  }, [meetingId]);

  return { isConnected, lastMessage, addListener };
}
