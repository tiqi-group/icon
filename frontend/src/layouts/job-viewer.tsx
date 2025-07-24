import { Outlet } from "react-router";
import { ReactRouterAppProvider } from "@toolpad/core/react-router";
import { BRANDING } from "../App";

export default function JobViewerLayout() {
  return (
    <ReactRouterAppProvider branding={BRANDING}>
      <Outlet />
    </ReactRouterAppProvider>
  );
}
