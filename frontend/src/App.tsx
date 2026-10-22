import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./lib/auth";
import Dashboard from "./pages/Dashboard";
import FolioPage from "./pages/FolioPage";
import Folios from "./pages/Folios";
import FrontDesk from "./pages/FrontDesk";
import Inventory from "./pages/Inventory";
import Invoice from "./pages/Invoice";
import Kitchen from "./pages/Kitchen";
import Laundry from "./pages/Laundry";
import Login from "./pages/Login";
import Pos from "./pages/Pos";
import Reports from "./pages/Reports";
import GuestRegister from "./pages/GuestRegister";
import Reservations from "./pages/Reservations";
import Rooms from "./pages/Rooms";
import Settings from "./pages/Settings";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/folios/:id/invoice" element={<RequireAuth><Invoice /></RequireAuth>} />
      <Route path="/reports/guest-register" element={<RequireAuth><GuestRegister /></RequireAuth>} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="front-desk" element={<FrontDesk />} />
        <Route path="reservations" element={<Reservations />} />
        <Route path="rooms" element={<Rooms />} />
        <Route path="folios" element={<Folios />} />
        <Route path="folios/:id" element={<FolioPage />} />
        <Route path="pos" element={<Pos />} />
        <Route path="kitchen" element={<Kitchen />} />
        <Route path="laundry" element={<Laundry />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
