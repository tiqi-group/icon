import * as React from "react";
import * as ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import App from "./App";
import Layout from "./layouts/dashboard";
import DashboardPage from "./pages";
import ExperimentsPage from "./pages/experiments";
import ParameterPage from "./pages/parameters";
import { PlotPage } from "./pages/plot";
import { DataPage } from "./pages/data";

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
        ],
      },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
