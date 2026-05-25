from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict

import matplotlib.pyplot as plt
import pandas as pd

from icon.client.api.helpers.notebook import in_notebook
from icon.server.api.models.experiment_dict import ExperimentMetadata
from icon.server.data_access.models.sqlite.job import timezone

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from icon.client.client import Client
    from icon.server.api.models.experiment_dict import (
        ExperimentDict,
    )
    from icon.server.api.models.parameter_metadata import (
        ParameterMetadata,
    )

logger = logging.getLogger(__name__)


class ScanParameter(TypedDict):
    parameter: ParameterProxy | str
    """A ParameterProxy object retrieved from the API, or the parameter identifier. """
    values: list[Any]
    """List of explicit values to scan."""
    device_name: str | None
    """Name of the device this parameter belongs to. None if variable lives in
    InfluxDB."""


def get_experiment_identifier_dict(experiments: list[str]) -> dict[str, str]:
    """Processes a list of experiment strings to create a dictionary of unique identifiers.

    The keys are unique identifiers:
    - If the instance name (within brackets) is unique, it is used as the key.
    - If not, the instance name is appended with the class name to make it unique.

    The values are the original full names from the input list.

    Args:
        experiments:
            List of experiment strings in the format 'path.to.ClassName (InstanceName)'.

    Returns:
        A dictionary where keys are unique identifiers and values are the full names.
    """
    # Extract instance names and track their counts
    instance_names = [entry.split("(")[-1].strip(")") for entry in experiments]
    instance_counts = Counter(instance_names)

    # Create the result dictionary
    identifier_dict = {}

    for entry in experiments:
        full_name, instance_name = entry.rsplit("(", 1)
        instance_name = instance_name.strip(")")
        class_name = full_name.split(".")[-1].strip()

        # Determine unique identifier
        if instance_counts[instance_name] == 1:
            unique_identifier = instance_name
        else:
            unique_identifier = f"{instance_name} ({class_name})"

        # Add to the dictionary
        identifier_dict[unique_identifier] = entry

    return identifier_dict


def get_display_group_identifier_dict(display_groups: list[str]) -> dict[str, str]:
    """Map short display-name keys to full display-group keys.

    ``'experiment_library.globals.global_parameters (Doppler Cooling)'``
    becomes ``'Global Parameters (Doppler Cooling)'``.  When the short class
    name collides across namespaces, the parent module is prepended to keep
    keys unique.

    Args:
        display_groups: Full display-group key strings as returned by the server.

    Returns:
        Dict mapping short identifiers to full keys.
    """

    def _parse(key: str) -> tuple[str, str]:
        namespace, _, instance = key.rpartition(" (")
        return namespace, instance.rstrip(")")

    def _short(namespace: str, instance: str) -> str:
        class_part = namespace.rsplit(".", 1)[-1].replace("_", " ").title()
        return f"{class_part} ({instance})"

    def _longer(namespace: str, instance: str) -> str:
        parts = namespace.split(".")
        if len(parts) >= 2:  # noqa: PLR2004
            prefix = parts[-2].replace("_", " ").title()
            class_part = parts[-1].replace("_", " ").title()
            return f"{prefix} {class_part} ({instance})"
        return f"{namespace} ({instance})"

    short_names = [_short(*_parse(k)) for k in display_groups]
    counts = Counter(short_names)

    result: dict[str, str] = {}
    for key in display_groups:
        namespace, instance = _parse(key)
        short = _short(namespace, instance)
        result[short if counts[short] == 1 else _longer(namespace, instance)] = key

    return result


def get_parameter_identifier_mapping(
    display_group_metadata: dict[str, ParameterMetadata],
) -> dict[str, str]:
    parameter_id_mapping: dict[str, str] = {}
    for parameter_id, parameter_metadata in display_group_metadata.items():
        parameter_id_mapping[parameter_metadata["display_name"]] = parameter_id
    return parameter_id_mapping


