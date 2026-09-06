import struct

import ndspy.nftr
import pytest


def _pad(data, alignment=4):
    return data + b'\0' * (-len(data) % alignment)


def _magic(name, reversed_magic):
    return name[::-1] if reversed_magic else name


def _build_nftr(endianness='<', reversed_magic=True):
    glyphs = [bytes([0x1B]), bytes([0xE4])]
    cglp = bytearray(struct.pack(
        endianness + '4sIBBHHBB',
        _magic(b'CGLP', reversed_magic),
        0,
        2,
        2,
        1,
        0x1234,
        2,
        0,
    ))
    cglp.extend(b''.join(glyphs))
    cglp = bytearray(_pad(cglp))
    struct.pack_into(endianness + 'I', cglp, 4, len(cglp))

    cwdh = bytearray(struct.pack(
        endianness + '4sIHHI',
        _magic(b'CWDH', reversed_magic),
        0,
        0,
        1,
        0,
    ))
    cwdh.extend(struct.pack(endianness + 'bBBbBB', -1, 2, 3, 0, 2, 2))
    cwdh = bytearray(_pad(cwdh))
    struct.pack_into(endianness + 'I', cwdh, 4, len(cwdh))

    cmap = bytearray(struct.pack(
        endianness + '4sIHHHHI',
        _magic(b'CMAP', reversed_magic),
        0,
        0x41,
        0x5A,
        2,
        7,
        0,
    ))
    cmap.extend(struct.pack(endianness + 'H', 2))
    cmap.extend(struct.pack(endianness + 'HHHH', 0x41, 0, 0x5A, 1))
    cmap = bytearray(_pad(cmap))
    struct.pack_into(endianness + 'I', cmap, 4, len(cmap))

    finf_size = 0x20
    cglp_offset = 0x10 + finf_size
    cwdh_offset = cglp_offset + len(cglp)
    cmap_offset = cwdh_offset + len(cwdh)
    finf = struct.pack(
        endianness + '4sIBBHbBBBIII4B',
        _magic(b'FINF', reversed_magic),
        finf_size,
        0,
        8,
        1,
        -1,
        2,
        3,
        2,
        cglp_offset + 8,
        cwdh_offset + 8,
        cmap_offset + 8,
        8,
        2,
        1,
        0,
    )

    body = finf + cglp + cwdh + cmap
    return struct.pack(
        endianness + '4sHHIHH',
        _magic(b'NFTR', reversed_magic),
        0xFEFF,
        0x0102,
        0x10 + len(body),
        0x10,
        4,
    ) + body


@pytest.mark.parametrize(
    'endianness,reversed_magic',
    [('<', True), ('>', False)],
)
def test_load_and_save(endianness, reversed_magic):
    data = _build_nftr(endianness, reversed_magic)
    font = ndspy.nftr.NFTR(data)

    assert font.endianness == endianness
    assert font.reversedMagic is reversed_magic
    assert font.version == 0x0102
    assert font.defaultWidth.left == -1
    assert font.glyphWidth == 2
    assert font.glyphHeight == 2
    assert font.bpp == 2
    assert font.cglpUnknown == 0x1234
    assert len(font.glyphs) == 2
    assert font.glyphs[0].getPixels() == [0, 1, 2, 3]
    assert font.glyphs[1].getPixels() == [3, 2, 1, 0]
    assert font.widths[0].left == -1
    assert font.widths[1].charWidth == 2
    assert font.characterMap == {0x41: 0, 0x5A: 1}
    assert font.mappingBlocks[0].unknown == 7
    assert font.save() == data


@pytest.mark.parametrize('bpp', [1, 2, 3, 4])
def test_glyph_pixel_round_trip(bpp):
    width = 8
    height = 1
    mask = (1 << bpp) - 1
    pixels = [index & mask for index in range(width)]
    data_length = (width * height * bpp + 7) // 8
    glyph = ndspy.nftr.Glyph(width, height, bpp, bytes(data_length))
    glyph.setPixels(pixels)
    assert glyph.getPixels() == pixels


def test_invalid_pixel_value():
    glyph = ndspy.nftr.Glyph(1, 1, 1, b'\0')
    with pytest.raises(ValueError):
        glyph.setPixels([2])


def test_truncated_file():
    with pytest.raises(ValueError):
        ndspy.nftr.NFTR(b'RTFN')


def test_multiple_width_and_mapping_blocks():
    font = ndspy.nftr.NFTR(_build_nftr())
    font.widthBlocks = [
        ndspy.nftr.WidthBlock(0, [ndspy.nftr.CharacterWidth(-1, 2, 3)]),
        ndspy.nftr.WidthBlock(1, [ndspy.nftr.CharacterWidth(0, 2, 2)]),
    ]
    font.mappingBlocks = [
        ndspy.nftr.MappingBlock(0x20, 0x20, 0, {0x20: 0}),
        ndspy.nftr.MappingBlock(0x30, 0x31, 1, {0x31: 1}),
        ndspy.nftr.MappingBlock(0x41, 0x41, 2, {0x41: 0}),
    ]

    saved = font.save()
    loaded = ndspy.nftr.NFTR(saved)
    assert [block.firstGlyphIndex for block in loaded.widthBlocks] == [0, 1]
    assert [block.type for block in loaded.mappingBlocks] == [0, 1, 2]
    assert loaded.characterMap == {0x20: 0, 0x31: 1, 0x41: 0}
    assert loaded.save() == saved


def test_finf_without_extended_metrics():
    font = ndspy.nftr.NFTR(_build_nftr())
    font.fontHeight = None
    font.fontWidth = None
    font.bearingY = None
    font.bearingX = None

    loaded = ndspy.nftr.NFTR(font.save())
    assert loaded.fontHeight is None
    assert loaded.save() == font.save()
