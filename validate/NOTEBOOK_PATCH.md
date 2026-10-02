# Notebook patch: make the MAX_GEN cut-off speak

`MAX_GEN` is the only thing that terminates the ancestor walk when a GEDCOM
contains an ancestry loop. Both guards in the BFS (`ahnen_map`, `path_visited`)
are keyed on the ahnentafel id, which only ever grows, so neither can fire on a
repeated person. Today the cut-off is silent, so a looped tree renders
fabricated generations instead of failing.

On a healthy tree the walk stops on its own and **nothing is ever dropped**, so
this warning never fires. Measured on a real 8,743-person tree: deepest
generation 21, zero drops. On the same tree before its three loops were fixed:
depth equal to the cap at every cap tried, and drops every time.

Three small edits to the "Building the generation structure" cell.

## 1. Update the comment on the constant

```python
# MAX_GEN caps BFS depth. It is also the only thing that terminates the walk
# when the tree contains an ancestry loop: both guards below are keyed on the
# ahnentafel id, which always grows, so neither can detect a repeated person.
# A healthy pedigree stops on its own well before this.
MAX_GEN = 23
```

## 2. Collect what the guard cuts

```python
    visited: Set[str] = set()
    path_visited = set()
    truncated = []          # (person, ahnen_id) pairs stopped by MAX_GEN

    while queue:
      ctx = queue.popleft()

      if ctx.gen >= MAX_GEN:
        truncated.append((ctx.person, ctx.ahnen_id))
        continue
```

## 3. Warn before returning

Insert just above `return dict(generations)`:

```python
    if truncated:
        deepest = max(generations) if generations else 0
        names = []
        for person, _ in truncated[:5]:
            label = (person.name or person.ref).replace('/', '').strip()
            if label not in names:
                names.append(label)
        print(f"\n[build_ancestor_generations] WARNING: the walk hit MAX_GEN "
              f"({MAX_GEN}) and cut {len(truncated)} line(s) short at "
              f"generation {deepest}.")
        print("  Either the pedigree genuinely runs deeper than MAX_GEN, or it "
              "contains an ancestry loop.")
        print("  The tell: with a loop the depth reached always equals MAX_GEN, "
              "whatever you set it to,")
        print("  and generations near the cut repeat the same people over and "
              "over in the rendered book.")
        print("  Check with validate/validate_cycles.py before trusting the "
              "deepest generations.")
        print("  Lines cut short at: " + ", ".join(names)
              + (" ..." if len(truncated) > len(names) else ""))

    return dict(generations)
```

## What it looks like

Healthy tree, the normal case, no output at all:

```
(nothing at all: the walk completed on its own at generation 21, MAX_GEN 23, zero lines cut)
```

Looped tree:

```
[build_ancestor_generations] WARNING: the walk hit MAX_GEN (23) and cut 23 line(s) short at generation 23.
  Either the pedigree genuinely runs deeper than MAX_GEN, or it contains an ancestry loop.
  The tell: with a loop the depth reached always equals MAX_GEN, whatever you set it to,
  and generations near the cut repeat the same people over and over in the rendered book.
  Check with validate/validate_cycles.py before trusting the deepest generations.
  Lines cut short at: Arie Willems Dekker, Elisabeth Isaacsen, Pieter Pietersz de Lijster, Marijtje Nijssen, Pieter Pietersz Gorter ...
```

## Why a warning and not an exception

A deep pedigree that legitimately exceeds `MAX_GEN` is a real, if rare, case,
and raising would stop someone rendering a book over it. The warning names the
discriminator so the reader can tell the two apart in one run: raise `MAX_GEN`
and re-run. A genuine pedigree gets deeper and then stops. A loop reaches the
new cap exactly, again.


## Verified

Simulated against both real exports before drafting:

- loop-free tree: no output, walk completed on its own at generation 21
- 2024 tree with three loops: warning fires, 23 lines cut at generation 23, and
  the named people cover all three known loops (Dekker, de Lijster, Gorter)
