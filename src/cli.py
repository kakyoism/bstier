#!/usr/bin/env python3
"""
CLI argument parsing for bstier - Brawl Stars tierlist helper
"""

import argparse
import sys
from pathlib import Path

# Add project root to Python path so imports work from any cwd
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# No longer need load_and_validate_meta import


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog='bstier-cli',
        description='Brawl Stars tierlist helper CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract text tierlist from a Deepdraft map tierlist picture, then save to a file
  bstier-cli extract --source deepdraft --from /path/to/tier.png --to /path/to/tier.json

  # Same as above, but print to screen only without saving as a file
  bstier-cli extract --source deepdraft --from /path/to/tier.png 

  # Generate a tierlist picture from a text metadata file
  bstier-cli generate --from /path/to/tier.json --to tier.svg

  # Same as above, but outputs to a rasterized picture
  bstier-cli generate --from /path/to/tier.json --to tier.png --reso 1024x768

  # Convert a regular text tierlist to a class-based tierlist
  bstier-cli convert --by class --from /path/to/tier-in.json --to /path/to/tier-out.json

  # Convert a regular tierlist to a lane-based tierlist
  bstier-cli convert --by lane --from /path/to/tier-in.json --to /path/to/tier-out.json
""")

    # Global options
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # extract subcommand
    extract_parser = subparsers.add_parser('extract', help='Extract text tierlist from a tierlist picture')
    extract_parser.add_argument('--from', dest='fromPath', required=True, help='Path to the input tierlist picture')
    extract_parser.add_argument('--to', dest='toPath', help='Path to save the output JSON file')
    extract_parser.add_argument('--source', '-s', dest='source', choices=('deepdraft', 'tiermaker', ), default='deepdraft', required=True, help='Source tag that defines the tierlist image format')

    # generate subcommand
    generate_parser = subparsers.add_parser('generate', help='Generate a tierlist picture from a text metadata file')
    generate_parser.add_argument('--from', dest='fromPath', required=True, help='Path to the input JSON file')
    generate_parser.add_argument('--to', dest='toPath', required=True, help='Path to save the output picture')
    generate_parser.add_argument('--reso', help='Resolution for the rasterized picture (e.g., 1024x768)')

    # convert subcommand
    convert_parser = subparsers.add_parser('convert', help='Convert a tierlist format')
    convert_parser.add_argument('--from', dest='fromPath', required=True, help='Path to the input JSON file')
    convert_parser.add_argument('--to', dest='toPath', required=True, help='Path to save the output JSON file')
    convert_parser.add_argument('--by', dest='convType', required=True, choices=('class', 'lane'), default='class', help='Conversion type')

    return parser


def main():
    """Main CLI entry point - only handles argument parsing."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Delegate all post-parse logic to core
    from src.core import main as core_main
    sys.exit(core_main(args))


if __name__ == '__main__':
    main()