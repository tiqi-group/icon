import { Box, Typography } from "@mui/material";
import { useConfiguration } from "../hooks/useConfiguration";
import { EditableSettingField } from "../components/settings/EditableSettingsField";
import { BaseButtonComponent } from "../components/settings/ButtonComponent";

export const SettingsPage = () => {
  const config = useConfiguration();
  if (config == null) return null;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h6">Version</Typography>
      <Typography>{config.version}</Typography>

      <Typography variant="h6" sx={{ mt: 2 }}>
        Date
      </Typography>
      <Typography variant="subtitle2">Timezone</Typography>
      <Typography>{config.date.timezone}</Typography>

      <Typography variant="h6" sx={{ mt: 2 }}>
        Databases – InfluxDBv1
      </Typography>
      <EditableSettingField
        configKey="databases.influxdbv1.host"
        label="Host"
        value={config.databases.influxdbv1.host}
      />
      <EditableSettingField
        configKey="databases.influxdbv1.port"
        label="Port"
        value={config.databases.influxdbv1.port}
      />
      <EditableSettingField
        configKey="databases.influxdbv1.username"
        label="Username"
        value={config.databases.influxdbv1.username}
      />
      <EditableSettingField
        configKey="databases.influxdbv1.password"
        label="Password"
        value={config.databases.influxdbv1.password}
      />
      <EditableSettingField
        configKey="databases.influxdbv1.database"
        label="Database"
        value={config.databases.influxdbv1.database}
      />
      <BaseButtonComponent
        id="databases.influxdbv1.ssl"
        label="SSL"
        value={config.databases.influxdbv1.ssl}
      />
      <Typography variant="subtitle2">SSL</Typography>
      <Typography>{String(config.databases.influxdbv1.ssl)}</Typography>
      <Typography variant="subtitle2">Verify SSL</Typography>
      <Typography>{String(config.databases.influxdbv1.verify_ssl)}</Typography>
      <Typography variant="subtitle2">Headers</Typography>
      <Typography>{JSON.stringify(config.databases.influxdbv1.headers)}</Typography>

      <Typography variant="h6" sx={{ mt: 2 }}>
        Experiment Library
      </Typography>
      <Typography variant="subtitle2">Directory</Typography>
      <Typography>{config.experiment_library.dir}</Typography>
      <Typography variant="subtitle2">Git Repository</Typography>
      <Typography>{config.experiment_library.git_repository}</Typography>
      <Typography variant="subtitle2">Update Interval</Typography>
      <Typography>{config.experiment_library.update_interval}</Typography>

      <Typography variant="h6" sx={{ mt: 2 }}>
        Hardware
      </Typography>
      <Typography variant="subtitle2">Host</Typography>
      <Typography>{config.hardware.host}</Typography>
      <Typography variant="subtitle2">Port</Typography>
      <Typography>{config.hardware.port}</Typography>

      <Typography variant="h6" sx={{ mt: 2 }}>
        Health Check
      </Typography>
      <Typography variant="subtitle2">Interval (s)</Typography>
      <Typography>{config.health_check.interval_seconds}</Typography>

      <Typography variant="h6" sx={{ mt: 2 }}>
        Server
      </Typography>
      <Typography variant="subtitle2">Host</Typography>
      <Typography>{config.server.host}</Typography>
      <Typography variant="subtitle2">Port</Typography>
      <Typography>{config.server.port}</Typography>
    </Box>
  );
};
