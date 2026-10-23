"""Deterministic SVG and PNG rendering for tierlist documents."""

import base64
import dataclasses
import datetime
import html
import mimetypes
import pathlib
import re

import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont
import PIL.ImageOps as ImageOps


BACKGROUND = '#17152c'
PANEL_BACKGROUND = '#211e3c'
TIER_COLORS = {
    'S+': '#f4513f',
    'S': '#ff6d73',
    'A': '#f5a59b',
    'B': '#f7e6a1',
    'C': '#50dfc0',
    'D': '#61a8f4',
    'F': '#9c91f4',
}
TIERMAKER_TIER_COLORS = {
    'S+': '#e87582',
    'S': '#ee8582',
    'A': '#f5c388',
    'B': '#f9df8b',
    'C': '#fdff91',
    'D': '#cbfd8e',
    'F': '#a0fc8f',
}
TIER_ORDER = ('S+', 'S', 'A', 'B', 'C', 'D', 'F')
ROLE_COLORS = ('#51469d', '#3b65a0', '#34836f', '#966539', '#854876')
ROLE_WIDTH = 108
DEFAULT_PNG_RESOLUTION = (2048, 1536)
SIGNATURE_COLOR = '#aaa8b8'


@dataclasses.dataclass(frozen=True)
class TileLayout:
    name: str
    tier: str
    x: int
    y: int
    width: int
    height: int


@dataclasses.dataclass(frozen=True)
class RoleRowLayout:
    label: str
    y: int
    height: int
    tiles: tuple


@dataclasses.dataclass(frozen=True)
class PanelLayout:
    title: str
    x: int
    y: int
    width: int
    height: int
    rows: tuple


@dataclasses.dataclass(frozen=True)
class MapPanelLayout:
    x: int
    y: int
    width: int
    height: int
    image_path: object
    image_x: int
    image_y: int
    image_width: int
    image_height: int


@dataclasses.dataclass(frozen=True)
class DocumentLayout:
    width: int
    height: int
    panels: tuple
    map_panel: object
    role_width: int
    scale: float


def _normalize_identifier(value):
    return ''.join(character.casefold() for character in str(value)
                   if character.isalnum())


def _title_case(value):
    text = str(value).strip()
    text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', text)
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
    words = re.split(r'[\s_-]+', text)
    return ' '.join(word[:1].upper() + word[1:] for word in words if word)


def parse_resolution(value):
    """Parse a positive ``WIDTHxHEIGHT`` resolution or return ``None``."""
    if value is None:
        return None
    parts = str(value).lower().split('x')
    if len(parts) != 2:
        raise ValueError('Resolution must use WIDTHxHEIGHT format')
    try:
        resolution = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError('Resolution must contain integer dimensions') from exc
    if any(dimension <= 0 for dimension in resolution):
        raise ValueError('Resolution dimensions must be positive')
    return resolution


def _source_tiers(document):
    original = document.get('originalTierlist', document)
    result = {}
    for tier, names in original.items():
        if tier == 'version':
            continue
        for name in names:
            result[_normalize_identifier(name)] = tier
    return result


def _panel_groups(document):
    if 'globalRoles' in document and 'mapRoles' in document:
        return (
            ('Common Classes', document['globalRoles']),
            ('Map Roles', document['mapRoles']),
        )
    if 'globalRoles' in document:
        return (('Common Classes', document['globalRoles']),)
    return (('Tierlist', document.get('originalTierlist', document)),)


def _map_files(map_dir):
    if map_dir is None:
        return {}
    result = {}
    for path in sorted(pathlib.Path(map_dir).iterdir()):
        if path.suffix.casefold() not in {'.png', '.jpg', '.jpeg'}:
            continue
        result.setdefault(_normalize_identifier(path.stem), path)
    return result


def _scaled(value, scale):
    return max(1, int(round(value * scale)))


