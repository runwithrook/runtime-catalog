#!/usr/bin/env python3
"""Attest built runtime catalog documents with a shared provenance predicate."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


BUILD_REPORT_NAME = "build-report.json"
CHANNEL_INDEX_NAME = "runtime-channels.json"
DEFAULT_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"


class CatalogAttestationError(RuntimeError):
    """Raised when catalog attestation fails."""


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogAttestationError(f"file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogAttestationError(f"failed to parse JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CatalogAttestationError(f"expected a JSON object in {path}")
    return payload


def _catalog_documents(catalog_dir: Path) -> list[Path]:
    report = _read_json(catalog_dir / BUILD_REPORT_NAME)
    documents = [catalog_dir / CHANNEL_INDEX_NAME]
    for item in report.get("manifests") or []:
        if not isinstance(item, dict):
            continue
        relative = str(item.get("path") or "").strip()
        if relative:
            documents.append(catalog_dir / relative)
    return documents


def _predicate(*, builder_identity: str, source_repo: str, source_ref: str, document_path: str) -> dict:
    return {
        "builder_identity": builder_identity,
        "build_definition": {
            "source_repo": source_repo,
            "ref": source_ref,
            "document_path": document_path,
        },
    }


def _run(command: list[str]) -> None:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CatalogAttestationError(detail or f"command failed: {' '.join(command)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-dir", default="catalog")
    parser.add_argument("--builder-identity", required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--predicate-type", default=DEFAULT_PREDICATE_TYPE)
    parser.add_argument("--cosign-bin", default="cosign")
    args = parser.parse_args()

    catalog_dir = Path(args.catalog_dir).expanduser().resolve()
    documents = _catalog_documents(catalog_dir)
    for document in documents:
        if not document.exists():
            raise CatalogAttestationError(f"catalog document does not exist: {document}")
        predicate_path = document.parent / f"{document.name}.predicate.json"
        predicate_path.write_text(
            json.dumps(
                _predicate(
                    builder_identity=str(args.builder_identity),
                    source_repo=str(args.source_repo),
                    source_ref=str(args.source_ref),
                    document_path=document.relative_to(catalog_dir).as_posix(),
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            _run(
                [
                    str(args.cosign_bin),
                    "attest-blob",
                    "--yes",
                    "--predicate",
                    str(predicate_path),
                    "--type",
                    str(args.predicate_type),
                    "--bundle",
                    str(document.parent / f"{document.name}.intoto.sigstore.json"),
                    "--output-attestation",
                    str(document.parent / f"{document.name}.intoto.jsonl"),
                    str(document),
                ]
            )
        finally:
            predicate_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
