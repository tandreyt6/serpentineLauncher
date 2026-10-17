from Core.application.diagnostics import diagnostic
import struct
import zlib

from Core.application.contracts import CoreError
from Core.application.settings import CoreConfig


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def sanitized_png(data: bytes, config: CoreConfig) -> tuple[int, int, bytes]:
    if len(data) > config.mod_icon_bytes or not data.startswith(PNG_SIGNATURE):
        raise CoreError(diagnostic('mod_icons.icon.must.be.a.bounded.png'))
    position = len(PNG_SIGNATURE)
    chunks = []
    image_data = []
    width = height = depth = color = 0
    palette = b""
    transparency_seen = False
    idat_finished = False
    end_seen = False
    while position < len(data):
        if position + 12 > len(data):
            raise CoreError(diagnostic('mod_icons.truncated.png.chunk'))
        size, kind = struct.unpack_from(">I4s", data, position)
        end = position + 12 + size
        if end > len(data) or kind[2] & 32 or any(not 65 <= char <= 90 and not 97 <= char <= 122 for char in kind):
            raise CoreError(diagnostic('mod_icons.invalid.png.chunk'))
        payload = data[position + 8:end - 4]
        checksum = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != checksum:
            raise CoreError(diagnostic('mod_icons.png.crc.mismatch'))
        if not chunks and kind != b"IHDR":
            raise CoreError(diagnostic('mod_icons.png.must.begin.with.ihdr'))
        if kind == b"IHDR":
            if chunks or size != 13:
                raise CoreError(diagnostic('mod_icons.invalid.png.ihdr'))
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if not width or not height or max(width, height) > config.mod_icon_dimension or width * height > config.mod_icon_pixels:
                raise CoreError(diagnostic('mod_icons.png.exceeds.dimension.limit'))
            if color not in PNG_DEPTHS or depth not in PNG_DEPTHS[color] or compression or filtering or interlace:
                raise CoreError(diagnostic('mod_icons.unsupported.png.encoding.or.interlacing'))
        elif kind == b"PLTE":
            if palette or image_data or color in (0, 4) or not size or size % 3 or size > 768 or color == 3 and size // 3 > 2 ** depth:
                raise CoreError(diagnostic('mod_icons.invalid.png.palette'))
            palette = payload
        elif kind == b"tRNS":
            if transparency_seen or image_data or color in (4, 6) or color == 0 and size != 2 or color == 2 and size != 6 or color == 3 and (not palette or not 0 < size <= len(palette) // 3):
                raise CoreError(diagnostic('mod_icons.invalid.png.transparency'))
            transparency_seen = True
        elif kind == b"IDAT":
            if idat_finished or color == 3 and not palette:
                raise CoreError(diagnostic('mod_icons.invalid.png.idat.order'))
            image_data.append(payload)
        elif kind == b"IEND":
            if size or not image_data or end != len(data):
                raise CoreError(diagnostic('mod_icons.invalid.png.end'))
            end_seen = True
        elif not kind[0] & 32:
            raise CoreError(diagnostic('mod_icons.unknown.critical.png.chunk'))
        if image_data and kind != b"IDAT":
            idat_finished = True
        if kind in (b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND"):
            chunks.append(data[position:end])
        position = end
    if not end_seen:
        raise CoreError(diagnostic('mod_icons.png.iend.is.missing'))
    row_bytes = (width * PNG_CHANNELS[color] * depth + 7) // 8 + 1
    expected = row_bytes * height
    if expected > config.mod_icon_decoded_bytes:
        raise CoreError(diagnostic('mod_icons.png.exceeds.decoded.size.limit'))
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(b"".join(image_data), expected + 1)
    if len(decoded) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise CoreError(diagnostic('mod_icons.invalid.or.oversized.png.image.stream'))
    if any(decoded[position] > 4 for position in range(0, expected, row_bytes)):
        raise CoreError(diagnostic('mod_icons.invalid.png.filter'))
    return width, height, PNG_SIGNATURE + b"".join(chunks)
