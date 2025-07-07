import { Outlet } from "react-router";
import { DashboardLayout } from "@toolpad/core/DashboardLayout";

export default function Layout() {
  return (
    <DashboardLayout defaultSidebarCollapsed sidebarExpandedWidth="200px">
      <Outlet />
    </DashboardLayout>
  );
}
