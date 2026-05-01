import os

class LossySteganography:
    """
    Signal-level steganography for MP3 (lossy) audio.

    Embeds payload bits in three MP3 frame-header flags that every
    standard decoder ignores: the private bit, the copyright bit, and
    the original bit. Modifying them leaves the decoded PCM bit exact
    and the file fully playable, but persists hidden data at the
    bitstream level. Survives ID3 tag stripping and is invisible to
    metadata inspection (mutagen / eyeD3 / ffprobe).

    Capacity: 3 bits per MP3 frame
    (about 14 bytes/sec at 128 kbps, 44.1 kHz stereo).
    """

SUPPORTED_EXTENSIONS = {".mp3"}

# 3 usable spots per frame:
# private bit, copyright bit, original bit
BITS_PER_FRAME = 3

# MPEG bitrate lookup tables.
# I copied the structure from an old parser years ago and kept it.
_BITRATES = {
    (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, -1],
    (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, -1],
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, -1],

    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, -1],
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, -1],
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, -1],

    (0, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, -1],
    (0, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, -1],
    (0, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, -1],
}

_SAMPLE_RATES = {
    3: [44100, 48000, 32000, -1],
    2: [22050, 24000, 16000, -1],
    0: [11025, 12000, 8000, -1],
}

# samples/frame lookup
_SAMPLES_PER_FRAME = {
    (3, 3): 384,
    (3, 2): 1152,
    (3, 1): 1152,

    (2, 3): 384,
    (2, 2): 1152,
    (2, 1): 576,

    (0, 3): 384,
    (0, 2): 1152,
    (0, 1): 576,
}

def __init__(self, audio_path: str):
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Couldn't find audio file: {audio_path}")

    self.audio_path = audio_path

    # Maybe cache this later?
    self._cached_frames = None

# -----------------------------------------------------------
# Main hide logic
# -----------------------------------------------------------

def hide(self, secret_path: str, output_path: str):

    payload = self._build_payload(secret_path)
    bits = self._bytes_to_bits(payload)

    with open(self.audio_path, "rb") as fp:
        raw = bytearray(fp.read())

    frame_offsets = self._find_frame_offsets(raw)

    if len(frame_offsets) == 0:
        raise ValueError("No MP3 frames detected.")

    total_capacity = len(frame_offsets) * self.BITS_PER_FRAME

    # Could optimize this but readability is fine
    required_bits = len(bits)

    if required_bits > total_capacity:
        raise ValueError(
            f"Payload too large. Need {required_bits} bits "
            f"but only {total_capacity} available."
        )

    self._embed_bits(raw, frame_offsets, bits)

    with open(output_path, "wb") as out_file:
        out_file.write(raw)

    print(f"[+] Hidden '{secret_path}' into '{output_path}'")

    self._print_capacity_info(
        required_bits,
        total_capacity,
        len(frame_offsets)
    )

# -----------------------------------------------------------
# Extraction
# -----------------------------------------------------------

def extract(self, output_dir="."):

    with open(self.audio_path, "rb") as f:
        data = f.read()

    frames = self._find_frame_offsets(data)

    if not frames:
        raise ValueError("No valid MP3 frames found.")

    recovered_bits = self._read_all_bits(data, frames)

    # filename length
    filename_len = self._bits_to_int(recovered_bits[:16])

    name_start = 16
    name_end = name_start + (filename_len * 8)

    filename_bits = recovered_bits[name_start:name_end]
    filename = self._bits_to_bytes(filename_bits).decode("utf-8")

    # file size area
    size_end = name_end + 64
    file_size = self._bits_to_int(recovered_bits[name_end:size_end])

    # actual payload
    payload_end = size_end + (file_size * 8)

    payload_bits = recovered_bits[size_end:payload_end]
    recovered_data = self._bits_to_bytes(payload_bits)

    final_path = os.path.join(output_dir, filename)

    with open(final_path, "wb") as out:
        out.write(recovered_data)

    print(f"[+] Extracted '{filename}' -> '{final_path}'")

# -----------------------------------------------------------
# MP3 parsing helpers
# -----------------------------------------------------------

@staticmethod
def _skip_id3v2(data):

    # Skip ID3v2 header if it exists.
    # Parsing broke badly without.

    if len(data) < 10:
        return 0

    if data[0:3] != b"ID3":
        return 0

    size = (
        ((data[6] & 0x7F) << 21)
        | ((data[7] & 0x7F) << 14)
        | ((data[8] & 0x7F) << 7)
        | (data[9] & 0x7F)
    )

    return 10 + size

