# arbasoen validators

Data-quality checks for a GEDCOM before you render a book from it. Two
independent tools, MIT licensed like the rest of arbasoen.

| File | Finds |
|---|---|
| `validate_cycles.py` | people who are their own ancestor |
| `validate_chronology.py` | dates that cannot all be true at once |

Both **consume arbasoen's own `persons` and `families` structures** rather than
building a tree of their own, so they stay in step with `read_person` and
`read_family`. Both also run standalone against a GEDCOM path, reading only the
tags their checks need.

```
validate/
  validate_cycles.py
  validate_chronology.py
  tests/
    loop.ged          4 invented people, one ancestry loop
    chronology.ged    9 invented people, one of each date error
    run.sh            smoke tests, exits nonzero on any surprise
```

Each file is deliberately standalone, with no shared module and a little
duplication in the minimal readers. In a Colab project that is the useful
trade: a single `wget` of one file works, and neither tool can break the
other.

## Quick start

```bash
sh validate/tests/run.sh                       # smoke tests
python validate/validate_cycles.py tree.ged
python validate/validate_chronology.py tree.ged --json findings.json
```

## validate_cycles.py

Ancestry loop detection: finds people who are their own ancestor.

**Consumes arbasoen's own structures**, it does not build a tree of its own.
In Colab, after the notebook has loaded `persons` and `families`:

```python
from validate_cycles import report
report(persons, families)
```

It touches exactly three attributes: `Person.famc_rec`, `Family.husband_ref`,
`Family.wife_ref`, plus `Family.children_refs` in the default mode.

Standalone, for CI or a quick check:

```bash
python validate/validate_cycles.py tree.ged        # exit 1 if loops are found
python validate/validate_cycles.py tree.ged --famc-only
```

Standalone mode reads only FAMC / HUSB / WIFE / CHIL / NAME, which is all loop
detection needs, so `read_person` and `read_family` are not duplicated. It uses
ged4py when installed and falls back to a line reader otherwise, on the grounds
that a file which fails to open is exactly the file you most want to check.

### Why `--famc-only` exists

`read_person` keeps only the **first** `FAMC`:

```python
famc_rec = record.sub_tag('FAMC')   # singular
```

A person entered into two families, the classic symptom of a duplicated couple,
therefore has a second set of parents that is invisible from the person side and
visible only from the family side. **109 individuals in the reference tree have
more than one FAMC.** Loops frequently run through exactly that link, so the
default walks `children_refs` as well. `--famc-only` reproduces the renderer's
narrower view for comparison.

### Tests

`tests/loop.ged` is a four-person synthetic fixture (Anna is her own
grandmother) with no real personal data. Expected: one loop, exit code 1.

Regression-checked against a real 8,742-person export with three independently
diagnosed loops (de Lijster, Gorter, Heijzelendoorn). All three are found, with
no false positives on the corrected 8,743-person export, which reports clean.

## validate_chronology.py

Was every parent born, alive and of a plausible age when each child arrived,
plus the checks that share the same machinery: sibling spacing, childbearing
span, lifespan, born-after-own-death, married-after-dying.

```python
from validate_chronology import report
report(persons, families)
```

```bash
python validate/validate_chronology.py tree.ged
python validate/validate_chronology.py tree.ged --json findings.json --max-mother-age 48
```

Reads `Person.birth` / `baptism` / `christening` / `death` / `burial` and
`Family.marriage`, falling back from birth to baptism and from death to burial
with the appropriate slack. Thresholds are all flags.

### Tolerance

Every finding must survive the uncertainty of the dates behind it: `ABT` and
friends carry plus or minus two years, `BEF` and `AFT` three, a year-only date
half a year, a month-only date half a month. What comes out is not rounding
noise. Sibling spacing and childbearing span additionally ignore any birth
known less precisely than 60 days, since a guess cannot tell you two children
were born too close together.

### Why not reuse pretty_date

This is the one place where a validator and a renderer genuinely want opposite
behaviour. `pretty_date` normalises whatever it is handed and prints something
readable, which is right for a book. A validator has to keep the uncertainty
rather than resolve it, and it has to refuse to guess.

The clearest case is the non-standard `d/m/Y` form. `PrettyDateVisitor.visitPhrase`
resolves it with `strptime('%d/%m/%Y')`, day-first, silently. That is a fine
choice for printing. But when both components are 12 or under the order is not
recoverable from the string, and the renderer's assumption could be wrong with
no warning anywhere in the output. So this validator parses those as
month-precision and reports them under `ambiguous-slash`. **On a real
8,743-person export that is 684 dates**, every one of which is printed in the
book on an assumption. Unambiguous slashed dates, where one component exceeds
12, are parsed exactly and not reported.

### Tests

`tests/chronology.ged` is a nine-person synthetic fixture with no real personal
data, carrying one deliberate instance of each error class. Expected: 9
findings across 7 checks, exit code 1. `tests/loop.ged` has no dates and
reports clean, exit code 0.

Cross-checked against an independently written implementation over the same
8,743-person export: identical counts on every shared check (7, 13, 22, 16, 20,
13, 39, 3, 1). The lifespan check reports more here (3 against 1) because it
runs over every person rather than only over people who appear as a spouse.


## Adding these to the repo

They touch nothing that exists: a new `validate/` folder beside `examples/`.
Nothing in `arbasoen.ipynb` needs to change for the standalone mode to work.
To use them from the notebook, one cell after the tree is loaded:

```python
!wget -q https://raw.githubusercontent.com/barrynauta/arbasoen/main/validate/validate_cycles.py
!wget -q https://raw.githubusercontent.com/barrynauta/arbasoen/main/validate/validate_chronology.py
import validate_cycles, validate_chronology
validate_cycles.report(persons, families)
validate_chronology.report(persons, families)
```
