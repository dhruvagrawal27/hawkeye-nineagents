import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { type Alert, alertsApi } from '@/lib/api';
import { hawkeyeWs } from '@/lib/ws';

export function useRealtimeAlerts(limit = 20) {
  const qc = useQueryClient();
  const [latest, setLatest] = useState<Alert | null>(null);

  const query = useQuery({
    queryKey: ['alerts', { limit }],
    queryFn: () => alertsApi.list({ limit }),
    refetchInterval: 30_000,
  });

  useEffect(() => {
    hawkeyeWs.connect();
    const unsub = hawkeyeWs.subscribe((msg) => {
      if (msg.type === 'alert.new' && msg.alert) {
        setLatest(msg.alert as Alert);
        qc.setQueryData<Alert[]>(['alerts', { limit }], (existing) => {
          const next = [msg.alert as Alert, ...(existing ?? [])];
          return next.slice(0, limit);
        });
      } else if (msg.type === 'alert.updated' && msg.alert) {
        // Refresh existing row in place
        qc.setQueryData<Alert[]>(['alerts', { limit }], (existing) => {
          if (!existing) return existing;
          const idx = existing.findIndex((a) => a.id === msg.alert.id);
          if (idx === -1) return existing;
          const updated = { ...existing[idx], ...msg.alert };
          const next = [...existing];
          next[idx] = updated;
          return next;
        });
      }
    });
    return () => {
      unsub();
    };
  }, [qc, limit]);

  return { ...query, latest };
}
