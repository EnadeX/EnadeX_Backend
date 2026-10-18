import type { UseQueryResult } from "@tanstack/react-query";
import { type ReactNode } from "react";

import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingSpinner } from "./LoadingSpinner";

export function QueryBoundary<TData>({
  query,
  isEmpty,
  emptyTitle,
  emptyDescription,
  loadingLabel,
  children,
}: {
  query: UseQueryResult<TData>;
  isEmpty?: (data: TData) => boolean;
  emptyTitle?: string;
  emptyDescription?: ReactNode;
  loadingLabel?: string;
  children: (data: TData) => ReactNode;
}) {
  if (query.isPending) return <LoadingSpinner label={loadingLabel} />;
  if (query.isError) {
    const message =
      query.error instanceof Error
        ? query.error.message
        : "Erro desconhecido";
    return <ErrorState message={message} onRetry={() => query.refetch()} />;
  }
  const data = query.data as TData;
  if (isEmpty?.(data)) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }
  return <>{children(data)}</>;
}
