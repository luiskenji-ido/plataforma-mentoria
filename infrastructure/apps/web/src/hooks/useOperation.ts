import { useEffect, useState } from "react";
import type { OperationEvent, OperationSummary } from "@infra/shared";

/** Acompanha uma operação ao vivo por Server-Sent Events (reconecta sozinho sem perder eventos). */
export function useOperation(operationId: string | undefined) {
  const [summary, setSummary] = useState<OperationSummary>();
  const [events, setEvents] = useState<OperationEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    setEvents([]);
    setSummary(undefined);
    if (!operationId) return;
    let last = 0;
    let closed = false;
    let source: EventSource | undefined;
    const open = () => {
      source = new EventSource(`/api/operations/${operationId}/events?after=${last}`);
      source.onopen = () => setConnected(true);
      source.onmessage = (m) => {
        const e = JSON.parse(m.data) as OperationEvent;
        last = Math.max(last, e.seq);
        setEvents((list) => (list.length > 3000 ? [...list.slice(-2500), e] : [...list, e]));
      };
      source.addEventListener("summary", (m) => setSummary(JSON.parse((m as MessageEvent).data) as OperationSummary));
      source.addEventListener("end", () => {
        closed = true;
        source?.close();
        setConnected(false);
      });
      source.onerror = () => {
        setConnected(false);
        source?.close();
        if (!closed) setTimeout(open, 2000);
      };
    };
    open();
    return () => {
      closed = true;
      source?.close();
    };
  }, [operationId]);

  return { summary, events, connected };
}