def _find_frame_offsets(self, data):

    offsets = []

    start = self._skip_id3v2(data)
    data_len = len(data)

    i = start

    while i < data_len - 4:

        # sync bits
        if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
            i += 1
            continue

        try:
            frame_size = self._frame_size(data, i)
        except ValueError:
            i += 1
            continue

        # potentially not a valid frame
        if frame_size <= 4:
            i += 1
            continue

        if i + frame_size > data_len:
            break

        offsets.append(i)

        # jump to next frame
        i += frame_size

    return offsets

def _frame_size(self, data, offset):

    b1 = data[offset + 1]
    b2 = data[offset + 2]

    version = (b1 >> 3) & 0b11
    layer = (b1 >> 1) & 0b11

    bitrate_index = (b2 >> 4) & 0b1111
    sample_index = (b2 >> 2) & 0b11

    padding = (b2 >> 1) & 1

    if version == 1 or layer == 0:
        raise ValueError("Reserved MPEG values")

    if bitrate_index in (0, 15):
        raise ValueError("Bad bitrate")

    if sample_index == 3:
        raise ValueError("Bad samplerate")

    bitrate = self._BITRATES[(version, layer)][bitrate_index]
    sample_rate = self._SAMPLE_RATES[version][sample_index]

    # sanity check
    if bitrate <= 0 or sample_rate <= 0:
        raise ValueError("Invalid bitrate/sample rate combo")

    # Layer I math is slightly different
    if layer == 3:
        frame_len = (12 * bitrate * 1000 // sample_rate + padding) * 4
        return frame_len

    samples = self._SAMPLES_PER_FRAME[(version, layer)]

    calc = (samples // 8) * bitrate * 1000
    frame_len = calc // sample_rate + padding

    return frame_len

# -----------------------------------------------------------
# Bit embedding
# -----------------------------------------------------------

def _embed_bits(self, data, frame_offsets, bits):

    for idx in range(len(bits)):

        bit = bits[idx]

        frame_index = idx // self.BITS_PER_FRAME
        slot = idx % self.BITS_PER_FRAME

        self._set_slot_bit(
            data,
            frame_offsets[frame_index],
            slot,
            bit
        )

def _read_all_bits(self, data, frame_offsets):

    collected = []

    for frame_offset in frame_offsets:

        for slot in range(self.BITS_PER_FRAME):

            value = self._get_slot_bit(
                data,
                frame_offset,
                slot
            )

            collected.append(value)

    return collected

# slot 0 -> private bit
# slot 1 -> copyright
# slot 2 -> original

@staticmethod
def _set_slot_bit(data, offset, slot, bit):

    bit = bit & 1

    if slot == 0:

        # private bit
        data[offset + 2] = (data[offset + 2] & 0xFE) | bit

    elif slot == 1:

        data[offset + 3] = (
            (data[offset + 3] & ~0x08)
            | (bit << 3)
        )

    else:

        data[offset + 3] = (
            (data[offset + 3] & ~0x04)
            | (bit << 2)
        )

@staticmethod
def _get_slot_bit(data, offset, slot):

    if slot == 0:
        return data[offset + 2] & 1

    if slot == 1:
        return (data[offset + 3] >> 3) & 1

    return (data[offset + 3] >> 2) & 1

# -----------------------------------------------------------
# Payload helpers
# -----------------------------------------------------------

@staticmethod
def _build_payload(secret_path):

    with open(secret_path, "rb") as f:
        file_data = f.read()

    filename = os.path.basename(secret_path).encode("utf-8")

    filename_len = len(filename).to_bytes(2, "big")

    # 8 bytes might be excessive
    file_size = len(file_data).to_bytes(8, "big")

    payload = (
        filename_len
        + filename
        + file_size
        + file_data
    )

    return payload

@staticmethod
def _bytes_to_bits(data):

    out = []

    for byte in data:

        # manual bit extraction feels clearer
        for i in range(7, -1, -1):

            val = (byte >> i) & 1
            out.append(val)

    return out

@staticmethod
def _bits_to_bytes(bits):

    result = bytearray()

    usable_length = len(bits) - (len(bits) % 8)

    for i in range(0, usable_length, 8):

        value = 0

        for j in range(8):
            value = (value << 1) | bits[i + j]

        result.append(value)

    return bytes(result)

@staticmethod
def _bits_to_int(bits):

    value = 0

    for bit in bits:
        value = (value << 1) | bit

    return value

@staticmethod
def _print_capacity_info(bits_used, total_bits, frames):

    percent = (bits_used / total_bits) * 100

    print(
        f"[*] Used {bits_used}/{total_bits} bits "
        f"({percent:.2f}%) across {frames} frames"
    )
