#!/usr/bin/env python3
"""
validate_cycles.py - ancestry loop detection for arbasoen.

An ancestry loop is a person who is their own ancestor. It is always a data
error, and it is the one error class that can hang or explode a pedigree
walk, so it is worth checking before rendering.

Designed to consume arbasoen's own structures rather than re-parse anything.
After the notebook has built `persons` and `families`, run:

    from validate_cycles import report
    report(persons, families)

It can also run standalone against a GEDCOM file:

    python validate_cycles.py path/to/tree.ged

In that mode it reads only the parent links (FAMC, HUSB, WIFE, CHIL), which
is all loop detection needs, and deliberately does not duplicate
`read_person` / `read_family`.

Exit code is 1 when loops are found, so it can gate a CI job.

MIT licensed, same as arbasoen.
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Iterable, List, Mapping, Sequence, Set

__all__ = ["build_parent_map", "find_cycles", "format_report", "report"]


# --------------------------------------------------------------------------
# Building the parent map
# --------------------------------------------------------------------------

def build_parent_map(persons: Mapping, families: Mapping,
                     all_famc: bool = True) -> Dict[str, Set[str]]:
    """
    Map every person to the set of their parents.

    `persons` and `families` are arbasoen's dicts, keyed by xref
    (`@I123@`, `@F45@`). Only three attributes are touched:
    `Person.famc_rec`, `Family.husband_ref` and `Family.wife_ref`.

    all_famc=True also walks `Family.children_refs`, which catches parents
    that `Person.famc_rec` cannot see. `read_person` keeps only the first
    FAMC, so a person entered into two families (the classic symptom of a
    duplicated couple) has a second set of parents that is invisible from
    the person side and visible only from the family side. Loops often run
    through exactly that link, so leave this on unless you are deliberately
    reproducing the renderer's narrower view.
    """
    parents: Dict[str, Set[str]] = {ref: set() for ref in persons}

    def link(child: str, parent) -> None:
        if not child or not parent:
            return
        if child in parents and parent in persons and parent != child:
            parents[child].add(parent)

    for ref, person in persons.items():
        famc = getattr(person, "famc_rec", None)
        fam = families.get(famc) if famc else None
        if fam is not None:
            link(ref, getattr(fam, "husband_ref", None))
            link(ref, getattr(fam, "wife_ref", None))

    if all_famc:
        for fam in families.values():
            for child in getattr(fam, "children_refs", []) or []:
                link(child, getattr(fam, "husband_ref", None))
                link(child, getattr(fam, "wife_ref", None))

    return parents


# --------------------------------------------------------------------------
# Cycle detection
# --------------------------------------------------------------------------

def find_cycles(persons: Mapping, families: Mapping,
                all_famc: bool = True) -> List[List[str]]:
    """
    Return every distinct ancestry loop as a list of person refs, each ending
    where it began. Iterative depth-first search with the standard
    white/grey/black colouring, so it is safe on trees far deeper than
    Python's recursion limit.
    """
    parents = build_parent_map(persons, families, all_famc=all_famc)

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {ref: WHITE for ref in parents}
    cycles: List[List[str]] = []
    seen: Set[frozenset] = set()

    for start in parents:
        if colour[start] != WHITE:
            continue
        stack = [(start, iter(sorted(parents[start])))]
        path = [start]
        on_path = {start}
        colour[start] = GREY
        while stack:
            node, it = stack[-1]
            advanced = False
            for parent in it:
                if colour[parent] == WHITE:
                    colour[parent] = GREY
                    path.append(parent)
                    on_path.add(parent)
                    stack.append((parent, iter(sorted(parents[parent]))))
                    advanced = True
                    break
                if colour[parent] == GREY and parent in on_path:
                    loop = path[path.index(parent):] + [parent]
                    key = frozenset(loop)
                    if key not in seen:
                        seen.add(key)
                        cycles.append(loop)
            if not advanced:
                colour[node] = BLACK
                stack.pop()
                if path and path[-1] == node:
                    path.pop()
                    on_path.discard(node)

    return cycles


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def _label(ref: str, persons: Mapping) -> str:
    person = persons.get(ref)
    if person is None:
        return f"{ref} (missing)"
    name = (getattr(person, "name", "") or "").replace("/", "").strip()
    birth = getattr(getattr(person, "birth", None), "date", None)
    return f"{name or ref} {ref}" + (f" b.{birth}" if birth else "")


def format_report(cycles: Sequence[Sequence[str]], persons: Mapping) -> str:
    if not cycles:
        return "No ancestry loops found."
    lines = [f"{len(cycles)} ancestry loop(s) found.", ""]
    for n, loop in enumerate(cycles, 1):
        lines.append(f"Loop {n} ({len(loop) - 1} people):")
        for ref in loop:
            lines.append(f"    {_label(ref, persons)}")
        lines.append("")
    lines.append(
        "Each loop makes someone their own ancestor. Break exactly one link "
        "per loop, choosing the link with the weakest evidence rather than "
        "the most convenient one."
    )
    return "\n".join(lines)


def report(persons: Mapping, families: Mapping, all_famc: bool = True) -> int:
    """Print a report and return the number of loops found."""
    cycles = find_cycles(persons, families, all_famc=all_famc)
    print(format_report(cycles, persons))
    return len(cycles)


# --------------------------------------------------------------------------
# Standalone entry point
# --------------------------------------------------------------------------

class _Person:
    __slots__ = ("name", "famc_rec", "birth")

    def __init__(self, name: str = "") -> None:
        self.name = name
        self.famc_rec = None
        self.birth = type("E", (), {"date": None})()


class _Family:
    __slots__ = ("husband_ref", "wife_ref", "children_refs")

    def __init__(self) -> None:
        self.husband_ref = None
        self.wife_ref = None
        self.children_refs = []


def load_minimal(path: str):
    """
    Read only what loop detection needs: FAMC, HUSB, WIFE, CHIL and NAME.

    Uses ged4py when available so behaviour matches arbasoen, and otherwise
    falls back to a line reader. The fallback matters for real-world files:
    a tree that fails to open is exactly the tree you most want to check.
    """
    persons, families = {}, {}
    try:
        from ged4py import GedcomReader  # type: ignore
    except ImportError:
        GedcomReader = None

    if GedcomReader is not None:
        with GedcomReader(path) as reader:
            for record in reader.records0():
                if record.tag == "INDI":
                    person = _Person()
                    name = record.sub_tag("NAME")
                    if name:
                        person.name = name.value or ""
                    famc = record.sub_tag("FAMC")
                    if famc:
                        person.famc_rec = famc.xref_id
                    persons[record.xref_id] = person
                elif record.tag == "FAM":
                    family = _Family()
                    husband = record.sub_tag("HUSB")
                    wife = record.sub_tag("WIFE")
                    family.husband_ref = husband.xref_id if husband else None
                    family.wife_ref = wife.xref_id if wife else None
                    family.children_refs = [c.xref_id for c in record.sub_tags("CHIL")]
                    families[record.xref_id] = family
        return persons, families

    import re
    text = open(path, encoding="utf-8", errors="replace").read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    line_re = re.compile(r"^(\d+)\s+(@[^@]+@)?\s*(\S+)?(?:\s(.*))?$")
    current = kind = None
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
        elif level == "1" and current is not None:
            if kind == "I":
                if tag == "NAME" and not current.name:
                    current.name = value
                elif tag == "FAMC" and current.famc_rec is None:
                    current.famc_rec = value
            elif kind == "F":
                if tag == "HUSB":
                    current.husband_ref = value
                elif tag == "WIFE":
                    current.wife_ref = value
                elif tag == "CHIL":
                    current.children_refs.append(value)
    return persons, families


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("gedcom", help="path to a GEDCOM file")
    parser.add_argument("--famc-only", action="store_true",
                        help="use only Person.famc_rec, the renderer's narrower "
                             "view, instead of also walking Family.children_refs")
    args = parser.parse_args(list(argv) if argv is not None else None)

    persons, families = load_minimal(args.gedcom)
    print(f"Loaded {len(persons)} persons, {len(families)} families "
          f"from {args.gedcom}\n")
    return 1 if report(persons, families, all_famc=not args.famc_only) else 0


if __name__ == "__main__":
    sys.exit(main())
