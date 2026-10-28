# Changelog

All notable changes to terra-nauvis are documented in this file. The
format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Milestone `toolchain`: the `terra-nauvis` 0.1.0 mod skeleton, with `prototypes/config.lua` as the
  single source of names and constants, the Map scale startup setting (1 to 6, default 6), the
  placeholder preset "Terra Nauvis: Europe" (Europe's extent at scale 6 with an ocean beside the
  spawn, and a copy of vanilla's start mask on `elevation_nauvis`, so design constraint 3 holds on
  it; withheld while Alien Biomes is loaded, whose palms read `elevation`), the GPLv3 `LICENSE` and a
  written source offer; byte-reproducible zips from `tools/build_zip.py` (`--release`, which refuses
  any Earth body `tests/frozen.json` does not register, and `--check-tag`; it refuses an output
  folder in the live profile, in any spelling (the NT namespace included), a mods folder, and a
  file with a second hard link or a folder holding one); the gate runner
  `tools/earth_test.py` (`gate`, `suite`, `install-check`, `baseline`, `static`, `freeze`, and
  `guard-rebaseline`, which is left to the maintainer at an interactive terminal) with content-hash keys,
  live-profile guard brackets chained on the chain's last entry with an append-only journal and a
  check for game logs written outside every bracket, the workspace lock and its bracket token, a
  kill-on-close job object around every fh.py launch, a stop of every further game run of a command
  as soon as one run may have left its instance or ran on another build, validated milestone ids, every
  tool output judged at the absolute path the tool writes, the section 6 parser that
  reads every cell of 6.2 and 6.3 (P3 in force from the first milestone, and no row in force without
  its check), rule 5's pooled group for a timed ratio near its limit, suite evidence re-derived from
  raw outputs alone (timed repetitions, the walker, the server saves, and the game self-test by
  replaying its stored runs), the frozen-body check over every Earth body of the dumps, and the
  isolation checks (a) and (b) gating from here, (b) walking each placed prototype's property keys
  through the preset's redirects, with their positive controls on the test-only `ea-leak-fixture`
  presets, plus the `ab_placeholder` row beside Alien Biomes (placeholder presets only; it retires
  with the placeholder in `europe-coast`, and the AB palm leak on the real presets stays outside the
  gate until `climate-tiles`); `tools/tnguard.py` (the
  bracket check, the live-profile output refusal every repo tool shares and the declaration of every
  tool option); `tools/perf.py` (the quiet-window protocol, the affinity watcher, the T15b timer, the
  benchmark-mode walker, the real-time and server-save jobs); `tools/tn_static.py` (T16's static
  rows, which `ci.yml` runs, the name scan reading identifiers and `tools/mods/` among them, and the
  workflow scan holding both workflows to their exact steps and commands); the lint
  toolchain (luacheck 1.2.0 per user, luaparser 4.2.0); S8's tools and test mods, TQ1's timer and
  TQ2's driver ported to `tools/` and `tools/mods/`;
  EarthMaps' reference rasters in `data-src/earthmaps/` and the approval data in `data-src/approvals/`,
  each with its provenance; the T3 oracle in `tests/oracle/` (S8's places plus R7b's, R7a's, R1's and
  the brief's rows); and the `ci.yml` and `release.yml` GitHub workflows.
- Gate wall time on this machine (decision 1; test notes open item 6): cold 162.4 s
  (`previews/earth-build/gate/20261027-191014-toolchain`, every FG key stale) and warm 128.7 s
  (`previews/earth-build/gate/20261027-191322-toolchain`), both with the rotating live sample (the
  31-check game self-test, replayed from its outputs, and an M0t against M0t pair at 16 LP), both
  far under 10 minutes; paths are under `%FACTORIO_WS%`.
- Evidence: S8's offline self-tests run 62 + 760 + 10 + 4 + 10 checks from `tools/` with no failure;
  the game self-test passes 31 of 31 through fh.py and again when replayed from its stored outputs;
  the oracle data passes 1,578 checks; T16's fixture controls 220 of 220 and the runner's 87 of 87
  behave; P18 reads M0t/M0t 0.9892 at 16 LP and 0.9998 at 8 LP, every repetition re-derived from its
  raw outputs (suite `previews/earth-build/suite/20261027-175324-toolchain`; the game self-test's
  evidence from suite `previews/earth-build/suite/20261027-190504-toolchain`); on the placeholder
  preset Entity 8,549 and Cliff 287 equal the constant-coast twin's while Tile differs (10,093
  against 8,777), and the dump walk finds no firewall path, while on the fixture presets it reaches
  the fine field through the start mask and through the redirected `entity:coal:probability` and
  `decorative:brown-asterisk:richness`; beside the live Alien Biomes copy no placeholder preset is
  defined, while the placeholder's redirects would reach the fine field through `tree-palm-b`.
