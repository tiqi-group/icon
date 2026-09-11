import { createContext } from "react";
import {
  GroupsByNamespace,
  NamespaceToGroups,
} from "../hooks/useParameterDisplayGroups";

export const ParameterDisplayGroupsContext = createContext<{
  parameterDisplayGroups: GroupsByNamespace;
  parameterNamespaceToDisplayGroups: NamespaceToGroups;
}>({
  parameterDisplayGroups: {},
  parameterNamespaceToDisplayGroups: {},
});
