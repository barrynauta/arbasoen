#!/usr/bin/env python3
"""
validate_chronology.py - date sanity checks for arbasoen.

Asks one question of every parent and child pair: was the parent born, alive,
and of a plausible age when this child was born? Plus a handful of related
checks that share the same machinery.

Designed to consume arbasoen's own structures rather than re-parse anything.
After the notebook has built `persons` and `families`, run:

    from validate_chronology import report
    report(persons, families)

It can also run standalone against a GEDCOM file:

    python validate_chronology.py path/to/tree.ged

Every finding is tolerance-aware. An `ABT` date carries plus or minus two
years, `BEF` and `AFT` three, a year-only date half a year, and a month-only
date half a month. A finding is reported only when it survives that slack, so
what comes out is not rounding noise.

A note on dates, because this is where a validator and a renderer part company.
arbasoen's `pretty_date` normalises whatever it is given and prints something
readable, which is exactly right for a book. A validator must do the opposite:
keep the uncertainty, refuse to guess, and say so when a date cannot be read.
Hence the separate parser here, and the `ambiguous-slash` check, which reports
the dates that `pretty_date` resolves day-first by assumption.

Exit code is 1 when findings are reported, so it can gate a CI job.

MIT licensed, same as arbasoen.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence

__all__ = ["parse_date", "check", "format_report", "report"]

YEAR = 365.2425

MONTHS = {m: i + 1 for i, m in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


class Fuzzy(NamedTuple):
    """A date plus how wrong it might be, in days, plus how it was written."""
    ordinal: int
    slack: int
    kind: str

    @property
    def date(self) -> datetime.date:
        return datetime.date.fromordinal(self.ordinal)

    def __str__(self) -> str:
        return self.date.isoformat()


# --------------------------------------------------------------------------
# Date parsing
# --------------------------------------------------------------------------

_QUALIFIERS = (
    ("ABT", 730), ("ABOUT", 730), ("CIRCA", 730), ("CA", 730),
    ("EST", 730), ("CAL", 730),
    ("BEF", 1095), ("BEFORE", 1095),
    ("AFT", 1095), ("AFTER", 1095),
)


def parse_date(value: Optional[str]) -> Optional[Fuzzy]:
    """
    Parse a GEDCOM date, tolerating the non-standard forms real exports carry.

    Returns None when nothing usable can be read. Never raises, and never
    guesses silently: an unresolvable day/month order is reported as
    `kind='slash-ambiguous'` with month-level slack rather than as an exact
    date.
    """
    if not value:
        return None
    text = str(value).strip().upper()
    if not text:
        return None

    match = re.match(r"^BET(?:WEEN)?\s+(.*?)\s+AND\s+(.*)$", text)
    if match:
        first, second = parse_date(match.group(1)), parse_date(match.group(2))
        if first and second:
            middle = (first.ordinal + second.ordinal) // 2
            spread = abs(second.ordinal - first.ordinal) // 2
            return Fuzzy(middle, max(spread, first.slack, second.slack), "range")
        return first or second

    match = re.match(r"^(?:FROM|TO)\s+(.*)$", text)
    if match:
        return parse_date(match.group(1))

    for word, slack in _QUALIFIERS:
        prefix = re.match(rf"^{word}\.?\s+(.*)$", text)
        if prefix:
            inner = parse_date(prefix.group(1))
            if not inner:
                return None
            shift = 0
            if word in ("BEF", "BEFORE"):
                shift = -365
            elif word in ("AFT", "AFTER"):
                shift = 365
            kind = "approx" if shift == 0 else word.lower()
            return Fuzzy(inner.ordinal + shift, max(inner.slack, slack), kind)

    # Non-standard DD/MM/YYYY. arbasoen's pretty_date resolves these day-first;
    # here the order is only accepted when one component settles it.
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{3,4})$", text)
    if match:
        first, second, year = (int(g) for g in match.groups())
        try:
            if first > 12 >= second:
                return Fuzzy(datetime.date(year, second, first).toordinal(), 0, "exact")
            if second > 12 >= first:
                return Fuzzy(datetime.date(year, first, second).toordinal(), 0, "exact")
            if first <= 12 and second <= 12:
                return Fuzzy(datetime.date(year, second, min(first, 28)).toordinal(),
                             31, "slash-ambiguous")
        except ValueError:
            pass
        return _year_only(year)

    match = re.match(r"^(?:(\d{1,2})\s+)?(?:([A-Z]{3})[A-Z]*\.?\s+)?(\d{3,4})$", text)
    if match:
        day, month, year = match.group(1), match.group(2), int(match.group(3))
        if day and month in MONTHS:
            try:
                return Fuzzy(datetime.date(year, MONTHS[month], int(day)).toordinal(),
                             0, "exact")
            except ValueError:
                return _year_only(year)
        if month in MONTHS:
            return Fuzzy(datetime.date(year, MONTHS[month], 15).toordinal(), 15, "month")
        return _year_only(year)

    loose = re.search(r"\b(\d{3,4})\b", text)
    return _year_only(int(loose.group(1))) if loose else None


def _year_only(year: int) -> Optional[Fuzzy]:
    try:
        return Fuzzy(datetime.date(year, 7, 1).toordinal(), 183, "year")
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Reading arbasoen's structures
# --------------------------------------------------------------------------

def _event_date(person, *names) -> Optional[str]:
    for name in names:
        event = getattr(person, name, None)
        date = getattr(event, "date", None)
        if date:
            return date
    return None


def _birth(person) -> Optional[Fuzzy]:
    """Birth, falling back to baptism or christening minus a month."""
    direct = parse_date(_event_date(person, "birth"))
    if direct:
        return direct
    proxy = parse_date(_event_date(person, "baptism", "christening"))
    if proxy:
        return Fuzzy(proxy.ordinal - 30, max(proxy.slack, 60), proxy.kind)
    return None


def _death(person) -> Optional[Fuzzy]:
    """Death, falling back to burial plus a week of slack."""
    direct = parse_date(_event_date(person, "death"))
    if direct:
        return direct
    proxy = parse_date(_event_date(person, "burial"))
    if proxy:
        return Fuzzy(proxy.ordinal - 7, max(proxy.slack, 14), proxy.kind)
    return None


def _label(ref: str, persons: Mapping) -> str:
    person = persons.get(ref)
    if person is None:
        return f"{ref} (missing)"
    name = (getattr(person, "name", "") or "").replace("/", "").strip()
    return f"{name or ref} {ref}"


# --------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------

CHECKS = {
    "child-before-parent":  "child born before the parent was born",
    "parent-too-young":     "parent below the minimum age at the birth",
    "child-after-mother-death": "child born after the mother died",
    "posthumous-too-late":  "child born long after the father died",
    "mother-too-old":       "mother above the maximum age at the birth",
    "father-too-old":       "father above the maximum age at the birth",
    "sibling-gap":          "two siblings born impossibly close together",
    "childbearing-span":    "one mother bearing over too long a period",
    "lifespan":             "implausible lifespan",
    "born-after-death":     "born after their own death",
    "marriage-after-death": "married long after dying",
    "ambiguous-slash":      "d/m/y date whose order cannot be resolved",
}


def check(persons: Mapping, families: Mapping, *,
          min_mother_age: int = 14, min_father_age: int = 15,
          max_mother_age: int = 50, max_father_age: int = 70,
          max_lifespan: int = 105, min_sibling_gap: int = 250,
          max_childbearing_span: int = 26,
          posthumous_days: int = 300) -> Dict[str, List[dict]]:
    """Run every check. Returns findings keyed by check name."""
    found: Dict[str, List[dict]] = defaultdict(list)

    def add(kind: str, text: str, **refs) -> None:
        found[kind].append({"check": kind, "text": text, **refs})

    for ref, person in persons.items():
        birth, death = _birth(person), _death(person)
        if birth and death:
            slack = (birth.slack + death.slack)
            if death.ordinal + slack < birth.ordinal:
                add("born-after-death",
                    f"{_label(ref, persons)}: born {birth}, died {death}", person=ref)
            else:
                age = (death.ordinal - birth.ordinal) / YEAR
                if age - slack / YEAR > max_lifespan:
                    add("lifespan",
                        f"{_label(ref, persons)}: born {birth}, died {death}, "
                        f"age {age:.0f}", person=ref)
        for name in ("birth", "baptism", "christening", "death", "burial"):
            raw = _event_date(person, name)
            parsed = parse_date(raw) if raw else None
            if parsed and parsed.kind == "slash-ambiguous":
                add("ambiguous-slash",
                    f"{_label(ref, persons)}: {name} {raw!r} could be "
                    f"day/month or month/day", person=ref)

    for fam_ref, family in families.items():
        marriage = parse_date(getattr(getattr(family, "marriage", None), "date", None))
        children = list(getattr(family, "children_refs", []) or [])
        parents = (("father", getattr(family, "husband_ref", None)),
                   ("mother", getattr(family, "wife_ref", None)))

        for role, parent_ref in parents:
            if not parent_ref or parent_ref not in persons:
                continue
            parent = persons[parent_ref]
            p_birth, p_death = _birth(parent), _death(parent)

            if marriage and p_death:
                gap = marriage.ordinal - p_death.ordinal
                if gap - (marriage.slack + p_death.slack) > 365:
                    add("marriage-after-death",
                        f"{fam_ref}: married {marriage} but {role} "
                        f"{_label(parent_ref, persons)} died {p_death}",
                        family=fam_ref, person=parent_ref)

            min_age = min_mother_age if role == "mother" else min_father_age
            max_age = max_mother_age if role == "mother" else max_father_age

            for child_ref in children:
                child = persons.get(child_ref)
                if child is None:
                    continue
                c_birth = _birth(child)
                if not c_birth:
                    continue

                if p_birth:
                    gap = (c_birth.ordinal - p_birth.ordinal) / YEAR
                    slack = (c_birth.slack + p_birth.slack) / YEAR
                    if gap + slack < 0:
                        add("child-before-parent",
                            f"{_label(child_ref, persons)} born {c_birth}, "
                            f"{-gap:.0f}y before {role} "
                            f"{_label(parent_ref, persons)} born {p_birth}",
                            family=fam_ref, person=child_ref, parent=parent_ref)
                    elif gap + slack < min_age:
                        add("parent-too-young",
                            f"{role} {_label(parent_ref, persons)} was {gap:.0f} "
                            f"at the birth of {_label(child_ref, persons)} ({c_birth})",
                            family=fam_ref, person=parent_ref, child=child_ref)
                    elif gap - slack > max_age:
                        add("mother-too-old" if role == "mother" else "father-too-old",
                            f"{role} {_label(parent_ref, persons)} was {gap:.0f} "
                            f"at the birth of {_label(child_ref, persons)} ({c_birth})",
                            family=fam_ref, person=parent_ref, child=child_ref)

                if p_death:
                    after = c_birth.ordinal - p_death.ordinal
                    slack = c_birth.slack + p_death.slack
                    if role == "mother" and after - slack > 2:
                        add("child-after-mother-death",
                            f"{_label(child_ref, persons)} born {c_birth}, "
                            f"{after / YEAR:.1f}y after mother "
                            f"{_label(parent_ref, persons)} died {p_death}",
                            family=fam_ref, person=child_ref, parent=parent_ref)
                    if role == "father" and after - slack > posthumous_days:
                        add("posthumous-too-late",
                            f"{_label(child_ref, persons)} born {c_birth}, "
                            f"{after / YEAR:.1f}y after father "
                            f"{_label(parent_ref, persons)} died {p_death}",
                            family=fam_ref, person=child_ref, parent=parent_ref)

        # Sibling spacing and childbearing span need precise dates only.
        births = sorted(
            (b.ordinal, ref) for ref, b in
            ((c, _birth(persons[c])) for c in children if c in persons)
            if b and b.slack <= 60)
        for (first_o, first_ref), (second_o, second_ref) in zip(births, births[1:]):
            gap = second_o - first_o
            if 0 < gap < min_sibling_gap:
                add("sibling-gap",
                    f"{fam_ref}: {_label(first_ref, persons)} and "
                    f"{_label(second_ref, persons)} born only {gap} days apart",
                    family=fam_ref, person=first_ref, child=second_ref)
        if len(births) >= 2 and getattr(family, "wife_ref", None):
            span = (births[-1][0] - births[0][0]) / YEAR
            if span > max_childbearing_span:
                add("childbearing-span",
                    f"{fam_ref}: {_label(family.wife_ref, persons)} bore "
                    f"{len(births)} children over {span:.0f} years",
                    family=fam_ref, person=family.wife_ref)

    return dict(found)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

ORDER = ["child-before-parent", "born-after-death", "child-after-mother-death",
         "posthumous-too-late", "parent-too-young", "sibling-gap",
         "marriage-after-death", "mother-too-old", "father-too-old",
         "childbearing-span", "lifespan", "ambiguous-slash"]


def format_report(found: Mapping[str, Sequence[dict]], limit: int = 15) -> str:
    total = sum(len(v) for v in found.values())
    if not total:
        return "No chronology problems found."
    lines = [f"{total} finding(s).", "", "SUMMARY"]
    for name in ORDER:
        rows = found.get(name) or []
        if rows:
            lines.append(f"  {len(rows):5d}  {name:24} {CHECKS[name]}")
    for name in ORDER:
        rows = found.get(name) or []
        if not rows:
            continue
        lines += ["", "=" * 74, f"{name}  ({len(rows)})", "=" * 74]
        for row in rows[:limit]:
            lines.append(f"  - {row['text']}")
        if len(rows) > limit:
            lines.append(f"  ... and {len(rows) - limit} more")
    return "\n".join(lines)


def report(persons: Mapping, families: Mapping, limit: int = 15, **kwargs) -> int:
    found = check(persons, families, **kwargs)
    print(format_report(found, limit=limit))
    return sum(len(v) for v in found.values())


# --------------------------------------------------------------------------
# Standalone entry point
# --------------------------------------------------------------------------

class _Event:
    __slots__ = ("date", "place")

    def __init__(self, date=None, place=None):
        self.date, self.place = date, place


class _Person:
    __slots__ = ("name", "sex", "birth", "baptism", "christening", "death", "burial")

    def __init__(self):
        self.name = ""
        self.sex = ""
        for slot in ("birth", "baptism", "christening", "death", "burial"):
            setattr(self, slot, _Event())


class _Family:
    __slots__ = ("husband_ref", "wife_ref", "children_refs", "marriage")

    def __init__(self):
        self.husband_ref = self.wife_ref = None
        self.children_refs = []
        self.marriage = _Event()


_TAG_TO_SLOT = {"BIRT": "birth", "BAPM": "baptism", "CHR": "christening",
                "DEAT": "death", "BURI": "burial"}


def load_minimal(path: str):
    """Read only the tags the checks need. See validate_cycles.load_minimal."""
    persons, families = {}, {}
    text = open(path, encoding="utf-8", errors="replace").read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    line_re = re.compile(r"^(\d+)\s+(@[^@]+@)?\s*(\S+)?(?:\s(.*))?$")
    current = kind = section = None
    for raw in text.split("\n"):
        match = line_re.match(raw)
        if not match:
            continue
        level, xref, tag, value = match.groups()
        value = (value or "").strip()
        if level == "0":
            what = (value or tag or "").strip()
            if xref and what == "INDI":
                current, kind = persons.setdefault(xref, _Person()), "I"
            elif xref and what == "FAM":
                current, kind = families.setdefault(xref, _Family()), "F"
            else:
                current = kind = None
            section = None
        elif current is None:
            continue
        elif level == "1":
            section = tag
            if kind == "I":
                if tag == "NAME" and not current.name:
                    current.name = value
                elif tag == "SEX":
                    current.sex = value
            elif kind == "F":
                if tag == "HUSB":
                    current.husband_ref = value
                elif tag == "WIFE":
                    current.wife_ref = value
                elif tag == "CHIL":
                    current.children_refs.append(value)
        elif level == "2" and tag == "DATE" and section:
            if kind == "I" and section in _TAG_TO_SLOT:
                event = getattr(current, _TAG_TO_SLOT[section])
                if not event.date:
                    event.date = value
            elif kind == "F" and section == "MARR" and not current.marriage.date:
                current.marriage.date = value
    return persons, families


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("gedcom", help="path to a GEDCOM file")
    parser.add_argument("--json", metavar="FILE", help="also write findings as JSON")
    parser.add_argument("--limit", type=int, default=15,
                        help="rows shown per check (default 15)")
    parser.add_argument("--min-mother-age", type=int, default=14)
    parser.add_argument("--min-father-age", type=int, default=15)
    parser.add_argument("--max-mother-age", type=int, default=50)
    parser.add_argument("--max-father-age", type=int, default=70)
    parser.add_argument("--max-lifespan", type=int, default=105)
    parser.add_argument("--min-sibling-gap", type=int, default=250)
    parser.add_argument("--max-childbearing-span", type=int, default=26)
    args = parser.parse_args(list(argv) if argv is not None else None)

    persons, families = load_minimal(args.gedcom)
    print(f"Loaded {len(persons)} persons, {len(families)} families "
          f"from {args.gedcom}\n")
    found = check(persons, families,
                  min_mother_age=args.min_mother_age,
                  min_father_age=args.min_father_age,
                  max_mother_age=args.max_mother_age,
                  max_father_age=args.max_father_age,
                  max_lifespan=args.max_lifespan,
                  min_sibling_gap=args.min_sibling_gap,
                  max_childbearing_span=args.max_childbearing_span)
    print(format_report(found, limit=args.limit))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(found, handle, indent=1, ensure_ascii=False)
        print(f"\nJSON written to {args.json}")
    return 1 if any(found.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
