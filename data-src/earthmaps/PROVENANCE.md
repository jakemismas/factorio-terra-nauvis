# EarthMaps reference rasters: provenance

These files are the reference every fidelity, oracle and navigability check compares against
(ARCHITECTURE.md, "Build-time data flow", step 1). They derive from EarthMaps by HySpeed
(https://github.com/HySpeed/EarthMaps, GPLv3, `LICENSE` here), version 2.1.2, commit
`23c647b83fc4e4794dac994bfbd2232f4202cb6b` (`23c647b8`). They were ported to `main` by milestone
`toolchain` from an earlier prototype on the prototype branch
(TST-23: `spikes/` never reaches `main`).

## Decoder command

The rasters are the output of `tools/earthmaps_decode.py` (S8's decoder, version 1, ported
unchanged in its decoding) over a clone of EarthMaps at that commit in
`%FACTORIO_WS%\downloads\earthmaps\src` (`git clone https://github.com/HySpeed/EarthMaps`). The gate
regenerates them into a scratch directory and compares every PNG byte for byte with the files
below and with the sha256 that each map's JSON records under `png`:

```
python -I tools/earthmaps_decode.py %FACTORIO_WS%\downloads\earthmaps\src --png-out <scratch> --json-out <scratch> --no-simulation
```

`--no-simulation` skips the river sampler simulation, which only the JSON holds; the PNGs do not
depend on it. The reference JSON files are the planning run's own outputs (with the simulation),
copied byte for byte; the regenerated JSON is never compared with them, only their sizes and
class counts are.

## Files and sha256

| File | sha256 | Source |
|---|---|---|
| `europe.json` | `84d217b56f9fc5ee4a726d48bab84a82b4149c06db2103789e2f04e5e3844289` | byte copy of `spikes/S8-tooling/reference/europe.json` in an earlier prototype (`git show`) |
| `europe-land.png` | `29b127d5c7bd5c8b03c5fa5fa9205f8484742720a71d45df991aa613492f9a2b` | decoder output; equals `europe.json` png.land.sha256 |
| `europe-thinwater.png` | `c33747c0725b914f6853516d79ee5b7ee6fc7df755990b77603b25d15a7c2519` | decoder output; equals `europe.json` png.thinwater.sha256 |
| `europe-classes.png` | `4fd9e12d61d06ac0f27383ca2fb3e3036f69d1575e5383863a7a159ac94115c3` | decoder output; equals `europe.json` png.classes.sha256 |
| `atlantic.json` | `a93850d94881fda6d4ffb323f9426813d1b45a7a704375884ae28dfdb07e2361` | byte copy of `spikes/S8-tooling/reference/atlantic.json` in an earlier prototype (`git show`) |
| `atlantic-land.png` | `150af4cb1634045dc62ad07c5e9c46081733a6e6476bfedb91c5ec08a38518f4` | decoder output; equals `atlantic.json` png.land.sha256 |
| `atlantic-thinwater.png` | `547c262029ffbf8000e16f62bf5428368a9922233940fecd77664cfb5c395dfc` | decoder output; equals `atlantic.json` png.thinwater.sha256 |
| `atlantic-classes.png` | `753df5ad381eeea33e71cd9fe95ce5d85a9e2bd070d69e8bfafd0fd38138e8ac` | decoder output; equals `atlantic.json` png.classes.sha256 |
| `olde_world.json` | `07e1184698177de0f104061eca17b4cf7ab7504cacd7c533fc256c9d2e6c9c22` | byte copy of `spikes/S8-tooling/reference/olde_world.json` in an earlier prototype (`git show`) |
| `olde_world-land.png` | `7a7af0b11aeb8e21f84adbdf965f94f800789435ce228572267c45dd87e20e57` | decoder output; equals `olde_world.json` png.land.sha256 |
| `olde_world-thinwater.png` | `a06d773279ab91a958d268feacfb12f6fd2f2435a69a38609b33b68b5da77a70` | decoder output; equals `olde_world.json` png.thinwater.sha256 |
| `olde_world-classes.png` | `4600b243cc84e77c0274a8c672743e516e85dacac992f8e97c2e3159c1dbb9ad` | decoder output; equals `olde_world.json` png.classes.sha256 |
| `LICENSE` | `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903` | EarthMaps' LICENSE (GPLv3) at commit `23c647b8`, line endings normalised to LF by `.gitattributes` |

## EarthMaps data files decoded

| Map | World file | sha256 | Cities file | sha256 |
|---|---|---|---|---|
| europe | `data/world_europe.lua` | b6fef7cf4c4adce01acb9bbe79815390a14861991e28a32facb4c8a552365bd0 | `data/cities_europe.lua` | 5aafce3b3ae5ea8c7ad767a00e0eb0411a8cf24aa75bc12ec6a8541ad5cbe58c |
| atlantic | `data/world_atlantic.lua` | 3bb758e3263b53265dc603a82ea5f0b2c0437bd44bc15f817573e7c62b69fd1a | `data/cities_atlantic.lua` | b7b99386b4718a78390ff3567bcb34b52f151eaad61d518d964304bfadca9009 |
| olde_world | `data/world_olde_world.lua` | 178ea01db883dd15be8d89db89ba46e4605d3290ec25dc34afdbc3afc927ee7f | `data/cities_olde_world.lua` | 6781bc12b32de4655ccd5a1fd8fd88c19512e24c9d460ac1ba575522157445de |
