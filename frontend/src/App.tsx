import { useEffect } from 'react';
import { Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { Dashboard } from '@/pages/Dashboard';
import { ReplayStudio } from '@/pages/ReplayStudio';
import { AlertsPage } from '@/pages/AlertsPage';
import { EmployeesPage } from '@/pages/EmployeesPage';
import { EmployeeDetail } from '@/pages/EmployeeDetail';
import { GraphExplorer } from '@/pages/GraphExplorer';
import { SettingsPage } from '@/pages/SettingsPage';
import { ToastViewport, toast } from '@/components/ui/Toast';
import { hawkeyeWs } from '@/lib/ws';

export default function App() {
  // App-level WebSocket subscription: surface every new alert as a toast
  useEffect(() => {
    hawkeyeWs.connect();
    const unsub = hawkeyeWs.subscribe((msg) => {
      if (msg.type === 'alert.new' && msg.alert) {
        const a = msg.alert;
        toast(`New ${a.risk_level} alert · ${a.employee_id}`, {
          body: a.top_signal ?? undefined,
          variant:
            a.risk_level === 'CRITICAL'
              ? 'critical'
              : a.risk_level === 'HIGH'
              ? 'alert'
              : 'info',
        });
      }
    });
    return () => {
      unsub();
    };
  }, []);

  return (
    <>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="alerts"          element={<AlertsPage />} />
          <Route path="employees"       element={<EmployeesPage />} />
          <Route path="employees/:id"   element={<EmployeeDetail />} />
          <Route path="graph"           element={<GraphExplorer />} />
          <Route path="replay"          element={<ReplayStudio />} />
          <Route path="settings"        element={<SettingsPage />} />
        </Route>
      </Routes>
      <ToastViewport />
    </>
  );
}
