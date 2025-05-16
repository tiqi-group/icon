import { Outlet } from "react-router";
import { DashboardLayout } from "@toolpad/core/DashboardLayout";
import { PageContainer } from "@toolpad/core/PageContainer";

export default function Layout() {
  return (
    <DashboardLayout defaultSidebarCollapsed sidebarExpandedWidth="200px">
      {/* <PageContainer style={{ maxWidth: "100%", paddingLeft: "0" }}> */}
      <Outlet />
      {/* </PageContainer> */}
    </DashboardLayout>
  );
}
