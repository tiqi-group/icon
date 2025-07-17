import * as React from "react";
import * as ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import App from "./App";
import Layout from "./layouts/dashboard";
import DashboardPage from "./pages";
import ExperimentsPage from "./pages/experiments";
import ParameterPage from "./pages/parameters";
import { DataPage } from "./pages/data";
import DevicesPage from "./pages/devices";
import { SettingsPage } from "./pages/settings";
import JobViewerLayout from "./layouts/job-viewer";
import { JobViewerPage } from "./pages/job-viewer";

const router = createBrowserRouter([
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

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
