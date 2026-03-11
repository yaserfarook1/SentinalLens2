import { useCallback, useMemo } from "react";
import { createApiClient } from "@/lib/api-client";
import { getAccessToken } from "@/lib/auth";

export function useApi() {
  const getToken = useCallback(async (): Promise<string | null> => {
    return await getAccessToken();
  }, []);

  const client = useMemo(() => createApiClient(getToken), [getToken]);

  return client;
}
