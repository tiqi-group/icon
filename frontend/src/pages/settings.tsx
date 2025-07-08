import { Box, Tabs, Tab, Typography } from "@mui/material";
import { useConfiguration } from "../hooks/useConfiguration";
import { EditableSettingField } from "../components/settings/EditableSettingsField";
import { BaseButtonComponent } from "../components/settings/ButtonComponent";
import { useNotifications } from "@toolpad/core";
import { useSearchParams } from "react-router";

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => (
  <div hidden={value !== index} role="tabpanel">
    {value === index && <Box sx={{ px: 3, pt: 2 }}>{children}</Box>}
  </div>
);

const tabLabels = [
  "date",
  "databases",
  "experiment-library",
  "hardware",
  "health-check",
  "server",
];

export const SettingsPage = () => {
  const config = useConfiguration();
  const notifications = useNotifications();
  const [searchParams, setSearchParams] = useSearchParams();

  const tabParam = searchParams.get("tab");
  let tab = tabParam ? tabLabels.indexOf(tabParam) : -1;

  if (tab === -1) {
    tab = 0;
    setSearchParams({ tab: tabLabels[tab] });
  }

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSearchParams({ tab: tabLabels[newValue] });
  };

  if (!config) return null;

  return (
    <Box>
      <Tabs
        value={tab}
        onChange={handleTabChange}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        <Tab label="Date" />
        <Tab label="Databases" />
        <Tab label="Experiment Library" />
        <Tab label="Hardware" />
        <Tab label="Health Check" />
        <Tab label="Server" />
      </Tabs>

      <TabPanel value={tab} index={0}>
        <Typography variant="h6">Date</Typography>
        <EditableSettingField
          configKey="date.timezone"
          label="Timezone"
          value={config.date.timezone}
          description="The system timezone used for logging and scheduling."
        />
      </TabPanel>
      <TabPanel value={tab} index={1}>
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
        <BaseButtonComponent
          id="databases.influxdbv1.ssl"
          label="SSL"
          value={config.databases.influxdbv1.ssl}
          description="Enable SSL for secure connection to InfluxDB."
        />
        <BaseButtonComponent
          id="databases.influxdbv1.verify_ssl"
          label="Verify SSL"
          value={config.databases.influxdbv1.verify_ssl}
          description="Verify SSL certificates when connecting to InfluxDB."
        />
        <Typography variant="subtitle2">Headers</Typography>
        <Typography>{JSON.stringify(config.databases.influxdbv1.headers)}</Typography>
      </TabPanel>

      <TabPanel value={tab} index={2}>
        <Typography variant="h6">Experiment Library</Typography>
        <EditableSettingField
          configKey="experiment_library.dir"
          label="Directory"
          value={config.experiment_library.dir}
          description="Root directory containing experiment source files."
        />
        <EditableSettingField
          configKey="experiment_library.git_repository"
          label="Git Repository"
          value={config.experiment_library.git_repository}
          description="Remote Git repository URL for pulling experiment definitions."
        />
        <EditableSettingField
          configKey="experiment_library.update_interval"
          label="Update Interval"
          value={config.experiment_library.update_interval}
          description="Interval (in seconds) to check for experiment library updates."
        />
      </TabPanel>
      <TabPanel value={tab} index={3}>
        <Typography variant="h6">Hardware</Typography>
        <EditableSettingField
          configKey="hardware.host"
          label="Host"
          value={config.hardware.host}
          description="Hostname or IP address for the hardware server."
        />
        <EditableSettingField
          configKey="hardware.port"
          label="Port"
          value={config.hardware.port}
          description="Port number used to communicate with the hardware server."
        />
      </TabPanel>
      <TabPanel value={tab} index={4}>
        <Typography variant="h6">Health Check</Typography>
        <EditableSettingField
          configKey="health_check.interval_seconds"
          label="Interval (s)"
          value={config.health_check.interval_seconds}
          description="Polling interval (in seconds) to check database and hardware availability."
        />
      </TabPanel>
      <TabPanel value={tab} index={5}>
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
      </TabPanel>
    </Box>
  );
};
