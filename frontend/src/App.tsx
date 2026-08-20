import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthContext";
import { AppShell } from "@/components/layout/AppShell";
import { RequireRole } from "@/components/layout/RequireRole";
import { LandingPage } from "@/pages/LandingPage";
import { AuthPage } from "@/pages/AuthPage";
import { InvitePage } from "@/pages/InvitePage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { HomePage } from "@/pages/HomePage";
import { KnowledgePage } from "@/pages/KnowledgePage";
import { AgentsPage } from "@/pages/AgentsPage";
import { ActivityPage } from "@/pages/ActivityPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { SourcesPage } from "@/pages/SourcesPage";
import { PeoplePage } from "@/pages/PeoplePage";
import { SettingsPage } from "@/pages/SettingsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/invite/:token" element={<InvitePage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />

          <Route path="/app" element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route
              path="overview"
              element={
                <RequireRole minRole="admin">
                  <OverviewPage />
                </RequireRole>
              }
            />
            <Route
              path="sources"
              element={
                <RequireRole minRole="admin">
                  <SourcesPage />
                </RequireRole>
              }
            />
            <Route
              path="people"
              element={
                <RequireRole minRole="admin">
                  <PeoplePage />
                </RequireRole>
              }
            />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
