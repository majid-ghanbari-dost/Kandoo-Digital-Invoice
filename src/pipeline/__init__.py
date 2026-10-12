"""Python API for additive reference capture-to-canonical execution (Issue #4)."""
from .model import (PipelineCompleted, PipelineStopped, PipelineExecutionError,
                    StageOutcome)
from .service import PipelineService
from .workspace import PipelineWorkspace

__all__ = ["PipelineWorkspace", "PipelineService", "PipelineCompleted",
           "PipelineStopped", "PipelineExecutionError", "StageOutcome"]
