import { useCallback, useEffect, useRef, useState } from "react";

/** Carrega dados de forma assíncrona (com recarga manual) sem bibliotecas extras. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = [], enabled = true) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const call = useRef(0);

  const reload = useCallback(async () => {
    const id = ++call.current;
    setLoading(true);
    setError(undefined);
    try {
      const result = await loader();
      if (id === call.current) setData(result);
    } catch (e) {
      if (id === call.current) setError((e as Error).message);
    } finally {
      if (id === call.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (enabled) void reload();
  }, [reload, enabled]);

  return { data, error, loading, reload, setData };
}
