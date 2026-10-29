import hashlib
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert

from .config import FIELDS, MAX_BYTES, Profile
from .db import Attempt, Batch, Duplicate, Quarantine, RawRecord, Review, Sale, now, sessions
from .input import InputError, parse_csv
from .quality import canonical, correct, money

OUTCOMES = ("accepted_valid", "accepted_corrected", "quarantined", "excluded_duplicate")


class Pipeline:
    def __init__(self, db):
        self.db = db
        self.session = sessions(db)

    def submit(self, content: bytes, filename: str, profile: Profile):
        if len(content) > MAX_BYTES:
            raise InputError("File exceeds 5 MiB upload limit")
        digest = hashlib.sha256(content).hexdigest()
        key = hashlib.sha256(f"{digest}:{profile.name}:{profile.fingerprint}".encode()).hexdigest()
        with self.session.begin() as s:
            s.execute(insert(Batch).values(submission_key=key, file_hash=digest,
                filename=filename[:500], content=content, profile=asdict(profile), config_hash=profile.fingerprint,
                status="pending").on_conflict_do_nothing(index_elements=["submission_key"]))
            batch_id = s.scalar(select(Batch.id).where(Batch.submission_key == key))
        self.process(batch_id)
        return batch_id

    def process(self, batch_id):
        start = time.monotonic()
        try:
            with self.session.begin() as s:
                b = s.scalar(select(Batch).where(Batch.id == batch_id))
                if b is None:
                    raise ValueError("Unknown batch")
                if b.status == "completed":
                    return
                profile = Profile(**{**b.profile, "date_formats": tuple(b.profile["date_formats"])})
                if profile.fingerprint != b.config_hash:
                    raise RuntimeError("Configuration changed; resubmit under current version instead of retrying")
                parsed = parse_csv(b.content, profile)
                b.schema_info = {"unknown_columns": parsed.unknown_columns, "mappings": parsed.mappings}
                if not s.scalar(select(RawRecord.id).where(RawRecord.batch_id == b.id).limit(1)):
                    for raw, mapped, line in zip(parsed.raw, parsed.mapped, parsed.line_numbers):
                        s.add(RawRecord(batch_id=b.id, source_line=line, original=raw, mapped=mapped))
                b.status, b.error, b.error_kind = "processing", None, None
            with self.session.begin() as s:
                # Serialize acceptance decisions with manual review and other ingestions.
                b = s.scalar(select(Batch).where(Batch.id == batch_id))
                if b.status == "completed":
                    return
                rows = list(s.scalars(select(RawRecord).where(RawRecord.batch_id == batch_id).order_by(RawRecord.source_line)))
                results = {}
                groups = defaultdict(list)
                for raw in rows:
                    values, initial, issues, attempts = correct(raw.mapped, profile)
                    schema_attempts = [
                        {"field": f"column:{target}", "original": source, "proposed": target,
                         "rule_id": "column_mapping", "rule_version": "1.0.0",
                         "reason": "declared column alias and/or surrounding header whitespace",
                         "applied": True, "revalidation_ok": not issues}
                        for source, target in b.schema_info["mappings"].items()
                        if source != target and target in FIELDS
                    ]
                    attempts = schema_attempts + attempts
                    raw.current, raw.initial_issues = values, initial
                    raw.validity = "invalid" if issues else ("corrected" if any(a["applied"] for a in attempts) else "valid")
                    results[raw.id] = (values, issues)
                    for attempt in attempts:
                        s.add(Attempt(batch_id=batch_id, raw_id=raw.id, **attempt))
                    if values["transaction_id"]:
                        groups[values["transaction_id"]].append(raw)
                # Conflicts include invalid siblings: do not pick a winner by validation order.
                conflicts = set()
                for group in groups.values():
                    if len({self.signature(results[r.id][0]) for r in group}) > 1:
                        for raw in group:
                            conflicts.add(raw.id)
                            related = next(r for r in group if self.signature(results[r.id][0]) != self.signature(results[raw.id][0]))
                            s.add(Duplicate(raw_id=raw.id, related_raw_id=related.id, kind="conflict_in_batch", reason="same transaction_id, different normalized content"))
                representatives = {}
                for raw in rows:
                    values, issues = results[raw.id]
                    issues = list(issues)
                    if raw.id in conflicts:
                        issues.append({"field": "transaction_id", "reason": "conflicting rows in this batch; review all versions"})
                    if issues:
                        self.quarantine(s, raw, values, issues)
                        continue
                    signature = self.signature(values)
                    if signature in representatives:
                        related = representatives[signature]
                        self.duplicate(s, raw, related, "exact_in_batch")
                        continue
                    representatives[signature] = raw.id
                    self.accept_or_duplicate(s, raw, values)
                s.flush()
                b.status, b.finished_at = "completed", now()
                b.duration_seconds = str(round(time.monotonic() - start, 4))
        except Exception as exc:
            # The failed processing transaction rolls back all outputs; durable raw input remains.
            with self.session.begin() as s:
                b = s.get(Batch, batch_id)
                if b and b.status != "completed":
                    b.status, b.error_kind = "failed", "input" if isinstance(exc, InputError) else "operational"
                    b.error = str(exc)[:2000] if isinstance(exc, InputError) else f"{type(exc).__name__}: processing failed; see application log and retry"
                    b.finished_at, b.duration_seconds = now(), str(round(time.monotonic() - start, 4))
            raise

    @staticmethod
    def signature(values):
        return tuple(sorted(canonical(values).items()))

    @staticmethod
    def quarantine(s, raw, values, issues):
        raw.disposition, raw.outcome = "quarantine", "quarantined"
        s.add(Quarantine(raw_id=raw.id, values=values, issues=issues))

    @staticmethod
    def duplicate(s, raw, related_id, kind):
        raw.disposition, raw.outcome = "duplicate", "excluded_duplicate"
        s.add(Duplicate(raw_id=raw.id, related_raw_id=related_id, kind=kind, reason="identical normalized accepted content; lineage retained"))

    def accept_or_duplicate(self, s, raw, values):
        existing = s.get(Sale, values["transaction_id"])
        if existing:
            if canonical(values) == existing.normalized:
                self.duplicate(s, raw, existing.raw_id, "exact_existing")
            else:
                s.add(Duplicate(raw_id=raw.id, related_raw_id=existing.raw_id, kind="conflict_existing", reason="preserve existing accepted record"))
                self.quarantine(s, raw, values, [{"field": "transaction_id", "reason": "conflicts with previously accepted transaction; use a verified distinct key or reconcile upstream"}])
            return
        data = {f: values[f] for f in FIELDS}
        data.update(transaction_date=date.fromisoformat(values["transaction_date"]), quantity=int(values["quantity"]),
                    unit_price=money(values["unit_price"]), total_amount=money(values["total_amount"]))
        s.add(Sale(raw_id=raw.id, normalized=canonical(values), **data))
        s.flush()  # make accepted content visible to subsequent rows in the same transaction
        raw.disposition = "accepted"
        raw.outcome = "accepted_corrected" if raw.validity == "corrected" else "accepted_valid"

    def review(self, raw_id, edited: dict, actor: str):
        if not actor.strip() or len(actor) > 200:
            raise ValueError("A reviewer name (1–200 characters) is required")
        if set(edited) != set(FIELDS) or any(not isinstance(v, str) or len(v) > 10000 for v in edited.values()):
            raise ValueError("Review must supply all canonical fields as strings of at most 10,000 characters")
        with self.session.begin() as s:
            raw = s.scalar(select(RawRecord).where(RawRecord.id == raw_id))
            if raw is None or raw.outcome != "quarantined":
                raise ValueError("Only currently quarantined records may be reviewed")
            batch = s.get(Batch, raw.batch_id)
            profile = Profile(**{**batch.profile, "date_formats": tuple(batch.profile["date_formats"])})
            if profile.fingerprint != batch.config_hash:
                raise ValueError("Original rules/configuration changed; resubmit through a new batch")
            values, _, issues, attempts = correct(edited, profile)
            review = Review(raw_id=raw.id, actor=actor.strip(), before=raw.current, submitted=edited,
                            after=values, issues=issues, outcome="quarantined")
            s.add(review)
            s.flush()
            for attempt in attempts:
                s.add(Attempt(batch_id=batch.id, raw_id=raw.id, review_id=review.id, **attempt))
            raw.current, raw.validity = values, "invalid" if issues else "corrected"
            # Resolve prior quarantine snapshots, then append a fresh unresolved one if needed.
            s.execute(update(Quarantine).where(Quarantine.raw_id == raw.id, Quarantine.resolved_at.is_(None)).values(resolved_at=now()))
            if issues:
                self.quarantine(s, raw, values, issues)
            else:
                # Unresolved sibling conflicts still require explicit resolution. A reviewed row
                # may now win only because a human explicitly supplied this version.
                self.accept_or_duplicate(s, raw, values)
            s.flush()
            review.outcome = raw.outcome
            if raw.outcome == "quarantined":
                review.issues = s.scalars(select(Quarantine).where(Quarantine.raw_id == raw.id, Quarantine.resolved_at.is_(None))).one().issues
            return raw.outcome

    def summary(self, batch_id):
        with self.session() as s:
            batch = s.get(Batch, batch_id)
            if batch is None:
                raise ValueError("Unknown batch")
            rows = list(s.scalars(select(RawRecord).where(RawRecord.batch_id == batch_id)))
            counts = Counter(r.outcome for r in rows if r.outcome)
            return {"batch_id": batch_id, "status": batch.status, "input_rows": len(rows),
                    **{key: counts[key] for key in OUTCOMES}, "unprocessed": sum(r.outcome is None for r in rows),
                    "duration_seconds": batch.duration_seconds, "error": batch.error, "error_kind": batch.error_kind}