class ParameterProxy:
    def __init__(
        self, client: Client, parameter_id: str, parameter_metadata: ParameterMetadata
    ) -> None:
        self._client = client
        self._parameter_metadata = parameter_metadata
        self._parameter_id = parameter_id

    @property
    def value(self) -> Any:
        return self._client.trigger_method(
            "parameters.get_parameter_by_id",
            kwargs={
                "parameter_id": self._parameter_id,
            },
        )

    @value.setter
    def value(self, value: Any) -> None:
        self._client.trigger_method(
            "parameters.update_parameter_by_id",
            kwargs={
                "parameter_id": self._parameter_id,
                "value": value,
            },
        )

    def __repr__(self) -> str:
        return (
            f"<Parameter: {self._parameter_metadata['display_name']}>\n"
            f"    id={self._parameter_id}\n"
            f"    default={self._parameter_metadata['default_value']}\n"
            f"    min={self._parameter_metadata['min_value']}\n"
            f"    max={self._parameter_metadata['max_value']}\n"
        )


class DisplayGroupProxy:
    def __init__(
        self,
        client: Client,
        display_group_name: str,
        display_group_metadata: dict[str, ParameterMetadata],
    ) -> None:
        self._client = client
        self._display_group_metadata = display_group_metadata
        self._display_group_name = display_group_name
        self._parameter_id_mapping = get_parameter_identifier_mapping(
            self._display_group_metadata
        )

    def __getitem__(self, parameter_name: str) -> Any:
        parameter_id = self._parameter_id_mapping[parameter_name]

        return ParameterProxy(
            self._client, parameter_id, self._display_group_metadata[parameter_id]
        )

    def __setitem__(self, parameter_name: str, value: Any) -> Any:
        parameter_id = self._parameter_id_mapping[parameter_name]

        return self._client.trigger_method(
            "parameters.update_parameter_by_id",
            kwargs={
                "parameter_id": parameter_id,
                "value": value,
            },
        )

    def __repr__(self) -> str:
        repr = f"<{self._display_group_name}>"

        for parameter_id in self._display_group_metadata:
            repr += (
                f"\n    - {self._display_group_metadata[parameter_id]['display_name']}"
            )
        return repr


