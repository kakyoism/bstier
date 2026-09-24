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

### Deep-Draft M1 extraction
To extract a Deep-Draft image and generate the map-aware M1 document, use the
`--master` option:

`poetry run bstier extract --source deepdraft --master --from tier.png --to master.json`

This path requires the `tesseract` executable to be available on `PATH`. OCR
returns raw text, which is resolved against `res/spec/all.map.json`; unknown
maps fail instead of being silently assigned. Without `--master`, extraction
continues to produce the original tierlist-only JSON output.

### M1 rendering
Render an M1 document as SVG or PNG with the existing `generate` command:

`poetry run bstier generate --from master.json --to master.svg`

`poetry run bstier generate --from master.json --to master.png`

PNG output defaults to `2048x1536`; use `--reso WIDTHxHEIGHT` to override it.

Role panels preserve the source-tier order and use the source tier as the
brawler tile border color. Missing avatar assets render as a placeholder.

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
  - Bounty: Range, BlueStar, Pressure
  - Brawl Ball: Damage, Flex, Pressure
  - Gem Grab: Carrier, Damage, Control, Pressure
  - Heist: Safe-Damage, Flex, Defence
  - HotZone: Zone-Time, Damage, Control
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
