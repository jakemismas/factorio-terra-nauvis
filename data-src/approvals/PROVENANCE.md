# Approval data: provenance

`approvals-data.json` is the machine twin of the design notes (the maintainer's review tables with
the adopted defaults; design section 1): the data the milestones load into
`terra-nauvis/prototypes/tables/`. It is a byte copy of `spikes/approvals/out/approvals-data.json`
in an earlier prototype on the prototype branch (`git show`; TST-23), built there by
`spikes/approvals/build_approvals.py`. A row the maintainer flips is a data edit to this file, recorded in
the design notes, never a code change.

| File | sha256 | Source |
|---|---|---|
| `approvals-data.json` | `33ce91d5e5303fb47825d52593e942d22f2d16e7f03b3d11cab4fd97eaa24c5a` | byte copy of `spikes/approvals/out/approvals-data.json` at `45c86d706c21` |
| `destroyed-zone.json` | `8113d3185fb1c2ea552c4568a9c20de40c2c8d1f45a00f0ebfd7cdfaa9c9a8fe` | the decision of 2026-10-30 10:05: the zone's outline, written by hand, superseding `approvals-data.json` `destroyed_europe_polygon` |
