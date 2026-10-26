#!/usr/bin/env python3
"""
CLI argument parsing for bstier - Brawl Stars tierlist helper
"""

import argparse
import sys
from pathlib import Path

import src.core as core

# Add project root to Python path so imports work from any cwd
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# No longer need load_and_validate_meta import


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog='bstier',
        description='Brawl Stars tierlist helper CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract text tierlist from a Deepdraft map tierlist picture, then save to a file
  bstier extract --source deepdraft --from /path/to/tier.png --to /path/to/tier.json

  # Extract a Deepdraft tierlist and generate the M1 map-role document
  bstier extract --source deepdraft --master --from /path/to/tier.png --to /path/to/master.json

  # Extract a TierMaker global tierlist with a user-provided title
  bstier extract --source tiermaker --title "June 2026" --from /path/to/tier.png --to /path/to/tiermaker.json

  # Same as above, but print to screen only without saving as a file
  bstier extract --source deepdraft --from /path/to/tier.png 

  # Generate a tierlist picture from a text metadata file
  bstier generate --from /path/to/tier.json --to tier.svg

  # Same as above, but outputs to a rasterized picture
  bstier generate --from /path/to/tier.json --to tier.png --reso 1024x768

  # Generate five stat tierlists as JSON, SVG, PNG, and JPG
  bstier stats --to /path/to/stats-output

  # Convert a regular text tierlist to a class-based tierlist
  bstier convert --by class --from /path/to/tier-in.json --to /path/to/tier-out.json

  # Convert a regular tierlist to a lane-based tierlist
  bstier convert --by lane --from /path/to/tier-in.json --to /path/to/tier-out.json
""")

    # Global options
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # extract subcommand
    extract_parser = subparsers.add_parser('extract', help='Extract text tierlist from a tierlist picture')
    extract_parser.add_argument('-f', '--from', dest='fromPath', required=True, help='Path to the input tierlist picture')
    extract_parser.add_argument('-t', '--to', dest='toPath', help='Path to save the output JSON file')
    extract_parser.add_argument('-s', '--source', dest='source', choices=('deepdraft', 'tiermaker', ), default='deepdraft', required=True, help='Source tag that defines the tierlist image format')
    extract_parser.add_argument('--title', help='Title to persist for TierMaker global documents')
    extract_parser.add_argument('--master', action='store_true', help='Generate the M1 map and role document; currently supported for Deep-Draft input')

    # generate subcommand
    generate_parser = subparsers.add_parser('generate', help='Generate a tierlist picture from a text metadata file')
    generate_parser.add_argument('-f', '--from', dest='fromPath', required=True, help='Path to the input JSON file')
    generate_parser.add_argument('-t', '--to', dest='toPath', required=True, help='Path to save the output picture')
    generate_parser.add_argument(
        '--reso',
        help='PNG resolution (DeepDraft default: 2048x1536; TierMaker: content height at 2048 wide)',
    )

    stats_parser = subparsers.add_parser(
        'stats', help='Generate five brawler stat tierlists from the local catalog')
    stats_parser.add_argument('-t', '--to', dest='toPath', required=True,
                              help='Output folder for JSON, SVG, PNG, and JPG files')
    stats_parser.add_argument('--reso', help='PNG resolution in WIDTHxHEIGHT format')

    # convert subcommand
    convert_parser = subparsers.add_parser('convert', help='Convert a tierlist format')
    convert_parser.add_argument('-f', '--from', dest='fromPath', required=True, help='Path to the input JSON file')
    convert_parser.add_argument('-t', '--to', dest='toPath', required=True, help='Path to save the output JSON file')
    convert_parser.add_argument('-b', '--by', dest='convType', required=True, choices=('class', 'lane'), default='class', help='Conversion type')

    return parser


def main():
    """Main CLI entry point - only handles argument parsing."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Delegate all post-parse logic to core
    result, _ = core.main(args)
    sys.exit(0 if result.ok else 1)


if __name__ == '__main__':
    main()
