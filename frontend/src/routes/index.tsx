import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from '@/components/layout/AppLayout';
import {
  AdminRoute,
  ProtectedRoute,
  PublicOnlyRoute,
} from '@/components/layout/RouteGuards';
import { LandingPage } from '@/pages/LandingPage';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { DiseaseDetectionPage } from '@/pages/DiseaseDetectionPage';
import { CropRecommendationPage } from '@/pages/CropRecommendationPage';
import { YieldEstimationPage } from '@/pages/YieldEstimationPage';
import { WeatherPage } from '@/pages/WeatherPage';
import { HistoryPage } from '@/pages/HistoryPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { AdminUsersPage } from '@/pages/admin/AdminUsersPage';
import { AdminStatsPage } from '@/pages/admin/AdminStatsPage';
import { AdminModelsPage } from '@/pages/admin/AdminModelsPage';
import { AdminActivityPage } from '@/pages/admin/AdminActivityPage';

/** Routes that require a signed-in user, wrapped in the application chrome. */
function Protected({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
  );
}

/** Routes that require an administrator account. */
function Administrative({ children }: { children: React.ReactNode }) {
  return (
    <AdminRoute>
      <AppLayout>{children}</AppLayout>
    </AdminRoute>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnlyRoute>
            <RegisterPage />
          </PublicOnlyRoute>
        }
      />

      {/* Authenticated */}
      <Route
        path="/dashboard"
        element={
          <Protected>
            <DashboardPage />
          </Protected>
        }
      />
      <Route
        path="/disease"
        element={
          <Protected>
            <DiseaseDetectionPage />
          </Protected>
        }
      />
      <Route
        path="/crops"
        element={
          <Protected>
            <CropRecommendationPage />
          </Protected>
        }
      />
      <Route
        path="/yield"
        element={
          <Protected>
            <YieldEstimationPage />
          </Protected>
        }
      />
      <Route
        path="/weather"
        element={
          <Protected>
            <WeatherPage />
          </Protected>
        }
      />
      <Route
        path="/history"
        element={
          <Protected>
            <HistoryPage />
          </Protected>
        }
      />
      <Route
        path="/profile"
        element={
          <Protected>
            <ProfilePage />
          </Protected>
        }
      />

      {/* Administration */}
      <Route
        path="/admin"
        element={
          <Administrative>
            <AdminStatsPage />
          </Administrative>
        }
      />
      <Route
        path="/admin/users"
        element={
          <Administrative>
            <AdminUsersPage />
          </Administrative>
        }
      />
      <Route
        path="/admin/models"
        element={
          <Administrative>
            <AdminModelsPage />
          </Administrative>
        }
      />
      <Route
        path="/admin/activity"
        element={
          <Administrative>
            <AdminActivityPage />
          </Administrative>
        }
      />

      {/* Convenience redirects */}
      <Route path="/admin/dashboard" element={<Navigate to="/admin" replace />} />
      <Route path="/admin/stats" element={<Navigate to="/admin" replace />} />

      {/* Not found */}
      <Route
        path="*"
        element={
          <AppLayout>
            <NotFoundPage />
          </AppLayout>
        }
      />
    </Routes>
  );
}
