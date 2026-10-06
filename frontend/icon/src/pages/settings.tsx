import {
  Tabs,
  Tab,
  Typography,
  Paper,
  IconButton,
  Stack,
  Box,
  Select,
  MenuItem,
  CircularProgress,
  Tooltip,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import { useConfiguration } from "../hooks/useConfiguration";
import { Configuration } from "../types/Configuration";
import { EditableSettingField } from "../components/settings/EditableSettingsField";
import { ReachabilityIndicator } from "../components/devices/ReachabilityIndicator";
import { HardwareStatus } from "../components/statusCards/HardwareStatus";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { useDialogs, useNotifications } from "@toolpad/core";
import { useSearchParams } from "react-router";
import { EditableDictField } from "../components/settings/EditableDictField";
import { BaseButton } from "../components/parameterComponents/BaseButton";
import { updateConfiguration } from "../utils/updateConfiguration";
import { useBrowserSetting } from "../hooks/useBrowserSetting";
import { Input } from "../components/parameterComponents/Input";
import { useEffect, useState } from "react";

export const DEFAULT_WINDOW_SIZE = 1000;

type DeviceConfig = Configuration["hardware"]["devices"][number];

const HARDWARE_CONTROLLERS: Pick<
  DeviceConfig,
  "controller_module" | "controller_class" | "args"
>[] = [
  {
    controller_module: "icon.server.hardware_processing.zedboard_controller",
    controller_class: "ZedboardController",
    args: { host: "localhost", port: 6007 },
  },
  {
    controller_module: "icon.server.hardware_processing.fastino_controller",
    controller_class: "FastinoController",
    args: {},
  },
  {
    controller_module: "icon.server.hardware_processing.hardware_controller",
    controller_class: "FallbackHardwareController",
    args: { device_id: "FallbackHardware" },
  },
];

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => (
  <div hidden={value !== index} role="tabpanel">
    {value === index && (
      <div style={{ paddingLeft: 24, paddingRight: 24, paddingTop: 16 }}>
        {children}
      </div>
    )}
  </div>
);

const tabLabels = [
  "data",
  "date",
  "databases",
  "experiment-library",
  "hardware",
  "health-check",
  "server",
  "browser",
];

export const SettingsPage = () => {
  const config = useConfiguration();
  const { hardwareStatus } = useSystemStatus();

  const [prevConfig, setPrevConfig] = useState(config);
  const [outdatedStatus, setOutdatedStatus] = useState<HardwareStatus[]>();
  if (config !== prevConfig) {
    setPrevConfig(config);
    if (prevConfig) setOutdatedStatus(hardwareStatus);
  }
  const statusPending = outdatedStatus === hardwareStatus;
  const notifications = useNotifications();
  const dialogs = useDialogs();
  const [searchParams, setSearchParams] = useSearchParams();
  const [separateJobWindows, setSeparateJobWindows] = useBrowserSetting<boolean>(
    "separateJobWindows",
    false,
  );
  const [openExperimentWindows, setOpenExperimentWindows] = useBrowserSetting<boolean>(
    "openExperimentWindows",
    true,
  );
  const [openVisualizerInNewWindow, setOpenVisualizerInNewWindow] =
    useBrowserSetting<boolean>("openVisualizerInNewWindow", true);
  const [defaultWindowSize, setDefaultWindowSize] = useBrowserSetting<number>(
    "defaultWindowSize",
    DEFAULT_WINDOW_SIZE,
  );
  const [defaultWindowSizeInput, setDefaultWindowSizeInput] = useState(
    String(defaultWindowSize),
  );

  const updateDefaultWindowSize = (val: string) => {
    // An empty field resets the setting, invalid input keeps the current value.
    const num = val === "" ? DEFAULT_WINDOW_SIZE : Number(val);
    const newValue = Number.isInteger(num) && num >= 1 ? num : defaultWindowSize;
    setDefaultWindowSize(newValue);
    setDefaultWindowSizeInput(String(newValue));
  };

  const tabParam = searchParams.get("tab");
  let tab = tabParam ? tabLabels.indexOf(tabParam) : -1;
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSearchParams({ tab: tabLabels[newValue] });
  };

  useEffect(() => {
    if (tab === -1) {
      tab = 0;
      setSearchParams({ tab: tabLabels[tab] });
    }
  }, []);

  if (!config) return null;

  const updateDevices = async (devices: DeviceConfig[]) => {
    const err = await updateConfiguration("hardware.devices", devices);
    if (err instanceof Error) {
      notifications.show(`Failed to update configuration: ${err.message || err}`, {
        severity: "error",
      });
    }
  };

  const addDevice = (controllerIndex: number) =>
    updateDevices([
      ...config.hardware.devices,
      { id: "", ...HARDWARE_CONTROLLERS[controllerIndex], enabled: false },
    ]);

  const deleteDevice = async (index: number, name: string) => {
    const confirmed = await dialogs.confirm(
      `Remove "${name}" from the hardware configuration?`,
      { title: "Delete hardware", okText: "Delete", severity: "error" },
    );
    if (confirmed) {
      await updateDevices(config.hardware.devices.filter((_, i) => i !== index));
    }
  };

  return (
    <>
      <Tabs
        value={tab}
        onChange={handleTabChange}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        <Tab label="Data" />
        <Tab label="Date" />
        <Tab label="Databases" />
        <Tab label="Experiment Library" />
        <Tab label="Hardware" />
        <Tab label="Health Check" />
        <Tab label="Server" />
        <Tab label="Browser" />
      </Tabs>

      <Box sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <TabPanel value={tab} index={0}>
          <Typography variant="h6">Data</Typography>
          <EditableSettingField
            configKey="data.results_dir"
            label="Results directory"
            value={config.data.results_dir}
            description="The directory the results are written to."
          />
        </TabPanel>
        <TabPanel value={tab} index={1}>
          <Typography variant="h6">Date</Typography>
          <EditableSettingField
            configKey="date.timezone"
            label="Timezone"
            value={config.date.timezone}
            description="The system timezone used for logging and scheduling."
          />
        </TabPanel>
        <TabPanel value={tab} index={2}>
          <Typography variant="h6">InfluxDBv1</Typography>
          <EditableSettingField
            configKey="databases.influxdbv1.host"
            label="Host"
            value={config.databases.influxdbv1.host}
            description="Hostname or IP address of the InfluxDB v1 instance."
          />
          <EditableSettingField
            configKey="databases.influxdbv1.port"
            label="Port"
            value={config.databases.influxdbv1.port}
            description="Port number for the InfluxDB v1 instance."
          />
          <EditableSettingField
            configKey="databases.influxdbv1.username"
            label="Username"
            value={config.databases.influxdbv1.username}
            description="Username for authenticating with InfluxDB v1."
          />
          <EditableSettingField
            configKey="databases.influxdbv1.password"
            label="Password"
            value={config.databases.influxdbv1.password}
            description="Password for the specified InfluxDB user. For InfluxDB v2, use the API token here."
          />
          <EditableSettingField
            configKey="databases.influxdbv1.database"
            label="Database"
            value={config.databases.influxdbv1.database}
            description="Name of the InfluxDB v1 database to use."
          />
          <BaseButton
            label="SSL"
            description="Enable SSL for secure connection to InfluxDB."
            color={config.databases.influxdbv1.ssl === true ? "success" : "inherit"}
            onClick={() =>
              updateConfiguration(
                "databases.influxdbv1.ssl",
                !config.databases.influxdbv1.ssl,
              )
            }
          >
            {config.databases.influxdbv1.ssl == true ? "True" : "False"}
          </BaseButton>
          <BaseButton
            label="Verify SSL"
            description="Verify SSL certificates when connecting to InfluxDB."
            color={
              config.databases.influxdbv1.verify_ssl === true ? "success" : "inherit"
            }
            onClick={() =>
              updateConfiguration(
                "databases.influxdbv1.verify_ssl",
                !config.databases.influxdbv1.verify_ssl,
              )
            }
          >
            {config.databases.influxdbv1.verify_ssl == true ? "True" : "False"}
          </BaseButton>
          <EditableDictField
            configKey="databases.influxdbv1.headers"
            label="Headers"
            value={config.databases.influxdbv1.headers}
          />
          <br />
          <Typography variant="h6">SQLite</Typography>
          <EditableSettingField
            configKey="databases.sqlite.file"
            label="File"
            value={config.databases.sqlite.file}
            description="File path of the sqlite database."
          />
        </TabPanel>

        <TabPanel value={tab} index={3}>
          <Typography variant="h6">Experiment Library</Typography>
          <EditableSettingField
            configKey="experiment_library.update_interval"
            label="Update Interval"
            value={config.experiment_library.update_interval}
            description="Interval (in seconds) to check for experiment library updates."
          />
          <EditableSettingField
            configKey="experiment_library.client_class"
            label="Experiment Library Client Class (e.g. AsyncPyCrystalClient)"
            value={config.experiment_library.client_class}
            description="The experiment library client abstracts the interaction with an experiment library."
          />
          <Paper elevation={1}>
            <EditableDictField
              configKey="experiment_library.client_args"
              label="Experiment Library Configuration (client specific)"
              value={config.experiment_library.client_args}
            />
          </Paper>
        </TabPanel>
        <TabPanel value={tab} index={4}>
          <Typography variant="h6">Hardware</Typography>
          {config.hardware.devices.map((cfg, index) => {
            const status = statusPending ? undefined : hardwareStatus[index];
            const name = hardwareStatus[index]?.display_name ?? cfg.controller_class;
            return (
              <Paper
                key={`${config.hardware.devices.length}-${index}`}
                elevation={2}
                sx={{ padding: 2, marginBottom: 2, position: "relative" }}
              >
                <IconButton
                  title="Delete hardware"
                  onClick={() => deleteDevice(index, name)}
                  sx={{ position: "absolute", top: 8, right: 8 }}
                >
                  <DeleteIcon />
                </IconButton>
                <Stack direction="row" alignItems="center" sx={{ marginBottom: 2 }}>
                  {status ? (
                    <ReachabilityIndicator
                      enabled={status.enabled}
                      status={status.reachable}
                      errorMsg={status.error}
                    />
                  ) : (
                    <Tooltip title="Waiting for the next status update">
                      <CircularProgress size={15} sx={{ marginRight: 1 }} />
                    </Tooltip>
                  )}
                  <Typography variant="h6">{name}</Typography>
                </Stack>
                <BaseButton
                  label="Enabled"
                  description="Enable / Disable device."
                  color={cfg.enabled ? "success" : "inherit"}
                  onClick={() =>
                    updateConfiguration(
                      `hardware.devices[${index}].enabled`,
                      !cfg.enabled,
                    )
                  }
                >
                  {cfg.enabled ? "Enabled" : "Disabled"}
                </BaseButton>
                <EditableSettingField
                  configKey={`hardware.devices[${index}].controller_class`}
                  label="Hardware controller class (e.g. ZedboardHardwareController)"
                  value={cfg.controller_class}
                  description="Specifies the type of the hardware."
                />
                <EditableSettingField
                  configKey={`hardware.devices[${index}].controller_module`}
                  label="Hardware controller module (e.g. icon.server.hardware_processing.zedboard_controller)"
                  value={cfg.controller_module}
                  description="Python module which defines the hardware controller class."
                />
                <Paper elevation={1} sx={{ padding: 2, marginBottom: 2 }}>
                  <EditableDictField
                    configKey={`hardware.devices[${index}].args`}
                    label="Hardware Device Configuration (device specific)"
                    value={cfg.args}
                  />
                </Paper>
              </Paper>
            );
          })}
          <Stack direction="row" justifyContent="center" sx={{ marginBottom: 2 }}>
            <Select
              size="small"
              value=""
              displayEmpty
              renderValue={() => "Add Hardware Controller"}
              onChange={(e) => addDevice(Number(e.target.value))}
            >
              {HARDWARE_CONTROLLERS.map((controller, index) => (
                <MenuItem key={index} value={index}>
                  {`${controller.controller_class} (${controller.controller_module.split(".").pop()})`}
                </MenuItem>
              ))}
            </Select>
          </Stack>
        </TabPanel>
        <TabPanel value={tab} index={5}>
          <Typography variant="h6">Health Check</Typography>
          <EditableSettingField
            configKey="health_check.interval_seconds"
            label="Interval (s)"
            value={config.health_check.interval_seconds}
            description="Polling interval (in seconds) to check database and hardware availability."
          />
        </TabPanel>
        <TabPanel value={tab} index={6}>
          <Typography variant="h6">Icon Server</Typography>
          <EditableSettingField
            configKey="server.host"
            label="Host"
            value={config.server.host}
            description="Hostname of IP where the ICON backend server runs."
            onAfterUpdate={() =>
              notifications.show(
                "You have to restart ICON for the changes to take effect",
                { autoHideDuration: 3000, severity: "warning" },
              )
            }
          />
          <EditableSettingField
            configKey="server.port"
            label="Port"
            value={config.server.port}
            description="Port on which the ICON backend server listens."
            onAfterUpdate={() =>
              notifications.show(
                "You have to restart ICON for the changes to take effect",
                { autoHideDuration: 3000, severity: "warning" },
              )
            }
          />
          <Typography variant="h6">Pre-processing</Typography>
          <EditableSettingField
            configKey="server.pre_processing.workers"
            label="Number of Workers"
            value={config.server.pre_processing.workers}
            description="Number of pre-processing workers working on submitted experiment jobs."
            onAfterUpdate={() =>
              notifications.show(
                "You have to restart ICON for the changes to take effect",
                { autoHideDuration: 3000, severity: "warning" },
              )
            }
          />
        </TabPanel>
        <TabPanel value={tab} index={7}>
          <BaseButton
            label="Open Experiment Windows"
            description="Automatically open a job window when a new experiment is submitted."
            color={openExperimentWindows ? "success" : "inherit"}
            onClick={() => setOpenExperimentWindows(!openExperimentWindows)}
          >
            {openExperimentWindows ? "True" : "False"}
          </BaseButton>
          <BaseButton
            label="Use separate job windows"
            description="Open each job of the same experiment in a separate window."
            color={separateJobWindows ? "success" : "inherit"}
            onClick={() => setSeparateJobWindows(!separateJobWindows)}
          >
            {separateJobWindows ? "True" : "False"}
          </BaseButton>
          <BaseButton
            label="Open visualizer in new window"
            description="Open the sequence visualizer in a separate window instead of navigating to the Sequence page."
            color={openVisualizerInNewWindow ? "success" : "inherit"}
            onClick={() => setOpenVisualizerInNewWindow(!openVisualizerInNewWindow)}
          >
            {openVisualizerInNewWindow ? "True" : "False"}
          </BaseButton>
          <Input
            id="defaultWindowSize"
            label="Default window size"
            description={`Number of most recent data points shown in the plots of a job while its window size field is empty. Leave empty to reset to ${DEFAULT_WINDOW_SIZE}.`}
            type="number"
            min={10}
            value={defaultWindowSizeInput}
            onChange={setDefaultWindowSizeInput}
            onBlur={updateDefaultWindowSize}
          />
        </TabPanel>
      </Box>
    </>
  );
};
