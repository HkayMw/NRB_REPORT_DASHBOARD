"""Configurable monthly-report layout.

The report is defined as *groups* (bands on the week sheets, e.g. NID, CRVS),
each holding up to two *blocks* (side-by-side columns, e.g. IDs CAPTURED /
IDs DISTRIBUTED). Each block has *rows*; a row sums one or more form fields.
Rows and block totals can be flagged into the Report Summary sheet with a
`summary_label`. Anything not referenced is simply ignored by the report.

This default reproduces the office's existing workbook exactly (decoded from
its SUMIFS formulas). Admins can edit the stored config from the app.
"""

from nrb import db

SETTING_KEY = "report_config"

DEFAULT_REPORT_CONFIG = {
    "groups": [
        {
            "title": "NATIONAL IDENTITY (NID)",
            "summary_title": "NID",
            "blocks": [
                {
                    "title": "IDs CAPTURED",
                    "rows": [
                        {"label": "NEW APPLICANTS",
                         "fields": ["New applicants captured"],
                         "summary_label": "NEW APPLICANTS"},
                        {"label": "RENEWALS",
                         "fields": ["Expired  IDs processed"],
                         "summary_label": "RENEWALS"},
                        {"label": "REPLACEMENTS",
                         "fields": ["Damaged  IDs processed",
                                    "Defaced  IDs processed",
                                    "Lost  IDs processed"],
                         "summary_label": "REPLACEMENTS"},
                        {"label": "EDITS",
                         "fields": ["Edits processed"],
                         "summary_label": "EDITS"},
                    ],
                    "total_label": "TOTAL IDs CAPTURED",
                    "total_summary_label": None,
                },
                {
                    "title": "IDs DISTRIBUTED",
                    "rows": [
                        {"label": "NEW",
                         "fields": ["New applicants  IDs distributed"],
                         "summary_label": None},
                        {"label": "EXPIRED",
                         "fields": ["Renewed  IDs distributed"],
                         "summary_label": None},
                        {"label": "LOST",
                         "fields": ["Replaced Lost  IDs distributed"],
                         "summary_label": None},
                        {"label": "DAMAGED",
                         "fields": ["Replaced Damaged  IDs distributed",
                                    "Replaced Defaced  IDs distributed",
                                    "Edited IDs distributed"],
                         "summary_label": None},
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
                        {"label": "ENTERED",
                         "fields": ["NR8 forms entered"],
                         "summary_label": "NR8 FORMS ENTERED"},
                        {"label": "APPROVED",
                         "fields": ["NR8 forms approved"],
                         "summary_label": "APPROVED"},
                        {"label": "CERTs ISSUED",
                         "fields": ["Birth certificates issued"],
                         "summary_label": "BIRTH CERTIFICATES ISSUED"},
                        {"label": "NR8 FORMS COLLECTED",
                         "fields": ["NR8 forms collected"],
                         "summary_label": "NR8 FORMS COLLECTED"},
                    ],
                    "total_label": None,
                    "total_summary_label": None,
                },
                {
                    "title": "DEATH CERTIFICATE APPLICATIONS",
                    "rows": [
                        {"label": "ENTERED",
                         "fields": ["NR10 forms entered"],
                         "summary_label": "NR10 FORMS ENTERED"},
                        {"label": "APPROVED",
                         "fields": ["NR10 forms approved"],
                         "summary_label": "NR10 APPROVED"},
                        {"label": "CERTs ISSUED",
                         "fields": ["Death certificates issued"],
                         "summary_label": "DEATH CERTIFICATES ISSUED"},
                        {"label": "IDs RETRIEVED FROM DECEASED",
                         "fields": ["Deceased IDs retrieved"],
                         "summary_label": None},
                        {"label": "NR10 FORMS COLLECTED",
                         "fields": ["NR10 forms collected"],
                         "summary_label": "NR10 FORMS COLLECTED"},
                    ],
                    "total_label": None,
                    "total_summary_label": None,
                },
            ],
        },
    ]
}


def get_report_config():
    return db.get_setting(SETTING_KEY, DEFAULT_REPORT_CONFIG)


def save_report_config(cfg):
    errors = validate(cfg)
    if errors:
        raise ValueError("; ".join(errors))
    db.set_setting(SETTING_KEY, cfg)


def validate(cfg) -> list:
    from nrb import config
    errors = []
    groups = cfg.get("groups")
    if not isinstance(groups, list) or not groups:
        return ["Config must contain a non-empty 'groups' list."]
    for gi, g in enumerate(groups):
        if not g.get("title"):
            errors.append(f"Group {gi + 1}: missing title.")
        blocks = g.get("blocks", [])
        if not blocks or len(blocks) > 2:
            errors.append(f"Group '{g.get('title', gi + 1)}': needs 1–2 blocks.")
        for b in blocks:
            if not b.get("title"):
                errors.append(f"Group '{g.get('title')}': block missing title.")
            for r in b.get("rows", []):
                if not r.get("label"):
                    errors.append(f"Block '{b.get('title')}': row missing label.")
                for f in r.get("fields", []):
                    if f not in config.ALL_NUMERIC_FIELDS:
                        errors.append(
                            f"Row '{r.get('label')}': unknown form field '{f}'.")
                if not r.get("fields"):
                    errors.append(f"Row '{r.get('label')}': no source fields.")
    return errors


def row_value(df, fields) -> int:
    """Sum the given form fields over an already-filtered DataFrame."""
    total = 0
    for f in fields:
        if f in df.columns:
            total += int(df[f].fillna(0).sum())
    return total


def compute_block(df, block) -> dict:
    rows = [(r["label"], row_value(df, r["fields"])) for r in block.get("rows", [])]
    return {"rows": rows, "total": sum(v for _, v in rows)}


def summary_columns(cfg) -> list:
    """Flattened summary columns: [(group_summary_title, label, ref)] where
    ref = (group_idx, block_idx, row_idx | 'total')."""
    cols = []
    for gi, g in enumerate(cfg["groups"]):
        gtitle = g.get("summary_title") or g["title"]
        for bi, b in enumerate(g["blocks"]):
            for ri, r in enumerate(b.get("rows", [])):
                if r.get("summary_label"):
                    cols.append((gtitle, r["summary_label"], (gi, bi, ri)))
            if b.get("total_summary_label"):
                cols.append((gtitle, b["total_summary_label"], (gi, bi, "total")))
    return cols
