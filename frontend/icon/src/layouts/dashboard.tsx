import { DashboardLayout } from "@toolpad/core/DashboardLayout";
import { Outlet } from "react-router";
import { useControlState } from "../hooks/useControlState";
import { ToolbarActionsTakeControl } from "./toolbar-actions/TakeControl";
import { OverlayLock } from "../components/OverlayLock";

export default function Layout() {
  const { controllingSid, socketioSID } = useControlState();

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
      <Outlet />
    </DashboardLayout>
  );
}
