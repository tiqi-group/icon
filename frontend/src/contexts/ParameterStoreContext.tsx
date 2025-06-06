import React, { createContext } from "react";
import { Store } from "../stores/parmeterStore";

export const ParameterStoreContext = createContext<Store | null>(null);

export const ParameterStoreProvider = ({
  store,
  children,
}: {
  store: Store;
  children: React.ReactNode;
}) => (
  <ParameterStoreContext.Provider value={store}>
    {children}
  </ParameterStoreContext.Provider>
);
