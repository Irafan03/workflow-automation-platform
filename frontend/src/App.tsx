import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { Dashboard } from '@/pages/Dashboard'
import { WorkflowStudio } from '@/pages/WorkflowStudio'
import { SettingsPage } from '@/pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Studio gets its own full-screen layout (no sidebar) */}
        <Route path="/studio/:id" element={<WorkflowStudio />} />

        {/* Everything else uses the sidebar layout */}
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="/settings" element={<SettingsPage />} />
          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
