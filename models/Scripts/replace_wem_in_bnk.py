import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple


@dataclass(frozen=True)
class MediaEntry:
    index: int
    media_id: int
    offset: int
    size: int
    table_position: int


@dataclass(frozen=True)
class WemFormat:
    codec: int
    channels: int
    sample_rate: int
    channel_layout: int


def read_u32(data: bytes, position: int) -> int:
    return struct.unpack_from("<I", data, position)[0]


def find_bnk_chunks(data: bytes) -> Dict[bytes, Tuple[int, int]]:
    """Return {tag: (payload position, payload size)} for a Wwise BNK."""
    chunks = {}
    position = 0

    while position < len(data):
        if position + 8 > len(data):
            raise ValueError(f"BNK has {len(data) - position} trailing byte(s)")

        tag = bytes(data[position : position + 4])
        size = read_u32(data, position + 4)
        payload_position = position + 8
        chunk_end = payload_position + size
        if chunk_end > len(data):
            raise ValueError(
                f"BNK chunk {tag!r} ends outside the file: "
                f"{chunk_end} > {len(data)}"
            )
        if tag in chunks:
            raise ValueError(f"BNK contains more than one {tag!r} chunk")

        chunks[tag] = (payload_position, size)
        position = chunk_end

    return chunks


def read_media_entries(data: bytes, didx_position: int, didx_size: int):
    if didx_size % 12:
        raise ValueError(f"DIDX size {didx_size} is not divisible by 12")

    entries = []
    for index, relative_position in enumerate(range(0, didx_size, 12)):
        position = didx_position + relative_position
        media_id, offset, size = struct.unpack_from("<III", data, position)
        entries.append(MediaEntry(index, media_id, offset, size, position))
    return entries


def read_wem_format(data: bytes) -> WemFormat:
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("replacement is not a RIFF/WAVE WEM file")

    declared_size = read_u32(data, 4) + 8
    if declared_size != len(data):
        raise ValueError(
            f"WEM RIFF size is inconsistent: header={declared_size}, file={len(data)}"
        )

    position = 12
    while position + 8 <= len(data):
        tag = data[position : position + 4]
        size = read_u32(data, position + 4)
        payload_position = position + 8
        chunk_end = payload_position + size
        if chunk_end > len(data):
            raise ValueError(f"WEM chunk {tag!r} ends outside the file")
        if tag == b"fmt ":
            if size < 8:
                raise ValueError("WEM fmt chunk is too small")
            codec, channels, sample_rate = struct.unpack_from(
                "<HHI", data, payload_position
            )
            # Wwise Vorbis stores a private speaker/channel-layout value here.
            # Old DmC-era WEMs use plain masks (mono=4, stereo=3), while newer
            # encoders serialize AkChannelConfig differently (ex. 0x4101 and
            # 0x3102). The old decoder may tolerate this for mono but fail hard
            # when stereo channel coupling is initialized.
            channel_layout = (
                read_u32(data, payload_position + 20)
                if codec == 0xFFFF and size >= 24
                else 0
            )
            return WemFormat(codec, channels, sample_rate, channel_layout)
        position = chunk_end + (size & 1)

    raise ValueError("WEM has no fmt chunk")


