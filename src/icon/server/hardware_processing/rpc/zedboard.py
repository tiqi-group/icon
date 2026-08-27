from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Self, override

from icon.server.hardware_processing.rpc.client import MsgPackRPCClient
from icon.server.hardware_processing.rpc.errors import RFSoCError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from types import TracebackType

logger = logging.getLogger(__name__)

ParamVal = bool | int | float | str
ParamDescr = tuple[tuple[int, ParamVal], tuple[str, int, int, str, list[Any]]]
PageDescr = tuple[str, int, list[int]]


class Zedboard:
    """Direct RPC interface to the legacy experiment runtime on the Zedboard.

    Provides typed stateless methods for the following operations
      * read pages, parameters, channels, and remote action.
      * write parameters and invoke remote actions.
      * execute experiment with channel name resolution

    Intended to serve as a base class for specialized clients on top of the experiment
    runtime.

    **Note**: This is a compatibility module for the legacy Zedboard controller interface.
        The interface is deprecated and will be replaced in the future.
    """

    _client: MsgPackRPCClient

    def __init__(
        self,
        hostname: str = "zedboard.lab",
        port: int = 6007,
        timeout: float | None = 5,
    ) -> None:
        self._client = MsgPackRPCClient(
            hostname=hostname, port=port, timeout=timeout, framed=True
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[{self._client}]"

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.disconnect()

    def connect(self) -> None:
        """Establish a connection to the Zedboard.

        Raises:
            ConnectionRefusedError: if the peer does not accept the connection. Probably
                not listening.
            OSError: if the host cannot be reached or resolved.
        """
        self._client.connect()

    def disconnect(self) -> None:
        self._client.disconnect()

    @property
    def is_connected(self) -> bool:
        """Whether the underlying socket is up."""
        return self._client.is_connected

    def _invoke(self, method: str, *values: Any) -> Any:
        """Private wrapper for RPC invocations. Use specialized methods instead."""
        return self._client.call(method, *values)

    def get_pages(self) -> list[PageDescr]:
        """Returns page list. Position in the list is the page's id."""
        return self._invoke("pages")

    def get_params(self) -> list[ParamDescr]:
        """Returns global parameter list."""
        return self._invoke("params")

    def _get_channels(self, channel_type: str, page_id: int) -> list[str]:
        return [ch[0] for ch in self._invoke(channel_type, page_id)]

    def get_data_channels(self, page_id: int) -> list[str]:
        """Returns list of data channel names for the page."""
        return self._get_channels("dataChannels", page_id)

    def get_shot_channels(self, page_id: int) -> list[str]:
        """Returns list of shot channel names for the page."""
        return self._get_channels("shotChannels", page_id)

    def get_vector_channels(self, page_id: int) -> list[str]:
        """Returns list of vector channel names for the page."""
        return self._get_channels("vectorChannels", page_id)

    def get_remote_actions(self, page_id: int) -> list[str]:
        """Returns list of remote action names for the page. Position in the list is the action's id."""
        return self._invoke("remoteActions", page_id)

    def set_param(self, param_id: int, value: ParamVal) -> None:
        self.set_params([(param_id, value)])

    def set_params(self, params: Iterable[tuple[int, ParamVal]]) -> None:
        """Write several parameters in one round trip."""
        self._invoke("setParams", [[param_id, value] for param_id, value in params])

    def call_remote_action(self, page_id: int, action_id: int) -> Any:
        """Call remote action by page id and action id. See :meth:`get_remote_actions`."""
        return self._invoke("callRemoteAction", page_id, action_id)

    def _zip_channels(
        self, kind: str, page_id: int, names: list[str], values: Any
    ) -> dict[str, Any]:
        if values is None:
            raise RFSoCError(
                f"page {page_id} returned no {kind} channel data at all, but "
                f"{len(names)} channel name(s) are known: {names}"
            )
        try:
            return dict(zip(names, values, strict=True))
        except ValueError as e:
            raise RFSoCError(
                f"page {page_id}: device returned {len(values)} {kind} channel(s) but "
                f"{len(names)} name(s) are known ({names}). Either the RFSoC is "
                f"misconfigured, or the cached channel names are stale."
            ) from e

    def _result_channel_names(
        self, page_id: int
    ) -> tuple[list[str], list[str], list[str]]:
        """Data, shot and vector channel names for a page."""
        return (
            self.get_data_channels(page_id),
            self.get_shot_channels(page_id),
            self.get_vector_channels(page_id),
        )

    def run_experiment(self, page_id: int) -> ExperimentResult:
        """Run the experiment corresponding to the page.

        Channel names are resolved dynamically. This is required for experiments which
        build their channels dynamically (like the sequence runner experiment).
        """
        data_res, shot_res, vec_res = self._invoke("runExperiment", page_id)
        data_names, shot_names, vec_names = self._result_channel_names(page_id)
        return ExperimentResult(
            result_channels=self._zip_channels("data", page_id, data_names, data_res),
            shot_channels=self._zip_channels("shot", page_id, shot_names, shot_res),
            vector_channels=self._zip_channels("vector", page_id, vec_names, vec_res),
        )


@dataclass
class ExperimentResult:
    result_channels: dict[str, float] = field(default_factory=dict)
    vector_channels: dict[str, list[float]] = field(default_factory=dict)
    shot_channels: dict[str, list[int]] = field(default_factory=dict)


def _lookup_by_name[T](
    name: str, collection: Iterable[T], key: Callable[[T], str]
) -> T:
    try:
        return next(filter(lambda p: key(p) == name, collection))
    except StopIteration as e:
        raise RFSoCError(f"{name} does not exist on device") from e


class ZedboardSeqRunner(Zedboard):
    """Representation of the Sequence Runner Experiment on the Zedboard.

    On connect, the necessary configuration values for a sequence run are discovered once.

    Usage:

        zedboard = ZedboardSeqRunner(hostname="localhost", port=6000)
        zedboard.connect()

    The following steps are required for each sequence run:

        zedboard.load_sequence(seq_json)
        res = zedboard.run_sequence()
    """

    _SEQ_PAGE_NAME = "sequence JSON parser"
    _SEQ_PARAM_NAME = "Sequence JSON"

    _page_id: int
    """Page id for the sequence parser page."""
    _param_id: int
    """Parameter id for the JSON Sequence parameter."""

    @override
    def connect(self) -> None:
        """Connect to the device and discover configuration values."""
        super().connect()
        self._discover()

    @property
    def is_ready(self) -> bool:
        """Whether the socket is up and discovery has completed."""
        return self.is_connected and self._page_id is not None

    def _discover(self) -> None:
        """Discover the relevant page/parameter for the sequence runner.

        This is done only once after the connection is established.

        Raises:
            RFSoCError: if a required page/parameter/action could not be found.
              Most likely due to a misconfiguration on the device.
        """
        # Page: (name:str, flags:int, _param_ids:int[])
        page_id, (_, _, _param_ids) = _lookup_by_name(
            self._SEQ_PAGE_NAME, enumerate(self.get_pages()), lambda x: x[1][0]
        )

        # Param: ( (_param_id:int, value:any), (name:str, type:int, flags:int,
        #          tooltip:str, meta:any[]) )
        params = self.get_params()
        (param_id, _), _ = _lookup_by_name(
            self._SEQ_PARAM_NAME,
            (params[pid] for pid in _param_ids),
            lambda x: x[1][0],
        )

        self._page_id, self._param_id = page_id, param_id

    def load_sequence(self, sequence_json: str) -> None:
        """Transmit the sequence description to the device."""
        self.set_param(self._param_id, sequence_json)

    def run_sequence(self) -> ExperimentResult:
        """Execute the experiment, fetch the channel names and map the result data to the channels."""
        return self.run_experiment(self._page_id)


class ZedboardSeqRunnerCached(ZedboardSeqRunner):
    """Cached variant of ZedboardSeqRunner.

    By default, the run_experiment routine fetches the channel names after every
    experiment run. This is because the channel names are not known a priori as they are
    built according to the instructions in the sequence description.
    This Sequence Runner infers the channel names from the sequence description and allows to
    retrieve the channel names directly from the cache. This avoids three round trips to
    the device for querying the individual channel names. The assumption is that three
    round trips takes longer than decoding the sequence description.

    Usage:

    Identical to :class:`ZedboardSeqRunner`
    """

    class ChannelTypes(StrEnum):
        """Channel types as defined in the sequence description with the {ChannelTypes}_channel_names key."""

        READOUT = "readout"
        SHOT = "shot"
        VECTOR = "vector"

    _channel_names: dict[ChannelTypes, list[str]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.marker='"header":'
        self.marker_len = len(self.marker)

        self._channel_names = {t: [] for t in ZedboardSeqRunnerCached.ChannelTypes}

    @override
    def _result_channel_names(
        self, page_id: int
    ) -> tuple[list[str], list[str], list[str]]:
        """Serve the sequence runner's channel names from cache instead of the device.

        Raises:
            RFSoCError: if asked about any page other than the sequence page. The cache
                describes the loaded sequence, so it cannot answer for another page --
                and answering with it anyway would silently mislabel that page's results.
        """
        if page_id != self._page_id:
            raise RFSoCError(
                f"cached channel names describe page {self._page_id} (the sequence "
                f"runner), not page {page_id}"
            )
        return (
            self._channel_names[ZedboardSeqRunnerCached.ChannelTypes.READOUT],
            self._channel_names[ZedboardSeqRunnerCached.ChannelTypes.SHOT],
            self._channel_names[ZedboardSeqRunnerCached.ChannelTypes.VECTOR],
        )

    @override
    def load_sequence(self, sequence_json: str) -> None:
        """Update the cache with the new sequence description."""
        self._update_channel_names(sequence_json)
        super().load_sequence(sequence_json)

    def _update_channel_names(self, sequence_json: str) -> None:
        """Partially decode the header out of sequence_json to read the channel names.

        Fall back to full JSON decode if the partial decode fails.
        """
        try:
            hdr = json.JSONDecoder().raw_decode(sequence_json, sequence_json.index(self.marker) + self.marker_len )[0]
        except (json.decoder.JSONDecodeError, ValueError):
            logger.warning("Sequence description format unexpected. Expecting dense format with no spaces. Falling back to slow decoder.")
            try:
                hdr = json.loads(sequence_json).get("header",{})
            except json.decoder.JSONDecodeError as e:
                raise RFSoCError("Submitted sequence is not valid JSON. Can't run") from e

        for t in ZedboardSeqRunnerCached.ChannelTypes:
            self._channel_names[t] = hdr.get(f"{t}_channel_names", [])
