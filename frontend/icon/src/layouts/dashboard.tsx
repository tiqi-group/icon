import { DashboardLayout } from "@toolpad/core/DashboardLayout";
import { Navigate, Outlet } from "react-router";
import { useControlState } from "../hooks/useControlState";
import { ToolbarActionsTakeControl } from "./toolbar-actions/TakeControl";
import { OverlayLock } from "../components/OverlayLock";
import { useRestoredPageUrl } from "../hooks/useRestoredPageUrl";

export default function Layout() {
  const { controllingSid, socketioSID } = useControlState();
  const restoredPageUrl = useRestoredPageUrl();

  const isLockedByOther = controllingSid !== null && controllingSid !== socketioSID;

  return (
    <DashboardLayout
      defaultSidebarCollapsed
      sidebarExpandedWidth="200px"
      slots={{
        toolbarActions: ToolbarActionsTakeControl,
      }}
    >
      <OverlayLock isLockedByOther={isLockedByOther} />
      {restoredPageUrl ? <Navigate to={restoredPageUrl} replace /> : <Outlet />}
    </DashboardLayout>
  );
}
