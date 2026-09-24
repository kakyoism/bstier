# R&D

## Overview
This doc is the single source of truth of R&D plan, research findings, and design/implementation decisions.

## Milestone 1 (M1): Deep-Draft reshuffling by combat functions
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