class ExperimentJobProxy:
    def __init__(self, *, client: Client, job_id: int) -> None:
        self._client = client
        self._job_id = job_id
        self._getting_data = False
        self._client._sio.on(f"experiment_{self._job_id}", self._handle_live_data_point)

    @property
    def job_id(self) -> int:
        return self._job_id

    @property
    def status(self) -> str:
        """High-level job status: 'submitted', 'processing', or 'processed'."""
        job_dict: dict[str, Any] = self._client.trigger_method(
            "scheduler.get_job_by_id",
            kwargs={"job_id": self._job_id},
        )
        return str(job_dict["status"])

    @property
    def run_status(self) -> str | None:
        """Run-level status: 'pending', 'processing', 'done', 'failed', or 'cancelled'.

        Returns None if no run record exists yet (job still queued).
        """
        try:
            run_dict: dict[str, Any] = self._client.trigger_method(
                "scheduler.get_job_run_by_id",
                kwargs={"job_id": self._job_id},
            )
            return str(run_dict["status"])
        except Exception:
            return None

    @property
    def run_log(self) -> str | None:
        """Failure or cancellation message from the run, or None if no message."""
        try:
            run_dict: dict[str, Any] = self._client.trigger_method(
                "scheduler.get_job_run_by_id",
                kwargs={"job_id": self._job_id},
            )
            return run_dict.get("log") or None
        except Exception:
            return None

    @property
    def data(self) -> pd.DataFrame | None:
        """Accumulated experiment data received so far, or None if no data yet."""
        return self._client._experiment_job_data.get(self._job_id)

    def wait(self, poll_interval: float = 2.0) -> None:
        """Block until the job is done, then raise if it failed or was cancelled.

        Args:
            poll_interval: Seconds between status polls.

        Raises:
            RuntimeError: If the run finished with status 'failed' or 'cancelled'.
        """
        while self.status != "processed":
            time.sleep(poll_interval)
        terminal_run_status = self.run_status
        if terminal_run_status in ("failed", "cancelled"):
            log = self.run_log or "(no log)"
            raise RuntimeError(f"Job {self._job_id} {terminal_run_status}:\n{log}")

    def cancel(self) -> None:
        """Cancel this job. No-op if already processed."""
        self._client.trigger_method(
            "scheduler.cancel_job",
            kwargs={"job_id": self._job_id},
        )

    def toggle_plot(self) -> None:
        """Start live plotting if idle, stop it if already running."""
        if not self._getting_data:
            self._start_plot()
        else:
            self._stop_plot()

    def _start_plot(self) -> None:
        self._getting_data = True
        asyncio.run_coroutine_threadsafe(
            self._subscribe_to_experiment_data_stream(),
            self._client._loop,
        ).result()

    def _stop_plot(self) -> None:
        self._getting_data = False
        asyncio.run_coroutine_threadsafe(
            self._unsubscribe_from_experiment_data_stream(),
            self._client._loop,
        ).result()

    async def _subscribe_to_experiment_data_stream(self) -> None:
        self._client._sio.on(f"experiment_{self._job_id}", self._handle_live_data_point)
        self._client._loop.create_task(self._run_plot())

    async def _unsubscribe_from_experiment_data_stream(self) -> None:
        self._client._sio.handlers.get("/", {}).pop(f"experiment_{self._job_id}", None)

    async def _handle_live_data_point(self, data_point: dict[str, Any]) -> None:
        row = {
            **data_point.get("scan_params", {}),
            **data_point.get("result_channels", {}),
        }
        df_new = pd.DataFrame([row], index=[data_point["index"]])
        existing = self._client._experiment_job_data.get(self._job_id)
        if existing is None:
            self._client._experiment_job_data[self._job_id] = df_new
        else:
            self._client._experiment_job_data[self._job_id] = pd.concat(
                [existing, df_new]
            )

    async def _run_plot(self) -> None:
        self._fig, self._ax = plt.subplots()
        (self._line,) = self._ax.plot([], [], "r-")
        self._ax.grid()
        plt.ion()
        plt.show()

        async for data_frame in self._get_frame():
            self._update_plot(data_frame)
            if in_notebook():
                self._fig.canvas.draw_idle()
            else:
                self._fig.canvas.flush_events()
            await asyncio.sleep(0.01)

        self._getting_data = False
        await self._unsubscribe_from_experiment_data_stream()

    async def _get_frame(self) -> AsyncGenerator[pd.DataFrame | None, None]:
        previous_length = 0
        while self._getting_data:
            current_data = self._client._experiment_job_data.get(self._job_id)
            current_length = len(current_data.index) if current_data is not None else 0
            if current_length > previous_length:
                previous_length = current_length
                yield current_data
            else:
                await asyncio.sleep(0.1)

    def _update_plot(self, data_frame: pd.DataFrame | None) -> None:
        if data_frame is not None:
            self._line.set_data(data_frame.iloc[:, 0], data_frame.iloc[:, 1])
            if not self._ax.get_xlabel():
                self._ax.set_xlabel(data_frame.columns[0])
                self._ax.set_ylabel(data_frame.columns[1])
            self._ax.relim()
            self._ax.autoscale_view()

    def __repr__(self) -> str:
        return f"<ExperimentJobProxy job_id={self._job_id}>"


