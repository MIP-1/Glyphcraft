# B4: the panel search revealed mode-hidden sections

## What was wrong

`filterControls(q)` (`app.js`) toggled `.hidden` on every control and
`style.display` on every `.panel-section` purely from the search hit. Mode
visibility is decided elsewhere (`toggleModeSections()` sets the Script, Dither
and Colour section displays and the palette control). After a search, clearing
the box set every section's `display` back to `""`, so a Script-mode user who
searched once saw the Dither-only controls again. The same happened while a
query matched a control in a mode-hidden section.

## Fix

`filterControls()` now runs its hit pass and then re-applies
`toggleModeSections()` last, so mode visibility wins. While a query is active it
then hides any section the search left with no visible item. Nothing else
changed: the search still matches the same text, and the panel is unchanged when
the query is empty.

## Old vs new, measured in one browser session

Same page flow on both trees: search `depth`, then clear, with mode `script`.

| Tree | Dither section while searching | Dither section after clearing | Script section |
|---|---|---|---|
| old (`ad5bb37`) | `""` (visible) | `""` (visible — the bug) | `""` |
| new (working tree) | `none` | `none` | `""` |

## Regression test

`tests/test_suite.py` gained one check next to the existing search check:

```
search keeps mode-hidden sections hidden
```

It asserts mode `script`, the Dither section `display === "none"` and the Script
section still visible after searching and clearing. RED on the old tree (dither
`""`), GREEN now.

This raises the suite from 169 to **170 checks**; `tests/gate/run_gate.py` (G5)
now requires exactly 170. The check count only goes up.

Verification: 170 checks, 0 failures (`test-suite-b4.log`); G20 200/200 exact
(`golden-b4.log`); build + dist smoke `4135467496` (`build-b4.log`).
