class RunnerError(Exception):
    """A user-facing pipeline error."""


class AdapterError(RunnerError):
    """A tool/model adapter failed or is not configured."""
