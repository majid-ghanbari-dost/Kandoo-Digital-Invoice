"""kandoo.src.corpus — WP-12.1 Corpus Assembly (P12 Pilot layer).

SYNTHETIC pilot corpus material with declared ground-truth labels. This
package is pilot/evidence INPUT — never a production dependency (SPEC-WP121
§2.3: no production package may import it; the only sanctioned consumer is
the WP-12.2 calibration layer). It touches no production domain store,
ratifies no threshold (D-07/D-08), and runs no frozen pipeline.
"""
from .model import (  # noqa: F401
    CORPUS_MARKINGS,
    CORPUS_ORIGINS,
    ENTRY_TAG,
    FINGERPRINT_ALGORITHM_ID,
    LABEL_KIND_ABSENT,
    LABEL_KIND_VALUE,
    LABEL_KINDS,
    LABEL_PROVENANCE_DECLARED,
    MANIFEST_TAG,
    MARKING_SYNTHETIC,
    MAX_ENTRIES,
    ORIGIN_SYNTHETIC,
    CorpusAssembled,
    CorpusDuplicateVersion,
    CorpusEntry,
    CorpusInputRefused,
    CorpusLabel,
    CorpusLayerError,
    CorpusManifest,
    CorpusNotFound,
    CorpusReadIntegrityFailure,
    CorpusReadRefused,
    CorpusReadSuccess,
    CorpusReplay,
    CorpusStorageUnavailable,
    CorpusTemplateUnknown,
    CorpusVerificationUnavailable,
)
from .store import CorpusStore  # noqa: F401
from .service import CorpusAssemblyService  # noqa: F401

__all__ = [
    "CORPUS_MARKINGS",
    "CORPUS_ORIGINS",
    "ENTRY_TAG",
    "FINGERPRINT_ALGORITHM_ID",
    "LABEL_KIND_ABSENT",
    "LABEL_KIND_VALUE",
    "LABEL_KINDS",
    "LABEL_PROVENANCE_DECLARED",
    "MANIFEST_TAG",
    "MARKING_SYNTHETIC",
    "MAX_ENTRIES",
    "ORIGIN_SYNTHETIC",
    "CorpusAssembled",
    "CorpusAssemblyService",
    "CorpusDuplicateVersion",
    "CorpusEntry",
    "CorpusInputRefused",
    "CorpusLabel",
    "CorpusLayerError",
    "CorpusManifest",
    "CorpusNotFound",
    "CorpusReadIntegrityFailure",
    "CorpusReadRefused",
    "CorpusReadSuccess",
    "CorpusReplay",
    "CorpusStore",
    "CorpusStorageUnavailable",
    "CorpusTemplateUnknown",
    "CorpusVerificationUnavailable",
]
