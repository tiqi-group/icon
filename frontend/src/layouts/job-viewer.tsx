import { Outlet } from "react-router";
import { DashboardLayout } from "@toolpad/core/DashboardLayout";
import { ReactRouterAppProvider } from "@toolpad/core/react-router";
import { BRANDING } from "../App";

export default function JobViewerLayout() {
  return (
    <ReactRouterAppProvider branding={BRANDING}>
      <DashboardLayout hideNavigation>
        <Outlet />
      </DashboardLayout>
    </ReactRouterAppProvider>
  );
}