def _build_layout(document, width, map_dir, scale):
    """Build a layout at a compact, uniform geometry scale."""
    if width <= 0:
        raise ValueError('Layout width must be positive')

    margin = _scaled(24, scale)
    title_height = _scaled(112, scale)
    panel_gap = _scaled(20, scale)
    groups = _panel_groups(document)
    panel_count = len(groups)
    map_path = _map_files(map_dir).get(
        _normalize_identifier(document.get('map', '')))
    map_width = _scaled(300, scale) if document.get('map') else 0
    role_start_x = margin + map_width + panel_gap if map_width else margin
    role_area_width = width - role_start_x - margin
    panel_width = max(
        1,
        (role_area_width - panel_gap * (panel_count - 1)) // panel_count,
    )
    source_tiers = _source_tiers(document)
    role_width = _scaled(ROLE_WIDTH, scale)
    tile_width = _scaled(84, scale)
    tile_height = _scaled(76, scale)
    tile_gap = _scaled(6, scale)
    row_gap = _scaled(8, scale)
    panel_padding = _scaled(14, scale)
    panels = []

    for panel_index, (panel_title, role_groups) in enumerate(groups):
        panel_x = role_start_x + panel_index * (panel_width + panel_gap)
        row_y = (
            title_height
            + panel_padding
            + _scaled(48, scale)
        )
        rows = []
        for role_index, (role, names) in enumerate(role_groups.items()):
            names = list(names)
            usable_width = panel_width - role_width - 2 * panel_padding
            columns = max(1, (usable_width + tile_gap) // (tile_width + tile_gap))
            tiles = []
            for item_index, name in enumerate(names):
                row_index, column_index = divmod(item_index, columns)
                tiles.append(TileLayout(
                    name=name,
                    tier=source_tiers.get(_normalize_identifier(name), '*'),
                    x=(panel_x + panel_padding + role_width
                       + column_index * (tile_width + tile_gap)),
                    y=row_y + row_index * (tile_height + tile_gap),
                    width=tile_width,
                    height=tile_height,
                ))
            row_count = max(1, (len(names) + columns - 1) // columns)
            row_height = row_count * tile_height + (row_count - 1) * tile_gap
            rows.append(RoleRowLayout(role, row_y, row_height, tuple(tiles)))
            row_y += row_height + row_gap

        panel_height = max(100, row_y - title_height + panel_padding)
        panels.append(PanelLayout(
            title=panel_title,
            x=panel_x,
            y=title_height,
            width=panel_width,
            height=panel_height,
            rows=tuple(rows),
        ))

    footer_height = _scaled(72, scale)
    height = title_height + max(panel.height for panel in panels) + footer_height
    map_panel = None
    if map_width:
        map_x = margin
        map_y = title_height
        map_height = max(panel.height for panel in panels)
        image_area_width = max(1, map_width - 2 * panel_padding)
        image_area_height = max(1, map_height - _scaled(64, scale))
        source_width, source_height = (690, 1050)
        if map_path:
            with Image.open(map_path) as map_image:
                source_width, source_height = map_image.size
        image_scale = min(
            image_area_width / source_width,
            image_area_height / source_height,
        )
        image_width = max(1, int(source_width * image_scale))
        image_height = max(1, int(source_height * image_scale))
        map_panel = MapPanelLayout(
            x=map_x,
            y=map_y,
            width=map_width,
            height=map_height,
            image_path=map_path,
            image_x=map_x + (map_width - image_width) // 2,
            image_y=map_y + 48 + (image_area_height - image_height) // 2,
            image_width=image_width,
            image_height=image_height,
        )
    return DocumentLayout(
        width,
        height,
        tuple(panels),
        map_panel,
        role_width,
        scale,
    )


def build_layout(document, width=1600, map_dir=None, height=None):
    """Build shared absolute positions consumed by SVG and PNG renderers.

    When ``height`` is supplied, compact the geometry until the complete
    document fits the requested canvas. The returned positions remain in the
    requested coordinate system, so raster output does not need anisotropic
    post-render resizing.
    """
    if height is None:
        return _build_layout(document, width, map_dir, 1.0)
    if height <= 0:
        raise ValueError('Layout height must be positive')

    low = 0.01
    high = 1.0
    if _build_layout(document, width, map_dir, high).height <= height:
        scale = high
    else:
        for _ in range(32):
            candidate = (low + high) / 2
            if _build_layout(document, width, map_dir, candidate).height <= height:
                low = candidate
            else:
                high = candidate
        scale = low

    layout = _build_layout(document, width, map_dir, scale)
    return dataclasses.replace(layout, height=height)


def _avatar_files(avatar_dir):
    result = {}
    for path in sorted(pathlib.Path(avatar_dir).iterdir()):
        if path.suffix.casefold() not in {'.png', '.jpg', '.jpeg'}:
            continue
        result.setdefault(_normalize_identifier(path.stem), path)
    return result


def _image_uri(path):
    if path is None:
        return None
    content = base64.b64encode(path.read_bytes()).decode('ascii')
    media_type = mimetypes.guess_type(path.name)[0] or 'image/png'
    return f'data:{media_type};base64,{content}'


def _role_color(index):
    return ROLE_COLORS[index % len(ROLE_COLORS)]


def _document_title(document):
    if document.get('title'):
        return f'BrawlStars Tierlist: {document["title"]}'
    title = f'BrawlStars Tierlists: {_title_case(document.get("map", "Tierlist"))}'
    if document.get('mode'):
        title = f'{title} - {_title_case(document["mode"])}'
    return title


def _is_tiermaker_document(document):
    source = document.get('source')
    return source == 'tiermaker' or (
        'title' in document
        and 'map' not in document
        and 'mode' not in document
    )


def _tier_colors(document):
    """Return the source palette used for tier emphasis."""
    palette = (TIERMAKER_TIER_COLORS if _is_tiermaker_document(document)
               else TIER_COLORS).copy()
    for tier, color in document.get('tierColors', {}).items():
        if tier in palette and re.fullmatch(r'#[0-9a-fA-F]{6}', str(color)):
            palette[tier] = color
    return palette


def _signature(document):
    signature = f'Produced by kakyo on {datetime.date.today().isoformat()}'
    if _is_tiermaker_document(document):
        return signature
    return f'{signature} - Powered by DeepDraft'


def _fit_caption(draw, text, width, preferred_size):
    text = str(text)
    for size in range(max(1, preferred_size), 0, -1):
        font = ImageFont.load_default(size=size)
        if draw.textbbox((0, 0), text, font=font)[2] <= width:
            return text, font
    font = ImageFont.load_default(size=1)
    return _fit_text(draw, text, width, font), font


def _tile_visuals(tile, scale):
    avatar_padding = _scaled(14, scale)
    label_space = _scaled(20, scale)
    avatar_size = max(
        1,
        min(tile.width - 2 * avatar_padding, tile.height - label_space),
    )
    avatar_x = tile.x + (tile.width - avatar_size) // 2
    avatar_y = tile.y + _scaled(4, scale)
    underline_y = avatar_y + avatar_size
    return {
        'avatar_x': avatar_x,
        'avatar_y': avatar_y,
        'avatar_size': avatar_size,
        'underline_padding': _scaled(7, scale),
        'underline_y': underline_y,
        'underline_width': _scaled(5, scale),
    }


def _legend_layout(width, scale):
    block_width = _scaled(34, scale)
    block_height = _scaled(18, scale)
    gap = _scaled(6, scale)
    total_width = len(TIER_ORDER) * block_width + (len(TIER_ORDER) - 1) * gap
    start_x = width - _scaled(24, scale) - total_width
    y = _scaled(72, scale)
    return tuple(
        (
            tier,
            start_x + index * (block_width + gap),
            y,
            block_width,
            block_height,
        )
        for index, tier in enumerate(TIER_ORDER)
    )


def render_master_svg(document, avatar_dir, map_dir=None, width=1600):
    """Return a deterministic SVG for a master or tierlist document."""
    layout = build_layout(document, width, map_dir)
    avatars = _avatar_files(avatar_dir)
    tier_colors = _tier_colors(document)
    title = _document_title(document)
    panel_padding = _scaled(14, layout.scale)
    text_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    title, title_font = _fit_caption(
        text_draw,
        title,
        max(1, layout.width - 2 * panel_padding),
        _scaled(34, layout.scale),
    )
    parts = [
        (f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
         f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}">'),
        f'<rect width="100%" height="100%" fill="{BACKGROUND}"/>',
        (f'<text x="{layout.width // 2}" y="{_scaled(42, layout.scale)}" '
         'text-anchor="middle" font-family="sans-serif" '
         f'font-size="{title_font.size}" font-weight="bold" '
         f'fill="#ffffff">{html.escape(title)}</text>'),
    ]
    legend_font_size = _scaled(12, layout.scale)
    for tier, x, y, legend_width, legend_height in _legend_layout(
            layout.width, layout.scale):
        parts.append(
            f'<rect data-tier-legend="{html.escape(tier, quote=True)}" '
            f'x="{x}" y="{y}" width="{legend_width}" '
            f'height="{legend_height}" rx="{_scaled(4, layout.scale)}" '
            f'fill="{tier_colors[tier]}"/>')
        parts.append(
            f'<text x="{x + legend_width // 2}" '
            f'y="{y + legend_height - _scaled(4, layout.scale)}" '
            'text-anchor="middle" font-family="sans-serif" '
            f'font-size="{legend_font_size}" font-weight="bold" '
            f'fill="#ffffff">{html.escape(tier)}</text>')
    if layout.map_panel:
        map_panel = layout.map_panel
        parts.append(
            f'<rect x="{map_panel.x}" y="{map_panel.y}" width="{map_panel.width}" '
            f'height="{map_panel.height}" rx="12" fill="{PANEL_BACKGROUND}"/>')
        map_title, map_font = _fit_caption(
            text_draw,
            _title_case(document.get("map")),
            max(1, map_panel.width - 2 * panel_padding),
            _scaled(24, layout.scale),
        )
        parts.append(
            f'<text x="{map_panel.x + panel_padding}" '
            f'y="{map_panel.y + _scaled(28, layout.scale)}" '
            'font-family="sans-serif" '
            f'font-size="{map_font.size}" font-weight="bold" '
            f'fill="#ffffff">{html.escape(map_title)}</text>')
        map_uri = _image_uri(map_panel.image_path)
        if map_uri:
            parts.append(
                f'<image href="{map_uri}" x="{map_panel.image_x}" '
                f'y="{map_panel.image_y}" width="{map_panel.image_width}" '
                f'height="{map_panel.image_height}" preserveAspectRatio="xMidYMid meet"/>')
    for panel in layout.panels:
        parts.append(
            f'<rect x="{panel.x}" y="{panel.y}" width="{panel.width}" '
            f'height="{panel.height}" rx="12" fill="{PANEL_BACKGROUND}"/>')
        panel_title, panel_font = _fit_caption(
            text_draw,
            _title_case(panel.title),
            max(1, panel.width - 2 * panel_padding),
            _scaled(24, layout.scale),
        )
        parts.append(
            f'<text x="{panel.x + panel_padding}" '
            f'y="{panel.y + _scaled(28, layout.scale)}" '
            'font-family="sans-serif" '
            f'font-size="{panel_font.size}" font-weight="bold" '
            f'fill="#ffffff">{html.escape(panel_title)}</text>')
        for role_index, row in enumerate(panel.rows):
            role_x = panel.x + panel_padding
            role_y = row.y
            parts.append(
                f'<rect x="{role_x}" y="{role_y}" width="{layout.role_width}" '
                f'height="{row.height}" rx="8" fill="{_role_color(role_index)}"/>')
            role_label, role_font = _fit_caption(
                text_draw,
                _title_case(row.label),
                max(1, layout.role_width - 2 * panel_padding),
                _scaled(18, layout.scale),
            )
            parts.append(
                f'<text x="{role_x + layout.role_width // 2}" '
                f'y="{role_y + _scaled(24, layout.scale)}" '
                f'text-anchor="middle" font-family="sans-serif" '
                f'font-size="{role_font.size}" '
                f'font-weight="bold" fill="#ffffff">{html.escape(role_label)}</text>')
            for tile in row.tiles:
                tier_color = tier_colors.get(tile.tier, '#aaaaaa')
                visuals = _tile_visuals(tile, layout.scale)
                parts.append(
                    f'<rect data-brawler="{html.escape(str(tile.name), quote=True)}" '
                    f'x="{tile.x}" y="{tile.y}" width="{tile.width}" '
                    f'height="{tile.height}" rx="7" fill="#2b2947" stroke="none"/>')
                parts.append(
                    f'<line data-tier="{html.escape(str(tile.tier), quote=True)}" '
                    f'x1="{tile.x + visuals["underline_padding"]}" '
                    f'y1="{visuals["underline_y"]}" '
                    f'x2="{tile.x + tile.width - visuals["underline_padding"]}" '
                    f'y2="{visuals["underline_y"]}" '
                    f'stroke="{tier_color}" '
                    f'stroke-width="{visuals["underline_width"]}" '
                    'stroke-linecap="round"/>')
                uri = _image_uri(avatars.get(_normalize_identifier(tile.name)))
                if uri:
                    parts.append(
                        f'<image href="{uri}" x="{visuals["avatar_x"]}" '
                        f'y="{visuals["avatar_y"]}" '
                        f'width="{visuals["avatar_size"]}" '
                        f'height="{visuals["avatar_size"]}" '
                        'preserveAspectRatio="xMidYMid meet"/>')
                else:
                    parts.append(
                        f'<text x="{tile.x + tile.width // 2}" '
                        f'y="{tile.y + _scaled(36, layout.scale)}" '
                        'text-anchor="middle" font-family="sans-serif" '
                        f'font-size="{_scaled(20, layout.scale)}" '
                        'fill="#ffffff">?</text>')
    signature = html.escape(_signature(document))
    parts.append(
        f'<text x="{layout.width // 2}" '
        f'y="{layout.height - _scaled(24, layout.scale)}" '
        'text-anchor="middle" font-family="sans-serif" '
        f'font-size="{_scaled(24, layout.scale)}" fill="{SIGNATURE_COLOR}">'
        f'{signature}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def _fit_text(draw, text, width, font):
    original = str(text)
    if draw.textbbox((0, 0), original, font=font)[2] <= width:
        return original
    text = original
    while len(text) > 1 and draw.textbbox((0, 0), f'{text}…', font=font)[2] > width:
        text = text[:-1]
    return text if text == original else f'{text}…'


def render_master_png(document, avatar_dir, output_path, resolution=None, map_dir=None):
    """Render a master or tierlist document as PNG using the shared layout."""
    target = parse_resolution(resolution) or DEFAULT_PNG_RESOLUTION
    layout = build_layout(document, target[0], map_dir, target[1])
    canvas_size = target
    image = Image.new('RGB', canvas_size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    panel_padding = _scaled(14, layout.scale)
    avatars = _avatar_files(avatar_dir)
    tier_colors = _tier_colors(document)
    title, title_font = _fit_caption(
        draw,
        _document_title(document),
        max(1, layout.width - 2 * panel_padding),
        _scaled(34, layout.scale),
    )
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((layout.width - title_box[2]) // 2, _scaled(18, layout.scale)), title,
              fill='#ffffff', font=title_font)

    legend_font = ImageFont.load_default(size=_scaled(12, layout.scale))
    for tier, x, y, legend_width, legend_height in _legend_layout(
            layout.width, layout.scale):
        draw.rounded_rectangle(
            (x, y, x + legend_width, y + legend_height),
            radius=_scaled(4, layout.scale),
            fill=tier_colors[tier],
        )
        tier_box = draw.textbbox((0, 0), tier, font=legend_font)
        draw.text(
            (x + (legend_width - tier_box[2]) // 2,
             y + (legend_height - tier_box[3]) // 2),
            tier,
            fill='#ffffff',
            font=legend_font,
        )

    if layout.map_panel:
        map_panel = layout.map_panel
        map_title, map_font = _fit_caption(
            draw,
            _title_case(document.get('map')),
            max(1, map_panel.width - 2 * panel_padding),
            _scaled(24, layout.scale),
        )
        draw.rounded_rectangle(
            (map_panel.x, map_panel.y,
             map_panel.x + map_panel.width, map_panel.y + map_panel.height),
            radius=_scaled(12, layout.scale),
            fill=PANEL_BACKGROUND,
        )
        draw.text(
            (map_panel.x + panel_padding, map_panel.y + _scaled(14, layout.scale)),
            map_title,
            fill='#ffffff',
            font=map_font,
        )
        if map_panel.image_path:
            with Image.open(map_panel.image_path) as map_image:
                map_image = ImageOps.contain(
                    map_image.convert('RGBA'),
                    (map_panel.image_width, map_panel.image_height),
                    method=Image.Resampling.LANCZOS,
                )
                image.paste(
                    map_image,
                    (map_panel.image_x, map_panel.image_y),
                    map_image,
                )

    for panel in layout.panels:
        panel_title, panel_font = _fit_caption(
            draw,
            _title_case(panel.title),
            max(1, panel.width - 2 * panel_padding),
            _scaled(24, layout.scale),
        )
        draw.rounded_rectangle(
            (panel.x, panel.y, panel.x + panel.width, panel.y + panel.height),
            radius=_scaled(12, layout.scale),
            fill=PANEL_BACKGROUND,
        )
        draw.text(
            (panel.x + panel_padding, panel.y + _scaled(14, layout.scale)),
            panel_title,
            fill='#ffffff',
            font=panel_font,
        )
        for role_index, row in enumerate(panel.rows):
            role_x = panel.x + panel_padding
            role_y = row.y
            draw.rounded_rectangle(
                (role_x, role_y, role_x + layout.role_width, row.y + row.height),
                radius=_scaled(8, layout.scale),
                fill=_role_color(role_index),
            )
            role_label, role_font = _fit_caption(
                draw,
                _title_case(row.label),
                max(1, layout.role_width - 2 * panel_padding),
                _scaled(18, layout.scale),
            )
            role_box = draw.textbbox((0, 0), role_label, font=role_font)
            draw.text(
                (role_x + (layout.role_width - role_box[2]) // 2,
                 role_y + _scaled(10, layout.scale)),
                role_label,
                fill='#ffffff',
                font=role_font,
            )
            for tile in row.tiles:
                tier_color = tier_colors.get(tile.tier, '#aaaaaa')
                visuals = _tile_visuals(tile, layout.scale)
                draw.rounded_rectangle(
                    (tile.x, tile.y, tile.x + tile.width, tile.y + tile.height),
                    radius=_scaled(7, layout.scale),
                    fill='#2b2947',
                )
                draw.line(
                    (tile.x + visuals['underline_padding'], visuals['underline_y'],
                     tile.x + tile.width - visuals['underline_padding'],
                     visuals['underline_y']),
                    fill=tier_color,
                    width=visuals['underline_width'],
                )
                avatar_path = avatars.get(_normalize_identifier(tile.name))
                if avatar_path:
                    with Image.open(avatar_path) as avatar:
                        avatar = ImageOps.pad(
                            avatar.convert('RGBA'),
                            (visuals['avatar_size'], visuals['avatar_size']),
                            method=Image.Resampling.LANCZOS,
                            color=(0, 0, 0, 0),
                        )
                        image.paste(
                            avatar,
                            (visuals['avatar_x'], visuals['avatar_y']),
                            avatar,
                        )

    signature, signature_font = _fit_caption(
        draw,
        _signature(document),
        max(1, layout.width - 2 * panel_padding),
        _scaled(24, layout.scale),
    )
    signature_box = draw.textbbox((0, 0), signature, font=signature_font)
    draw.text(
        ((layout.width - signature_box[2]) // 2,
         layout.height - _scaled(24, layout.scale) - signature_box[3]),
        signature,
        fill=SIGNATURE_COLOR,
        font=signature_font,
    )
    image.save(output_path, format='PNG')


def render_document(document, avatar_dir, output_path, resolution=None, map_dir=None):
    """Render by output suffix, supporting SVG and PNG destinations."""
    output_path = pathlib.Path(output_path)
    suffix = output_path.suffix.casefold()
    target = parse_resolution(resolution)
    if suffix == '.svg':
        width = target[0] if target else 1600
        output_path.write_text(
            render_master_svg(document, avatar_dir, map_dir, width),
            encoding='utf-8',
        )
    elif suffix == '.png':
        render_master_png(document, avatar_dir, output_path, resolution, map_dir)
    else:
        raise ValueError('Output path must end with .svg or .png')