class ExperimentProxy:
    def __init__(
        self,
        client: Client,
        experiment_id: str,
        experiment_metadata: ExperimentMetadata,
    ) -> None:
        self._client = client
        self._experiment_id = experiment_id
        self._experiment_metadata = experiment_metadata

    def __repr__(self) -> str:
        repr = (
            f"<{self._experiment_metadata.constructor_kwargs['name']}> (Experiment: "
            f"{self._experiment_metadata.class_name})\n"
            f"  Display Groups:"
        )
        for display_group in self._experiment_metadata.parameters:
            repr += f"\n    - {display_group}"

        return repr

    def __iter__(self):
        for name in self._experiment_metadata.parameters:
            yield DisplayGroupProxy(
                self._client,
                name,
                self._experiment_metadata.parameters[name],
            )

    def __getitem__(self, display_group_name: str) -> Any:
        return DisplayGroupProxy(
            self._client,
            display_group_name,
            self._experiment_metadata.parameters[display_group_name],
        )

    def schedule(
        self,
        *,
        scan_parameters: list[ScanParameter] | None = None,
        priority: int = 20,
        repetitions: int = 1,
        number_of_shots: int = 50,
        local_parameters_timestamp: datetime | None = None,
        git_commit_hash: str | None = None,
        auto_calibration: bool = False,
    ) -> ExperimentJobProxy:
        """Schedule an experiment scan.

        Args:
            scan_parameters:
                A list of dictionaries where each dictionary defines a scan parameter
                and its values. Each dictionary should include:
                    - 'parameter': A ParameterProxy object retrieved from the API.
                    - 'values': Either a dictionary with 'start', 'stop', and
                        'num_points' keys or a list of explicit values.
                    - 'device_name': Name of the remote device as defined in Icon. None
                        if the parameter lives in InfluxDB.
            priority:
                Priority level of the experiment (default: 20).
            repetitions:
                Number of repetitions for the experiment to average over (default: 1).
            number_of_shots:
                Number of hardware shots per scan point (default: 50).
            local_parameters_timestamp:
                Timestamp of the local parameters to be used. Defaults to the current
                time.
            git_commit_hash:
                Git commit hash of the experiment library. If None is provided, it will
                take the latest commit on the main/master branch. Defaults to None.
            auto_calibration:
                Defines whether the parameter fits defined by the experiment should be
                applied automatically.

        Returns:
            ExperimentJobProxy: Proxy object for the scheduled experiment job.
        """
        if scan_parameters is None:
            scan_parameters = []
        if local_parameters_timestamp is None:
            local_parameters_timestamp = datetime.now(tz=timezone)
        job_id: int = self._client.trigger_method(
            "scheduler.submit_job",
            kwargs={
                "experiment_id": self._experiment_id,
                "scan_parameters": [
                    {
                        "id": parameter["parameter"]
                        if isinstance(parameter["parameter"], str)
                        else parameter["parameter"]._parameter_id,
                        "values": parameter["values"],
                        **(
                            {"device_name": parameter["device_name"]}
                            if parameter.get("device_name") is not None
                            else {}
                        ),
                    }
                    for parameter in scan_parameters
                ],
                "priority": priority,
                "local_parameters_timestamp": local_parameters_timestamp,
                "repetitions": repetitions,
                "number_of_shots": number_of_shots,
                "git_commit_hash": git_commit_hash,
                "auto_calibration": auto_calibration,
            },
        )
        return ExperimentJobProxy(client=self._client, job_id=job_id)


class ExperimentsController:
    def __init__(self, client: Client) -> None:
        self._client = client
        self._experiments: ExperimentDict = {
            key: ExperimentMetadata(**val)
            for key, val in self._client.trigger_method(
                "experiments.get_experiments"
            ).items()
        }
        self._experiments_id_mapping = get_experiment_identifier_dict(
            list(self._experiments.keys())
        )

    def __repr__(self) -> str:
        repr = "<Experiments>\n"
        for experiment in sorted(self._experiments_id_mapping):
            repr += f"  - {experiment}\n"
        return repr

    def __getitem__(self, key: str) -> ExperimentProxy:
        experiment_id = self._experiments_id_mapping.get(key, None)
        if experiment_id:
            return ExperimentProxy(
                self._client, experiment_id, self._experiments[experiment_id]
            )

        raise KeyError(f"There is no experiment with id {key}")
