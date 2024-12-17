import pydantic


class ScanParameter(pydantic.BaseModel):
    remote_source: str
    variable_name: str
    scan_values: list[float]
