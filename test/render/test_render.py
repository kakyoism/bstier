import pathlib
import sys
import json
import datetime

import PIL.Image as Image
import pytest


_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / 'src'))

import render
import core


def _master_document():
    return {
        'map': 'pinballDreams',
        'mode': 'brawlBall',
        'originalTierlist': {'S': ['gus', 'bull'], 'F': ['8bit']},
        'globalRoles': {'aggro': ['bull'], 'sniper': ['gus'], 'support': ['8bit']},
        'mapRoles': {'damage': ['bull'], 'flex': ['gus'], 'control': ['8bit']},
    }


def _tiermaker_document():
    return {
        'title': 'June 2026',
        'originalTierlist': {'S': ['gus'], 'F': ['8bit']},
        'globalRoles': {'sniper': ['gus'], 'support': ['8bit']},
    }


def test_svg_uses_role_views_and_source_order():
    svg = render.render_master_svg(
        _master_document(),
        _ROOT / 'res/avatar',
        _ROOT / 'res/map',
        width=900,
    )
    layout = render.build_layout(
        _master_document(),
        width=900,
        map_dir=_ROOT / 'res/map',
    )

    assert svg.startswith('<svg ')
    assert 'Common Classes' in svg
    assert 'Map Roles' in svg
    assert layout.map_panel.image_path.name == 'Pinball_Dreams.png'
    assert layout.map_panel.image_width / layout.map_panel.image_height < 1
    assert svg.index('data-brawler="bull"') < svg.index('data-brawler="gus"')
    assert 'data-brawler="8bit"' in svg
    assert 'BrawlStars Tierlists: Pinball Dreams - Brawl Ball' in svg
    assert (
        f'Produced by kakyo on {datetime.date.today().isoformat()} '
        '- Powered by DeepDraft'
    ) in svg
    assert f'fill="{render.SIGNATURE_COLOR}"' in svg
    assert 'Aggro' in svg
    assert 'Damage' in svg
    legend = render._legend_layout(layout.width, layout.scale)
    assert legend[-1][1] + legend[-1][3] == layout.width - render._scaled(
        24, layout.scale)
    assert legend[-1][2] + legend[-1][4] < layout.panels[0].y
    for tier in ('S+', 'S', 'A', 'B', 'C', 'D', 'F'):
        assert f'data-tier-legend="{tier}"' in svg
    assert 'fill="#51469d"' in svg
    assert 'font-weight="bold"' in svg
    assert '>bull</text>' not in svg
    assert '>gus</text>' not in svg
    assert 'preserveAspectRatio="xMidYMid meet"' in svg
    assert 'data-tier="S"' in svg
    assert 'stroke-width="5" stroke-linecap="round"' in svg
    assert 'stroke="#50dfc0" stroke-width="3"' not in svg


def test_caption_values_use_title_case():
    assert render._title_case('pinballDreams') == 'Pinball Dreams'
    assert render._title_case('brawlBall') == 'Brawl Ball'
    assert render._title_case('antiTank') == 'Anti Tank'


def test_svg_renders_tiermaker_as_one_common_classes_panel():
    svg = render.render_master_svg(
        _tiermaker_document(),
        _ROOT / 'res/avatar',
        _ROOT / 'res/map',
        width=900,
    )

    assert 'BrawlStars Tierlist: June 2026' in svg
    assert 'Common Classes' in svg
    assert 'Map Roles' not in svg
    assert '- Powered by DeepDraft' not in svg
    assert f'Produced by kakyo on {datetime.date.today().isoformat()}' in svg
    assert svg.count('<rect x=') >= 3


def test_svg_uses_tiermaker_colors_for_tier_underlines():
    svg = render.render_master_svg(
        _tiermaker_document(),
        _ROOT / 'res/avatar',
        _ROOT / 'res/map',
        width=900,
    )

    assert f'stroke="{render.TIERMAKER_TIER_COLORS["S"]}"' in svg
    assert f'stroke="{render.TIER_COLORS["S"]}"' not in svg


def test_png_uses_same_layout_and_requested_resolution(tmp_path):
    output_path = tmp_path / 'master.png'

    render.render_document(
        _master_document(),
        _ROOT / 'res/avatar',
        output_path,
        resolution='320x240',
        map_dir=_ROOT / 'res/map',
    )

    with Image.open(output_path) as image:
        assert image.size == (320, 240)
        assert image.mode == 'RGB'


def test_png_uses_high_resolution_default(tmp_path):
    output_path = tmp_path / 'master-default.png'

    render.render_document(
        _master_document(),
        _ROOT / 'res/avatar',
        output_path,
        map_dir=_ROOT / 'res/map',
    )

    with Image.open(output_path) as image:
        assert image.size == render.DEFAULT_PNG_RESOLUTION


def test_requested_png_resolution_reflows_without_stretching_avatars():
    dense_document = _master_document()
    names = [f'brawler-{index}' for index in range(24)]
    dense_document['globalRoles'] = {
        f'role-{index}': names for index in range(7)
    }
    dense_document['mapRoles'] = {
        f'map-role-{index}': names for index in range(4)
    }
    layout = render.build_layout(
        dense_document,
        width=1024,
        map_dir=_ROOT / 'res/map',
        height=768,
    )

    assert layout.width == 1024
    assert layout.height == 768
    assert layout.scale < 1
    for panel in layout.panels:
        for row in panel.rows:
            for tile in row.tiles:
                visuals = render._tile_visuals(tile, layout.scale)
                assert visuals['avatar_size'] > 0
                avatar_padding = render._scaled(14, layout.scale)
                label_space = render._scaled(20, layout.scale)
                expected_size = max(
                    1,
                    min(
                        tile.width - 2 * avatar_padding,
                        tile.height - label_space,
                    ),
                )
                assert visuals['avatar_size'] == expected_size
                assert visuals['underline_y'] == (
                    visuals['avatar_y'] + visuals['avatar_size']
                )
                assert tile.x + tile.width <= layout.width
                assert tile.y + tile.height <= layout.height


def test_generate_worker_writes_png(tmp_path):
    input_path = tmp_path / 'master.json'
    output_path = tmp_path / 'master.png'
    input_path.write_text(json.dumps(_master_document()))
    args = type('Args', (), {
        'command': 'generate',
        'fromPath': str(input_path),
        'toPath': str(output_path),
        'reso': '320x240',
    })()

    result, output = core.main(args)

    assert result.ok is True
    assert output.toPath == str(output_path)
    with Image.open(output_path) as image:
        assert image.size == (320, 240)


@pytest.mark.parametrize('value', ['320', '0x240', '320x0', 'badxsize'])
def test_invalid_resolution_raises_value_error(value):
    with pytest.raises(ValueError):
        render.parse_resolution(value)