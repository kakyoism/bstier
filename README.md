# bstier

## Overview
`bstier` is a helper app for Supercell's mobile game Brawl Stars.

Because competitive players often need to know which brawlers may have advantages on certain maps or modes, they need to painstakingly compare lots of brawler specs, collecting community opinions, and sometimes simply refer to streamers' tierlists. 

Those tierlists all have the same format:
- All the brawlers are considered in the same arena, ignoring their roles in maps and modes
- They are marked from S tier to F tier as a waterfall fashion.

However, in daily ranked and competitive games the players must make the following decisions in terms of whether or not to pick a brawler:
- Is this brawler a mid or a lane?
- Can this brawler counter the opponent team's current picks?
- Will my pick compensate our team's weakness?
- Will my pick overlap my teammates picks in terms of brawler class or map functions?
- Will my pick create useful synergy with my teammates' picks?

The traditional waterfall tierlist format cannot answer these quesions and thus provides very limited values for ranked and competitive players.

`bstier` aims to be a waterfall tierlist modifier for better readability for strategic ban/picks:
- It can reorder a given tierlist in terms of brawler class or a function-class system, so that we can sort the aggro brawlers by their tiers, etc.
- It can reorder a tierlist based on brawler positioning, so that we can pick the best mid and lanes, for example.
- It can reorder a tierlist towards a certain mode, so that we can, for example,  pick the best safe-damage, defence, and flex brawlers for Heist.

## Features
`bstier` can:
- take a screenshot of tierlist and convert it to a text tierlist using image recognition.
- shuffle the recognized names to put them back in whatever shape based on sorting criteria, such as positioning, global roles, and map-mode roles.
- create a new image tierlist based on the input text tierlist.

## Getting Started

### DeepDraft map tierlists

This is the recommended workflow for turning a DeepDraft screenshot into a
map-aware tierlist image. The process has two stages:

1. **Extract** the brawler names and their S-to-F tiers from the screenshot.
2. **Generate** an M1 document and render it as an SVG or PNG.

Run these commands from the repository root. The `run.sh` and `run.bat`
wrappers automatically enter the Poetry environment, so you do not need to
type `poetry run bstier` for every command:

- macOS/Linux: use `./ci/run.sh ...`
- Windows: use `ci\run.bat ...`

#### 1. Set up the project

Run the setup script once. It checks for Python, Poetry, and Tesseract OCR,
installs missing tools through the available system package manager, and then
installs the Python project dependencies:

macOS/Linux:

`./ci/setup.sh`

Windows:

`ci\setup.bat`

DeepDraft extraction needs Tesseract OCR because the map name is read from the
screenshot. If automatic installation is not available on your system, install
Python 3.11 or newer and Tesseract manually, then run the setup script again.

#### 2. Extract a DeepDraft screenshot

Replace `path/to/deepdraft-tierlist.png` with your screenshot path:

macOS/Linux:

`./ci/run.sh extract --source deepdraft --from path/to/deepdraft-tierlist.png --to /tmp/deepdraft-master.json --master`

Windows:

`ci\run.bat extract --source deepdraft --from path/to/deepdraft-tierlist.png --to deepdraft-master.json --master`

What the options mean:

- `extract` reads a tierlist image.
- `--source deepdraft` selects the DeepDraft screenshot layout.
- `--from` is the input image.
- `--to` is the JSON file to create.
- `--master` asks for the map-aware M1 document instead of the basic tierlist JSON.

The M1 document combines the OCR map name, the source tierlist, common brawler
classes, and map/mode roles. The OCR map name is checked against
`res/spec/all.map.json`; an unknown map causes extraction to fail rather than
silently assigning the wrong map.

If you only want the original tierlist data without map and role information,
omit `--master`:

macOS/Linux:

`./ci/run.sh extract --source deepdraft --from path/to/deepdraft-tierlist.png --to /tmp/deepdraft-tierlist.json`

Windows:

`ci\run.bat extract --source deepdraft --from path/to/deepdraft-tierlist.png --to deepdraft-tierlist.json`

#### 3. Render the M1 document

Create an SVG when you want a scalable image:

macOS/Linux:

`./ci/run.sh generate --from /tmp/deepdraft-master.json --to /tmp/deepdraft-master.svg`

