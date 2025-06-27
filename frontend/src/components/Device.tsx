import React, { useContext, useState } from "react";
import { Box, Typography, Button, TextField } from "@mui/material";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { DeviceStatus } from "../types/enums";
import { runMethod } from "../socket";
import EditIcon from "@mui/icons-material/Edit";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import { ReachabilityIndicator } from "./devices/ReachabilityIndicator";
import { ScannableParameterInterface } from "./devices/ScannableParameterInterface";

function websocketUrlToHttp(url: string): string {
  return url.replace(/^ws/, "http");
}

export const Device = React.memo(
  ({
    name,
    url,
    status,
    description,
    retry_attempts,
    retry_delay_seconds,
    reachable,
    view,
  }: {
    name: string;
    url: string;
    status: DeviceStatus;
    description: string | null;
    retry_attempts: number;
    retry_delay_seconds: number;
    reachable: boolean;
    view: "scannable" | "pydase";
  }) => {
    const [editingUrl, setEditingUrl] = useState(false);
    const infoContext = useContext(DeviceInfoContext);
    const deviceInfo = infoContext[name];

    const toggleStatus = () => {
      const newStatus = status === DeviceStatus.ENABLED ? "disabled" : "enabled";
      runMethod("devices.update_device", [], { name, status: newStatus });
    };

    const handleRetryAttemptsChange = (value: string) => {
      const parsed = parseInt(value);
      if (!Number.isNaN(parsed)) {
        runMethod("devices.update_device", [], {
          name,
          retry_attempts: parsed,
        });
      }
    };

    const handleRetryDelayChange = (value: string) => {
      const parsed = parseFloat(value);
      if (!Number.isNaN(parsed)) {
        runMethod("devices.update_device", [], {
          name,
          retry_delay_seconds: parsed,
        });
      }
    };

    const handleUrlSubmit = (newUrl: string) => {
      if (newUrl !== url) {
        runMethod("devices.update_device", [], {
          name,
          url: newUrl,
        });
      }
      setEditingUrl(false);
    };

    return (
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <ReachabilityIndicator
            enabled={status === DeviceStatus.ENABLED}
            reachable={reachable}
          />
          <Box
            sx={{
              flexGrow: 1,
              display: "flex",
              alignItems: "center",
              gap: 1,
              flexWrap: "wrap",
            }}
          >
            <Typography component="span" fontWeight="bold">
              {name}
            </Typography>

            {editingUrl ? (
              <TextField
                defaultValue={url}
                size="small"
                onBlur={(e) => handleUrlSubmit(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleUrlSubmit((e.target as HTMLInputElement).value);
                  } else if (e.key === "Escape") {
                    setEditingUrl(false);
                  }
                }}
                sx={{ width: "300px" }}
                autoFocus
              />
            ) : (
              <>
                <Typography component="span" color="text.secondary">
                  ({url}
                  <Tooltip
                    title={
                      status === DeviceStatus.ENABLED
                        ? "Disable the device to change the URL"
                        : "Edit URL"
                    }
                  >
                    <span>
                      <IconButton
                        size="small"
                        onClick={() => setEditingUrl(true)}
                        disabled={status === DeviceStatus.ENABLED}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  )
                </Typography>
              </>
            )}
          </Box>
          <Button
            size="small"
            variant="outlined"
            onClick={toggleStatus}
            sx={{ minWidth: "90px" }}
          >
            {status === DeviceStatus.ENABLED ? "Disable" : "Enable"}
          </Button>
        </Box>

        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ pl: 2.4 }}>
            {description}
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
          <TextField
            label="Retry Attempts"
            size="small"
            type="number"
            defaultValue={retry_attempts}
            onBlur={(e) => handleRetryAttemptsChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleRetryAttemptsChange((e.target as HTMLInputElement).value);
              }
            }}
            sx={{ width: "120px" }}
          />
          <TextField
            label="Retry Delay (s)"
            size="small"
            type="number"
            defaultValue={retry_delay_seconds}
            onBlur={(e) => handleRetryDelayChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleRetryDelayChange((e.target as HTMLInputElement).value);
              }
            }}
            sx={{ width: "140px" }}
          />
        </Box>
        {view === "scannable" ? (
          <ScannableParameterInterface name={name} />
        ) : deviceInfo.status === DeviceStatus.ENABLED ? (
          <iframe
            src={websocketUrlToHttp(deviceInfo.url)}
            style={{ width: "100%", height: "600px", border: "1px solid #ccc" }}
            title={`Pydase Interface for ${name}`}
          />
        ) : null}
      </Box>
    );
  },
);
