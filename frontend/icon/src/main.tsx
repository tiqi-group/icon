import * as React from "react";
import * as ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import App from "./App";
import Layout from "./layouts/dashboard";
import DashboardPage from "./pages";
import ExperimentsPage from "./pages/experiments";
import ParameterPage from "./pages/parameters";
import { DataPage } from "./pages/data";
import { VisualiserPage } from "./pages/visualiser";
import DevicesPage from "./pages/devices";
import { SettingsPage } from "./pages/settings";
import JobViewerLayout from "./layouts/job-viewer";
import { JobViewerPage } from "./pages/job-viewer";
import { UserStyle } from "./components/UserStyle";
import { applyUserStyle, getStoredUserStyle } from "./utils/userStyle";

const router = createBrowserRouter([
  {
    path: "/data/:jobId/plot/:kind/:plotIndex",
    HydrateFallback: () => <p role="status">Loading plot...</p>,
    lazy: async () => {
      const { PlotViewerPage } = await import("./features/plot-viewer/PlotViewerPage");
      return { Component: PlotViewerPage };
    },
  },
  {
    Component: App,
    children: [
      {
        path: "/",
        Component: Layout,
        children: [
          {
            path: "",
            Component: DashboardPage,
          },
          {
            path: "parameters",
            Component: ParameterPage,
          },
          {
            path: "experiments",
            Component: ExperimentsPage,
          },
          {
            path: "data",
            Component: DataPage,
          },
          {
            path: "devices",
            Component: DevicesPage,
          },
          {
            path: "sequence",
            Component: VisualiserPage,
          },
          {
            path: "settings",
            Component: SettingsPage,
          },
        ],
      },
    ],
  },
  {
    path: "/data/:jobId",
    Component: JobViewerLayout,
    children: [
      {
        index: true,
        Component: JobViewerPage,
      },
    ],
  },
]);

// Load the user style before the first render so the page does not change its look
// right after it appears. A style that is slow to load must not hold the app back.
const STYLE_LOAD_TIMEOUT_MS = 1000;

void Promise.race([
  applyUserStyle(getStoredUserStyle()),
  new Promise((resolve) => setTimeout(resolve, STYLE_LOAD_TIMEOUT_MS)),
]).then(() =>
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <UserStyle />
      <RouterProvider router={router} />
    </React.StrictMode>,
  ),
);
