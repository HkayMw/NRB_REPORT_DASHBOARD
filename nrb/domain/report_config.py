"""Pure validation and calculations for monthly report layouts."""

import pandas as pd

from nrb import config


DEFAULT_REPORT_CONFIG = {
    "groups": [
        {
            "title": "NATIONAL IDENTITY (NID)",
            "summary_title": "NID",
            "blocks": [
                {
                    "title": "IDs CAPTURED",
                    "rows": [
                        {
                            "label": "NEW APPLICANTS",
                            "fields": ["New applicants captured"],
                            "summary_label": "NEW APPLICANTS",
                        },
                        {
                            "label": "RENEWALS",
                            "fields": ["Expired  IDs processed"],
                            "summary_label": "RENEWALS",
                        },
                        {
                            "label": "REPLACEMENTS",
                            "fields": [
                                "Damaged  IDs processed",
                                "Defaced  IDs processed",
                                "Lost  IDs processed",
                            ],
                            "summary_label": "REPLACEMENTS",
                        },
                        {
                            "label": "EDITS",
                            "fields": ["Edits processed"],
                            "summary_label": "EDITS",
                        },
                    ],
                    "total_label": "TOTAL IDs CAPTURED",
                    "total_summary_label": None,
                },
                {
                    "title": "IDs DISTRIBUTED",
                    "rows": [
                        {
                            "label": "NEW",
                            "fields": ["New applicants  IDs distributed"],
                            "summary_label": None,
                        },
                        {
                            "label": "EXPIRED",
                            "fields": ["Renewed  IDs distributed"],
                            "summary_label": None,
                        },
                        {
                            "label": "LOST",
                            "fields": ["Replaced Lost  IDs distributed"],
                            "summary_label": None,
                        },
                        {
                            "label": "DAMAGED",
                            "fields": [
                                "Replaced Damaged  IDs distributed",
                                "Replaced Defaced  IDs distributed",
                                "Edited IDs distributed",
                            ],
                            "summary_label": None,
                        },
                    ],
                    "total_label": "TOTAL NIDS ISSUED",
                    "total_summary_label": "NIDS ISSUED",
                },
            ],
        },
        {
            "title": "CIVIL REGISTRATION AND VITAL STATISTICS (CRVS)",
            "summary_title": "CRVS",
            "blocks": [
                {
                    "title": "BIRTH CERTIFICATE APPLICATIONS",
                    "rows": [
                        {
                            "label": "ENTERED",
                            "fields": ["NR8 forms entered"],
                            "summary_label": "NR8 FORMS ENTERED",
                        },
                        {
                            "label": "APPROVED",
                            "fields": ["NR8 forms approved"],
                            "summary_label": "APPROVED",
                        },
                        {
                            "label": "CERTs ISSUED",
                            "fields": ["Birth certificates issued"],
                            "summary_label": "BIRTH CERTIFICATES ISSUED",
                        },
                        {
                            "label": "NR8 FORMS COLLECTED",
                            "fields": ["NR8 forms collected"],
                            "summary_label": "NR8 FORMS COLLECTED",
                        },
                    ],
                    "total_label": None,
                    "total_summary_label": None,
                },
                {
                    "title": "DEATH CERTIFICATE APPLICATIONS",
                    "rows": [
                        {
                            "label": "ENTERED",
                            "fields": ["NR10 forms entered"],
                            "summary_label": "NR10 FORMS ENTERED",
                        },
                        {
                            "label": "APPROVED",
                            "fields": ["NR10 forms approved"],
                            "summary_label": "NR10 APPROVED",
                        },
                        {
                            "label": "CERTs ISSUED",
                            "fields": ["Death certificates issued"],
                            "summary_label": "DEATH CERTIFICATES ISSUED",
                        },
                        {
                            "label": "IDs RETRIEVED FROM DECEASED",
                            "fields": ["Deceased IDs retrieved"],
                            "summary_label": None,
                        },
                        {
                            "label": "NR10 FORMS COLLECTED",
                            "fields": ["NR10 forms collected"],
                            "summary_label": "NR10 FORMS COLLECTED",
                        },
                    ],
                    "total_label": None,
                    "total_summary_label": None,
                },
            ],
        },
    ]
}


def _generic_layout(cfg: dict) -> dict:
    """Demo copy of the layout with office-specific form codes renamed."""
    groups = []
    for group in cfg["groups"]:
        blocks = []
        for block in group["blocks"]:
            rows = [
                {
                    **row,
                    "label": config.DEMO_LABEL_RENAMES.get(row["label"], row["label"]),
                    "fields": [
                        config.DEMO_FIELD_RENAMES.get(f, f) for f in row["fields"]
                    ],
                    "summary_label": config.DEMO_LABEL_RENAMES.get(
                        row["summary_label"], row["summary_label"]
                    ),
                }
                for row in block["rows"]
            ]
            blocks.append({**block, "rows": rows})
        groups.append({**group, "blocks": blocks})
    return {"groups": groups}


if config.DEMO_MODE:
    DEFAULT_REPORT_CONFIG = _generic_layout(DEFAULT_REPORT_CONFIG)


def validate(cfg) -> list:
    errors = []
    groups = cfg.get("groups")
    if not isinstance(groups, list) or not groups:
        return ["Config must contain a non-empty 'groups' list."]
    for gi, group in enumerate(groups):
        if not group.get("title"):
            errors.append(f"Group {gi + 1}: missing title.")
        blocks = group.get("blocks", [])
        if not blocks or len(blocks) > 2:
            errors.append(f"Group '{group.get('title', gi + 1)}': needs 1–2 blocks.")
        for block in blocks:
            if not block.get("title"):
                errors.append(f"Group '{group.get('title')}': block missing title.")
            for row in block.get("rows", []):
                if not row.get("label"):
                    errors.append(f"Block '{block.get('title')}': row missing label.")
                for field in row.get("fields", []):
                    if field not in config.ALL_NUMERIC_FIELDS:
                        errors.append(
                            f"Row '{row.get('label')}': unknown form field '{field}'."
                        )
                if not row.get("fields"):
                    errors.append(f"Row '{row.get('label')}': no source fields.")
    return errors


def row_value(df: pd.DataFrame, fields: list) -> int:
    """Sum the given form fields over an already-filtered DataFrame."""
    total = 0
    for field in fields:
        if field in df.columns:
            total += int(df[field].fillna(0).sum())
    return total


def compute_block(df: pd.DataFrame, block: dict) -> dict:
    rows = [
        (row["label"], row_value(df, row["fields"])) for row in block.get("rows", [])
    ]
    return {"rows": rows, "total": sum(value for _, value in rows)}


def summary_columns(
    cfg: dict,
) -> list[tuple[str, str, tuple[int, int, int | str]]]:
    """Flatten summary columns to (group title, label, source reference)."""
    columns: list[tuple[str, str, tuple[int, int, int | str]]] = []
    for group_index, group in enumerate(cfg["groups"]):
        group_title = group.get("summary_title") or group["title"]
        for block_index, block in enumerate(group["blocks"]):
            for row_index, row in enumerate(block.get("rows", [])):
                if row.get("summary_label"):
                    columns.append(
                        (
                            group_title,
                            row["summary_label"],
                            (group_index, block_index, row_index),
                        )
                    )
            if block.get("total_summary_label"):
                columns.append(
                    (
                        group_title,
                        block["total_summary_label"],
                        (group_index, block_index, "total"),
                    )
                )
    return columns
