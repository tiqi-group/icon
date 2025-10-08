from icon.server.api.models.scan_parameter import (
    DatabaseParameter,
    RealtimeParameter,
    scan_parameter_from_dict,
)


def test_scan_parameter_from_dict_detects_realtime() -> None:
    payload = {
        "n_scan_points": 1,
    }
    parameter = scan_parameter_from_dict(payload)
    expected_parameter = RealtimeParameter(
        n_scan_points=1,
    )

    assert parameter == expected_parameter


def test_scan_parameter_from_dict_detects_database_parameter() -> None:
    payload = {
        "id": "namespace='experiment_library.globals.global_parameters' "
        "parameter_group='Detection' param_type='ParameterTypes.FREQUENCY'",
        "values": [0, 1],
    }
    parameter = scan_parameter_from_dict(payload)

    expected_parameter = DatabaseParameter(
        id="namespace='experiment_library.globals.global_parameters' "
        "parameter_group='Detection' param_type='ParameterTypes.FREQUENCY'",
        values=[0.0, 1.0],
    )

    assert parameter == expected_parameter
