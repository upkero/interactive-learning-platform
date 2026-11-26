"""Document data required by the progress stream."""

from dataclasses import dataclass
from typing import Literal

from src.app.contracts.documents.document_record import DocumentRecord

RunOutcome = Literal["ready", "failed"]


@dataclass(frozen=True, slots=True)
class ReadableDocument:
    document: DocumentRecord
    owner_locale: str
    # Outcome of the current generation run (parts with index >=
    # generation_start_index). The synthetic ``document_done`` after a lost
    # Redis Stream must not claim success when the last run produced nothing.
    run_outcome: RunOutcome