def read_wem_chunk_tags(data: bytes) -> Tuple[bytes, ...]:
    """Return RIFF chunk tags in order, validating their boundaries."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("file is not a RIFF/WAVE WEM file")

    tags = []
    position = 12
    while position < len(data):
        if position + 8 > len(data):
            raise ValueError("WEM has trailing bytes outside a RIFF chunk")
        tag = bytes(data[position : position + 4])
        size = read_u32(data, position + 4)
        chunk_end = position + 8 + size
        if chunk_end > len(data):
            raise ValueError(f"WEM chunk {tag!r} ends outside the file")
        tags.append(tag)
        position = chunk_end + (size & 1)

    return tuple(tags)


def set_wem_channel_layout(data: bytearray, channel_layout: int) -> None:
    """Patch the private Wwise Vorbis channel-layout field in memory."""
    position = 12
    while position + 8 <= len(data):
        tag = bytes(data[position : position + 4])
        size = read_u32(data, position + 4)
        payload_position = position + 8
        chunk_end = payload_position + size
        if chunk_end > len(data):
            raise ValueError(f"WEM chunk {tag!r} ends outside the file")
        if tag == b"fmt ":
            if size < 24:
                raise ValueError("WEM fmt chunk is too small for channel layout")
            struct.pack_into("<I", data, payload_position + 20, channel_layout)
            return
        position = chunk_end + (size & 1)
    raise ValueError("WEM has no fmt chunk")


def format_description(value: WemFormat) -> str:
    return (
        f"codec=0x{value.codec:04X}, channels={value.channels}, "
        f"sample_rate={value.sample_rate}, "
        f"channel_layout=0x{value.channel_layout:08X}"
    )


def patch_bnk(
    source_bnk: Path,
    replacement_wem: Path,
    media_id: int,
    output_bnk: Path,
    force_incompatible: bool = False,
    dry_run: bool = False,
) -> None:
    bnk_data = bytearray(source_bnk.read_bytes())
    replacement_data = bytearray(replacement_wem.read_bytes())
    chunks = find_bnk_chunks(bnk_data)

    if b"DIDX" not in chunks or b"DATA" not in chunks:
        raise ValueError("BNK must contain both DIDX and DATA chunks")

    didx_position, didx_size = chunks[b"DIDX"]
    data_position, data_size = chunks[b"DATA"]
    entries = read_media_entries(bnk_data, didx_position, didx_size)
    matches = [entry for entry in entries if entry.media_id == media_id]
    if not matches:
        raise ValueError(f"media ID {media_id} was not found in {source_bnk}")
    if len(matches) != 1:
        raise ValueError(f"media ID {media_id} occurs {len(matches)} times in the BNK")

    target = matches[0]
    later_offsets = [entry.offset for entry in entries if entry.offset > target.offset]
    slot_end = min(later_offsets) if later_offsets else data_size
    slot_capacity = slot_end - target.offset

    if target.offset + target.size > data_size:
        raise ValueError("the original DIDX entry points outside the DATA chunk")
    if len(replacement_data) > slot_capacity:
        raise ValueError(
            f"replacement is too large: {len(replacement_data)} bytes, "
            f"slot capacity is {slot_capacity} bytes"
        )

    original_start = data_position + target.offset
    original_wem = bytes(bnk_data[original_start : original_start + target.size])
    original_format = read_wem_format(original_wem)
    replacement_format = read_wem_format(replacement_data)
    original_chunk_tags = read_wem_chunk_tags(original_wem)
    replacement_chunk_tags = read_wem_chunk_tags(replacement_data)

    print(f"BNK:             {source_bnk}")
    print(f"Media ID/index:  {target.media_id} / {target.index}")
    print(f"Original WEM:    {target.size} bytes; {format_description(original_format)}")
    print(
        f"Replacement WEM: {len(replacement_data)} bytes; "
        f"{format_description(replacement_format)}"
    )
    print(f"Fixed slot:      offset={target.offset}, capacity={slot_capacity} bytes")
    print(
        "RIFF chunks:     "
        + " -> ".join(tag.decode("ascii", "replace") for tag in replacement_chunk_tags)
    )

    # DmC's Wwise v65 banks duplicate the embedded media's absolute file
    # offset and size in HIRC/AkMediaInformation:
    #   sourceID, fileID, fileOffset, inMemoryMediaSize
    # Updating DIDX alone leaves the sound object reading the old byte count.
    hirc_references = []
    if b"HIRC" in chunks:
        hirc_position, hirc_size = chunks[b"HIRC"]
        hirc_end = hirc_position + hirc_size
        expected_file_offset = original_start
        media_id_bytes = struct.pack("<I", media_id)
        search_position = hirc_position
        while True:
            reference_position = bnk_data.find(
                media_id_bytes, search_position, hirc_end
            )
            if reference_position < 0:
                break
            if reference_position + 16 <= hirc_end:
                stored_offset = read_u32(bnk_data, reference_position + 8)
                stored_size = read_u32(bnk_data, reference_position + 12)
                if (
                    stored_offset == expected_file_offset
                    and stored_size == target.size
                ):
                    hirc_references.append(reference_position)
            search_position = reference_position + 4

    if not hirc_references:
        raise ValueError(
            "no matching HIRC/AkMediaInformation reference was found; "
            "refusing to create a partially updated BNK"
        )
    print(f"HIRC references: {len(hirc_references)} size field(s) will be updated")

    core_format_matches = (
        original_format.codec == replacement_format.codec
        and original_format.channels == replacement_format.channels
        and original_format.sample_rate == replacement_format.sample_rate
    )
    if not core_format_matches and not force_incompatible:
        raise ValueError(
            "replacement codec/channels/sample rate do not match the original; "
            "create a compatible WEM or explicitly use --force-incompatible"
        )
    if (
        core_format_matches
        and original_format.codec == 0xFFFF
        and original_format.channel_layout != replacement_format.channel_layout
    ):
        print(
            "[Auto-fix] Wwise Vorbis channel layout: "
            f"0x{replacement_format.channel_layout:08X} -> "
            f"0x{original_format.channel_layout:08X}"
        )
        set_wem_channel_layout(replacement_data, original_format.channel_layout)
        replacement_format = read_wem_format(replacement_data)
        print("[Auto-fix] Source WEM was not modified; only the BNK copy is patched.")
    if original_chunk_tags != replacement_chunk_tags and not force_incompatible:
        original_text = " -> ".join(
            tag.decode("ascii", "replace") for tag in original_chunk_tags
        )
        replacement_text = " -> ".join(
            tag.decode("ascii", "replace") for tag in replacement_chunk_tags
        )
        raise ValueError(
            "replacement RIFF chunk layout does not match the original: "
            f"{replacement_text} != {original_text}; this commonly means the WEM "
            "was generated by an incompatible Wwise version"
        )

    if dry_run:
        print("Dry run passed; no file was written.")
        return

    absolute_slot_end = data_position + slot_end
    bnk_data[original_start:absolute_slot_end] = (
        replacement_data + b"\x00" * (slot_capacity - len(replacement_data))
    )
    struct.pack_into("<I", bnk_data, target.table_position + 8, len(replacement_data))
    for reference_position in hirc_references:
        struct.pack_into("<I", bnk_data, reference_position + 12, len(replacement_data))

    if len(bnk_data) != source_bnk.stat().st_size:
        raise AssertionError("internal error: output BNK size changed")

    output_bnk.parent.mkdir(parents=True, exist_ok=True)
    output_bnk.write_bytes(bnk_data)
    print(f"Written:         {output_bnk} ({len(bnk_data)} bytes)")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Replace one embedded WEM without rebuilding or resizing the BNK. "
            "DIDX offsets, DATA alignment, other chunks, and total size are preserved."
        )
    )
    parser.add_argument("source_bnk", type=Path)
    parser.add_argument("replacement_wem", type=Path)
    parser.add_argument("media_id", type=int)
    parser.add_argument("output_bnk", type=Path)
    parser.add_argument(
        "--force-incompatible",
        action="store_true",
        help="allow codec/channel/sample-rate mismatches (normally unsafe)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="validate only; do not write output"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        patch_bnk(
            args.source_bnk,
            args.replacement_wem,
            args.media_id,
            args.output_bnk,
            args.force_incompatible,
            args.dry_run,
        )
    except (OSError, ValueError) as error:
        raise SystemExit(f"[Error] {error}") from error
