"""Cleaning pipeline for form responses.

Rules (agreed with the office):
- Name is a multi-select: one submission can cover several staff members.
- A row is "clean" only when every selected name matches the roster
  (old free-text era rows are excluded by default).
- Duplicate = same (date, section, name-set); the latest submission wins
  (treated as a correction). Different reporters on the same date+section
  are legitimate (e.g. CRVS office team + hospital teams) and are summed.
- Section is taken from 'Assigned Section'; if blank, inferred from which
  numeric fields were filled in (pre-skip-logic rows).
"""

from dataclasses import dataclass, field

import pandas as pd

from nrb import config


def _norm_name(name: str) -> str:
    return " ".join(str(name).replace("’", "'").split()).strip()


def split_names(raw) -> list:
    if pd.isna(raw):
        return []
    return [_norm_name(p) for p in str(raw).split(",") if _norm_name(p)]


def infer_section(row) -> str:
    """Pick the section whose fields have the most filled values."""
    best, best_count = "", 0
    for section, fields in config.SECTION_FIELDS.items():
        count = sum(1 for f in fields if f in row.index and pd.notna(row[f]))
        if count > best_count:
            best, best_count = section, count
    return best


@dataclass
class CleanResult:
    clean: pd.DataFrame = field(default_factory=pd.DataFrame)
    dropped_duplicates: pd.DataFrame = field(default_factory=pd.DataFrame)
    unknown_names: pd.DataFrame = field(default_factory=pd.DataFrame)
    issues: pd.DataFrame = field(default_factory=pd.DataFrame)


def clean_responses(df: pd.DataFrame, roster_names: list, today=None) -> CleanResult:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    # Tolerate header drift on the two whitespace-sensitive axes.
    rename = {}
    for col in df.columns:
        for f in config.ALL_NUMERIC_FIELDS + [
            config.TIMESTAMP_COL,
            config.NAME_COL,
            config.DATE_COL,
            config.SECTION_COL,
        ]:
            if (
                col != f
                and " ".join(col.split()).lower() == " ".join(f.split()).lower()
            ):
                rename[col] = f
    if rename:
        df = df.rename(columns=rename)

    df[config.TIMESTAMP_COL] = pd.to_datetime(
        df.get(config.TIMESTAMP_COL), errors="coerce"
    )
    df[config.DATE_COL] = pd.to_datetime(df.get(config.DATE_COL), errors="coerce")
    for f in config.ALL_NUMERIC_FIELDS:
        if f not in df.columns:
            df[f] = pd.NA
        df[f] = pd.to_numeric(df[f], errors="coerce")

    df["names_list"] = df[config.NAME_COL].apply(split_names)
    roster = {_norm_name(n) for n in roster_names}
    df["all_names_known"] = df["names_list"].apply(
        lambda names: bool(names) and all(n in roster for n in names)
    )

    # Section: explicit, else inferred.
    sec = df.get(config.SECTION_COL)
    df["section"] = sec.astype("string").str.strip() if sec is not None else ""
    blank = df["section"].isna() | (df["section"] == "")
    if blank.any():
        df.loc[blank, "section"] = df.loc[blank].apply(infer_section, axis=1)

    issues = []
    today = pd.Timestamp(today) if today else pd.Timestamp(config.today())

    unknown = df[~df["all_names_known"]]
    clean = df[
        df["all_names_known"] & df[config.DATE_COL].notna() & (df["section"] != "")
    ].copy()

    future = clean[clean[config.DATE_COL] > today]
    for _, r in future.iterrows():
        issues.append(
            {
                "issue": "Future date",
                "date": r[config.DATE_COL],
                "name": r[config.NAME_COL],
                "section": r["section"],
            }
        )

    # Deduplicate: same (date, section, name-set) -> latest timestamp wins.
    clean["name_key"] = clean["names_list"].apply(lambda ns: "|".join(sorted(ns)))
    clean = clean.sort_values(config.TIMESTAMP_COL)
    dup_mask = clean.duplicated(
        subset=[config.DATE_COL, "section", "name_key"], keep="last"
    )
    dropped = clean[dup_mask]
    clean = clean[~dup_mask].copy()

    # Flag (not drop) same date+section rows with overlapping-but-different name sets.
    for (d, s), grp in clean.groupby([config.DATE_COL, "section"]):
        if len(grp) > 1:
            sets = [set(ns) for ns in grp["names_list"]]
            overlap = any(a & b for i, a in enumerate(sets) for b in sets[i + 1 :])
            if overlap:
                issues.append(
                    {
                        "issue": "Same person in multiple submissions (possible double count)",
                        "date": d,
                        "section": s,
                        "name": " / ".join(grp[config.NAME_COL].astype(str)),
                    }
                )

    for f in config.ALL_NUMERIC_FIELDS:
        bad = clean[clean[f].notna() & ((clean[f] < 0) | (clean[f] % 1 != 0))]
        for _, r in bad.iterrows():
            issues.append(
                {
                    "issue": f"Suspicious value in '{f}' ({r[f]})",
                    "date": r[config.DATE_COL],
                    "name": r[config.NAME_COL],
                    "section": r["section"],
                }
            )

    clean["date"] = clean[config.DATE_COL].dt.normalize()
    return CleanResult(
        clean=clean.reset_index(drop=True),
        dropped_duplicates=dropped.reset_index(drop=True),
        unknown_names=unknown.reset_index(drop=True),
        issues=pd.DataFrame(issues, columns=["issue", "date", "name", "section"]),
    )


def explode_people(clean: pd.DataFrame) -> pd.DataFrame:
    """One row per (submission, person) for per-person analytics."""
    if clean.empty:
        return clean.assign(person=pd.Series(dtype=str))
    out = clean.explode("names_list").rename(columns={"names_list": "person"})
    return out[out["person"].notna()]