Windows:

`ci\run.bat generate --from deepdraft-master.json --to deepdraft-master.svg`

Create a PNG when you want a ready-to-share raster image:

macOS/Linux:

`./ci/run.sh generate --from /tmp/deepdraft-master.json --to /tmp/deepdraft-master.png`

Windows:

`ci\run.bat generate --from deepdraft-master.json --to deepdraft-master.png`

PNG output defaults to `2048x1536`. To request another size, pass
`--reso WIDTHxHEIGHT`, for example:

`./ci/run.sh generate --from /tmp/deepdraft-master.json --to /tmp/deepdraft-master-small.png --reso 1024x768`

The rendered result includes the `Common Classes` and `Map Roles` panels, a
right-aligned S+ through F tier-color legend, the map and mode in the title,
and a dated DeepDraft credit at the bottom. Missing avatar assets are rendered
as placeholders.

#### Complete example using the repository fixture

The repository includes a DeepDraft-style example image at
`test/extract/_org/deepdraft.png`. From the repository root, run:

`./ci/run.sh extract --source deepdraft --master --from test/extract/_org/deepdraft.png --to /tmp/bstier-master.json`

`./ci/run.sh generate --from /tmp/deepdraft-master.json --to /tmp/deepdraft-master.png`

On macOS, open the generated image with:

`open /tmp/deepdraft-master.png`

#### Batch-process a folder of DeepDraft images

To process every supported image directly inside a folder, run:

macOS/Linux:

`./ci/deepdraft.sh path/to/deepdraft-images`

Windows:

`ci\deepdraft.bat path\to\deepdraft-images`

The batch command extracts each image as a DeepDraft M1 JSON document, renders
matching SVG and PNG files, and stitches the source tierlist beside its map
image. Outputs are written under the input folder:

- `json/<basename>.json`
- `svg/<mode>-<map>.svg`
- `png/<mode>-<map>.png`
- `org/<mode>-<map>.png` (lowercase; map at left, source tierlist at right)

For example, a Brawl Ball tierlist for Pinball Dreams produces
`svg/brawlball-pinballdreams.svg`, `png/brawlball-pinballdreams.png`, and
`org/brawlball-pinballdreams.png`; its JSON keeps the input basename.
Transparent map pixels use the fixed `#2b2b2b` title-background color. Each
run clears the existing `json/`,
`svg/`, `png/`, and `org/` output folders first; input images directly in the
selected folder are not removed. If multiple inputs resolve to the same
mode-map filename, the later one is reported as a failure rather than
overwriting the first. The `--reso` option applies to the rendered `png/`
output; the stitched `org/` image follows the source tierlist height.

Use `--reso WIDTHxHEIGHT` to select the PNG resolution, for example
`./ci/deepdraft.sh path/to/deepdraft-images --reso 1024x768`.

### TierMaker global tierlists

TierMaker screenshots use a different layout and produce a global-only
document. The title is required because TierMaker images do not contain map or
mode metadata:

macOS/Linux:

`./ci/run.sh extract --source tiermaker --title "June 2026" --from path/to/tiermaker.jpg --to /tmp/tiermaker.json`

Windows:

`ci\run.bat extract --source tiermaker --title "June 2026" --from path\to\tiermaker.jpg --to tiermaker.json`

The extractor detects the colored tier column, recognizes the labels, handles
wrapped avatar rows, and preserves the source order. The generated JSON stores
the supplied `title`, the `originalTierlist`, and the `globalRoles` view. Render
it with the same `generate` command:

`./ci/run.sh generate --from /tmp/tiermaker.json --to /tmp/tiermaker.svg`

The rendered title uses the prefix `BrawlStars Tierlist:` and the output has a
single `Common Classes` panel.

