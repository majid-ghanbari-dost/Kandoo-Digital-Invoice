"""Result shapes of the composed issuance surface — NOT new domain states.

Every field is either (a) the verbatim outcome object returned by a frozen
layer, or (b) a projection of that outcome computed here. No lifecycle state,
transition, act name, origin, identifier algorithm, dedup rule or policy value
is defined or redefined in this module.
"""
from dataclasses import dataclass
from typing import Optional

from pipeline.model import PipelineCompleted


@dataclass(frozen=True)
class IssuanceSubmission:
    """ONE submission result: the pipeline outcome VERBATIM + identity helpers.

    `pipeline` is exactly the `PipelineCompleted`/`PipelineStopped` object
    returned by the composed pipeline service — never converted, retried,
    rewritten or auto-advanced. `invoice_id`/`capture_id` are None while the
    corresponding durable identity does not exist yet.
    """
    pipeline: object
    invoice_id: Optional[str]
    capture_id: Optional[str]

    @property
    def completed(self) -> bool:
        """True ⇔ a durable Canonical Invoice exists for this submission.

        This is an execution fact about THIS call, not a lifecycle state and
        not an acceptance claim.
        """
        return isinstance(self.pipeline, PipelineCompleted)


@dataclass(frozen=True)
class DigitalInvoiceStatus:
    """Projection of ONE verified WP-10.1 read; `outcome` is retained verbatim.

    - `exists`        — a durable Digital Invoice row exists for `invoice_id`.
    - `verified`      — this read re-verified the Digital Invoice row, its
                        event chain AND the linked P6.2 chain inside this call
                        (verify-on-read). False means nothing may be trusted.
    - `current_state` — the frozen lifecycle state VERBATIM (AS-03); None means
                        "no state was delivered by this read" — it is NOT a
                        state name, and never a substitute for DRAFT.
    - `detail`        — the exact reason/issue text of the verbatim outcome
                        when `verified` is False; "" on a verified read.
    """
    invoice_id: str
    outcome: object
    exists: bool
    verified: bool
    digital_invoice_id: Optional[str]
    current_state: Optional[str]
    detail: str
