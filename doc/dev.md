# R&D

## Overview
This doc is the single source of truth of R&D plan, research findings, and design/implementation decisions.

## Maintenance
New maps will be added over time. We need to add those map pictures to `res/mp/` and also the map metadata to `res/spec/all.map.json` before running any map commnads.

### TierMaker extraction: duplicate label and cropped last row

An October 2026 TierMaker screenshot failed with `Duplicate TierMaker tier label: A`.
The OCR adapter tries several image variants for each tier label; on the B row,
its first result was `A`, while four later results were `B`. Label recognition
now selects the most frequent valid result instead of the first one, while
keeping the first result as the tie-breaker.

The same screenshot exposed a second issue: its bottom F row was 78 pixels high
in a grid with an estimated 100-pixel cell size. TierMaker extraction now
accepts a bottom-edge tile when at least 70% of its height remains; other rows
still require 80%. The screenshot now extracts all six tiers, including nine
brawlers in F. The OCR regression test and full test suite pass (72 tests).

## Milestone 1 (M1): Deep-Draft reshuffling by combat and map roles
Because deep-draft support is our major feature for the first release, we must make sure we can shuffle the Deep-Draft map tierlist based on Brawler's Global Roles and Map-Mode Roles, see README.md for details. This can thus serve as our vertical slice.

The required tech:
- Recognize brawler names from the input tierlist image with correct layout.
- Recognize map name from Deep-Draft tierlist image's title line using OCR.
- Derive game mode from the extracted map name, then retrieve map-mode roles as labels for the brawlers according to the map mode info.
- Sort the extracted tierlist by their role labels instead of S-to-F tier labels; inside each role bracket, the brawlers are still sorted in their order in the input tiers. Here, the roles are two separate groups:
  - Global combat functions
  - Map roles depending on the map-of-interest's nature.
- Output the new tierlists (the above two groups) in both text and image forms.
- In the output image, enhance visual readability of brawler tiers in the input tier by giving them certain visual emphasis, such as a colour frame or underline in the original tier colours.

Tech Stack:
- Python
- OpenCV
- Pillow

The current M1 image path supports an explicit `extract --master` command. It
uses a Tesseract subprocess adapter for raw title OCR, then resolves the map
against `res/spec/all.map.json` before applying role metadata from
`res/spec/all.brawler.json`. The existing extraction path remains tierlist-only
unless `--master` is supplied.

The generated master document can be rendered with `generate` to either SVG or
PNG. Both formats use the same deterministic layout model, with global-role
and map-role panels, source-tier border colors, and avatar placeholders.

## Milestone 2 (M2): TierMaker reshuffling by combat roles

Similar to M1, this milestone will use a different source `--source tiermaker` with the same logic, except that it's a global tierlist without map info. 

So we only need to create the Common Classes version of the reshuffled tierlist.

But we likely need to use a different image recognition implementation geared towards the TierMaker tierlist format.

The implementation uses a source-extractor factory with independent
`DeepDraftExtractor` and `TierMakerExtractor` strategies. Both return a
normalized tierlist result, while keeping layout detection and avatar matching
source-specific.

TierMaker extraction requires `--title`. Its JSON document contains:

- `title`, preserved from the command line;
- `originalTierlist`, with dynamically recognized tier labels and source order;
- `globalRoles`, grouped using the M1 combat-role catalog.

TierMaker has no `map` or `mode` fields and therefore renders only the
`Common Classes` panel. DeepDraft continues to support its existing basic
extraction output and optional `--master` map-aware document.

## Milestone 3 (M3): Basic stats tierlist regarding health, range, movement speed, reload speed

- `stats --to OUTPUT_DIR` reads `res/spec/all.brawler.json` directly and creates
  five charts: health, main attack range, super range, movement speed, and
  reload speed. Each chart is exported as JSON, SVG, PNG, and an ImageMagick JPG.
- Each image has two panels. The left panel groups brawlers by their stat rating;
  the right panel groups them by the project's Common Classes. In both panels,
  rating tier takes priority, then brawlers within a tier are sorted by
  descending numeric value. There is no cross-row alignment.
  `reloadSpeed = 1 / mainAttack.reloadSeconds` makes faster reloads rank farther left.
- Ratings come from `rating.rangeMain`, `rating.rangeSuper`, `rating.speed`, and
  `rating.reload`. For slash-separated ratings, only the first label is used.
  `N/A` is its own last tier. Health uses `5000-` for values below 5000,
  thousand-HP bands from `5000` to `9000`, and `10000+` for values at least 10000.
- The tier legend and avatar underlines share a color scale. Consecutive
  brawlers tied on the numeric value in a row show only the first underline;
  later tied underlines are transparent in both panels. Titles use
  `Brawler Tierlist: <stat name>` and retain the existing dated credit.
