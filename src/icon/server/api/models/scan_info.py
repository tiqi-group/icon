import pydantic


class ScanParameter(pydantic.BaseModel):
    remote_source: str
    variable_name: str
    scan_values: list[float]


class ScanInfo(pydantic.BaseModel):
    scan_parameters: list[ScanParameter]
    auto_calibration: bool
