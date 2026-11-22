"use client";

import { use } from "react";
import { IssueDetailRoute } from "@workpal/views/issues/components";
import { ErrorBoundary } from "@workpal/ui/components/common/error-boundary";

export default function IssueDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <ErrorBoundary resetKeys={[id]}>
      <IssueDetailRoute routeId={id} />
    </ErrorBoundary>
  );
}
