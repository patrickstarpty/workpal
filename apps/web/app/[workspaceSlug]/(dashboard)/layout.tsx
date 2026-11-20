"use client";

import { Suspense } from "react";
import { DashboardLayout } from "@workpal/views/layout";
import { WorkpalIcon } from "@workpal/ui/components/common/workpal-icon";
import { SearchCommand } from "@workpal/views/search";
import { FloatingChat } from "@workpal/views/chat/floating-chat";
import { StarPrompt } from "@workpal/views/star-prompt";
import { WhatsNewDeck } from "@workpal/views/whats-new";
import { WebNotificationBridge } from "@/components/web-notification-bridge";
import { WorkspaceDocumentTitle } from "@/platform/workspace-document-title";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* useSearchParams requires a Suspense boundary in the app router. Sits
          outside DashboardLayout so the tab is named while the guard is still
          resolving the workspace. */}
      <Suspense fallback={null}>
        <WorkspaceDocumentTitle />
      </Suspense>
      <DashboardLayout
        loadingIndicator={<WorkpalIcon mode="think" size={40} />}
        extra={
          <>
            <SearchCommand />
            <WebNotificationBridge />
            <FloatingChat />
            <StarPrompt />
            <WhatsNewDeck />
          </>
        }
      >
        {children}
      </DashboardLayout>
    </>
  );
}
