"""Execution results, not new invoice/gate/lifecycle states."""
from dataclasses import dataclass
from typing import Optional, Tuple

from canonical_assembly import AssemblyReadSuccess, AssemblyTraceSuccess


@dataclass(frozen=True)
class StageOutcome:
    stage: str
    outcome: object


@dataclass(frozen=True)
class PipelineStopped:
    """The exact upstream outcome, including REVIEW/REJECT, is retained."""
    stage: str
    outcome: object
    capture_id: Optional[str]
    steps: Tuple[StageOutcome, ...]


@dataclass(frozen=True)
class PipelineCompleted:
    """Canonical invoice verified by both read and whole-chain trace.

    Does NOT mean digital issuance, product acceptance or business posting.
    """
    capture_id: str
    invoice: AssemblyReadSuccess
    trace: AssemblyTraceSuccess
    steps: Tuple[StageOutcome, ...]


class PipelineExecutionError(RuntimeError):
    """Unexpected exception; completed durable stages are NOT rolled back.

    The original exception is available as __cause__. Retry identical input
    after fixing the cause; frozen service replay semantics remain authoritative.
    """
    def __init__(self, stage, capture_id, steps):
        super().__init__(f"pipeline execution failed at {stage}")
        self.stage = stage
        self.capture_id = capture_id
        self.steps = tuple(steps)
