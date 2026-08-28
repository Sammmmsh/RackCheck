"""Versioned, serializable contracts shared by collectors and diagnostics."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Observation:
    key: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    detail: str = ""

    def __post_init__(self):
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("Observation key must be a nonempty string")
        if self.status not in {"ok", "error", "unsupported"}:
            raise ValueError("Invalid observation status")
        if not isinstance(self.data, dict):
            raise ValueError("Observation data must be an object")
        if not isinstance(self.source, str) or not isinstance(self.detail, str):
            raise ValueError("Observation source and detail must be strings")
        try:
            json.dumps(self.data, allow_nan=False)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("Observation data must contain finite JSON values") from exc


@dataclass
class Snapshot:
    hostname: str
    platform: str
    observations: list[Observation]
    context: str = "live"
    collected_at: str = field(default_factory=utc_now)
    schema_version: int = 1

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported snapshot schema_version")
        if self.context not in {"live", "fixture", "lab"}:
            raise ValueError("Invalid snapshot context")
        if not isinstance(self.hostname, str) or not isinstance(self.platform, str) or not self.hostname or not self.platform:
            raise ValueError("Snapshot hostname and platform must be nonempty strings")
        if not isinstance(self.collected_at, str):
            raise ValueError("Snapshot collected_at must be an ISO timestamp")
        if datetime.fromisoformat(self.collected_at.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("Snapshot timestamps must include a timezone")
        if not isinstance(self.observations, list) or not all(isinstance(o, Observation) for o in self.observations):
            raise ValueError("Snapshot observations must be a list of observations")
        keys = [o.key for o in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate observation keys")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "Snapshot":
        if not isinstance(value, dict):
            raise ValueError("Snapshot must be an object")
        required = {"schema_version", "hostname", "platform", "context", "collected_at", "observations"}
        if set(value) != required or not isinstance(value["observations"], list):
            raise ValueError("Invalid or incomplete snapshot fields")
        try:
            return cls(**{**value, "observations": [Observation(**o) for o in value["observations"]]})
        except (TypeError, KeyError) as exc:
            raise ValueError("Invalid observation fields") from exc


@dataclass
class Finding:
    check_id: str
    category: str
    status: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    recovery: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.status not in {"PASS", "WARN", "FAIL", "UNKNOWN"}:
            raise ValueError("Invalid finding status")


@dataclass
class Report:
    snapshot: Snapshot
    findings: list[Finding]
    generated_at: str = field(default_factory=utc_now)

    @property
    def status(self) -> str:
        statuses = {f.status for f in self.findings}
        for status in ("FAIL", "UNKNOWN", "WARN"):
            if status in statuses:
                return status
        return "PASS" if statuses else "UNKNOWN"

    @property
    def exit_code(self) -> int:
        return {"PASS": 0, "WARN": 0, "FAIL": 1, "UNKNOWN": 2}[self.status]

    def to_dict(self) -> dict:
        return {
            "schema_version": 1, "generated_at": self.generated_at, "status": self.status,
            "counts": {s: sum(f.status == s for f in self.findings) for s in ("PASS", "WARN", "FAIL", "UNKNOWN")},
            "snapshot": self.snapshot.to_dict(), "findings": [asdict(f) for f in self.findings],
        }