## Brawler Roles
- The official brawler classes can be midleading in draft process, e.g., Najia is used as a Range brawler (sniper) in open maps rather than a Damage Dealer (the official class).
- The same brawler may serve different purposes in different modes and maps, e.g., Barley can be a counter to other throwers when they are present, or a controller in a closed HotZone map.
- So we define a two-layer roles based on brawler's combat functions and map-mode functions; each brawler can have global and map/mode labels.
- The combat functions, inspired to BobbyBS, include:
  - Aggro: Creating tactical space on the frontline with swift movement and burst damage, countering low-HP brawlers
  - Anti-Tank: Countering Aggro and Tank with high-DPS attack
  - Controller: Countering Anti-Tank by controlling mid-range areas
  - Sniper: Countering Controllers and Anti-Tanks at long range on open maps
  - Support: Augmenting fellow brawlers into hybrid super class
  - Tank: High-HP slow-or-normal movement human-shields that counter low-HP brawlers (Snipers, Controllers, Throwers) on closed maps
  - Thrower: Countering everyone on walled maps, including Artillery brawlers and certain Support and Controllers such as Berry, Mr.P, Sirius, and Willow
- The mode functions, inspired by SpenLC, are (Flex means the brawler can either enhance the teammate as a support, or makes the opponent hard to counter due to its hybrid spec, e.g., Emz has high damage and controlling attack with certain self-defence skills, making her a Flex hard to counter):
  - Bounty: Damage, Support, Flex, Range, BlueStar/Pressure
  - Brawl Ball: Damage, Flex, Control, Pressure
  - Gem Grab: Carrier, Damage, Control, Pressure
  - Heist: Safe-Damage, Flex
  - HotZone: Zone-Time, Damage, Control, Pressure
  - Knockout: Range, Flex, Pressure
- `all.brawler.json` contains all the brawler data regarding the latest meta, including the said labels.

### Main-attack statistics
Each brawler's `mainAttack` stores `baseDamage` for one damage unit, `projectile` for the number of damage units in one shot, `damage` as the derived per-shot total, `ammo` for the number of stored shots, and `shape` as `singleShot`, `multiShot`, or `scattered`. Continuous attacks may also provide `durationSeconds` when their full stream has a different duration from the reload tick. `baseDamage`, `damage`, `projectile`, and `DPS` may be aligned arrays for alternate attack modes or values. Top-level `reloadSeconds` and `speedUnits` store reload time and movement speed. Derived statistics use `damage = baseDamage * projectile` and sustained `mainAttack.DPS = damage / (durationSeconds or reloadSeconds)`, rounded to the nearest integer; `ammo` describes magazine capacity and is not multiplied into sustained DPS.

### Bounty
- BlueStar: the brawlers that can easily grab the blue star at the beginning, usually those with swift movement such as Mortis, Max, or someone with a special teleport gadget such as Carl.
- Range: usually a Sniper (Marksman) or a support with long-range attack such as Gus and Byron.
- Pressure: Synonym of Aggro in the combat functions above.

### Brawl Ball
- Damage: Anti-Tank in combat functions.
- Flex: explained above in mode function overview.
- Pressure: Synonym for Aggro.

### Gem Grab
- Carrier: the mid brawler that has certain self-defence capability, such as crowd-control (CC) or teleport skills.
- Damage: Anti-Tank in combat functions.
- Control: Same as in combat factions.
- Pressure: Same as in other modes.

### Heist
- Safe-Damage: High-DPS brawlers, or certain brawler that can deal high damage to non-brawler objects (Mico using his second Starr Power).
- Flex: Brawlers that can both defend the team safe and damage the opponent safe, often those that can charge high-DPS super or teleport super, through defending the team safe, e.g., Nita, Bull, Crow.
- Defence: Brawlers that can defend the team safe by either defeating or disabling the opponent Safe-Damage brawlers but provide little to no value as Safe-Damage.

### HotZone
- Zone-Time: Brawlers with at least 7000 HP that can stand in the zone, or lower-HP brawlers with skills that control or deny the zone, force enemies out, secure enemy eliminations, or help teammates stay in the zone.
- Damage: Same as in other modes.
- Control: Same as in other modes.

### Knockout
- Flex: Brawlers can either enhance the teammate as a support, or makes the opponent hard to counter due to its hybrid nature, e.g., Emz has both high damage and area-control attack with certain self-defence skills, making her a Flex hard to counter; Ruffs can enhance teammates damage by farming super from Aggros (its hard counters), so although it has less self-defence, it can actually make the team stronger.
- Range: Same as in Bounty.
- Pressure: Same as in other modes.


## Dependencies
Python packages:
- `poetry install`

Tesseract OCR
- Windows: `winget install tesseract`
- macOS: `brew install tesseract`
