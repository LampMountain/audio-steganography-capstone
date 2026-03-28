import os
import shutil
from mutagen.id3 import ID3, TXXX, ID3NoHeaderError


class LossySteganography:
    """
    Handles steganography for lossy audio formats (MP3).

    NOTE: A more signal level approach (embedding in MP3 frame headers or
    Huffman tables) can be added later for steganalysis resistance.
    """

    SUPPORTED_EXTENSIONS = {".mp3"}

    # ID3 TXXX description field used to identify hidden payload.
    # Obscure enough to not collide with normal tags.
    _TAG_DESCRIPTION = "x_stego_payload"

    def __init__(self, audio_path: str):
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        self.audio_path = audio_path

    #Embed secret file into the MP3's ID3 tags.
    def hide(self, secret_path: str, output_path: str):
        with open(secret_path, "rb") as f:
            file_data = f.read()

        filename = os.path.basename(secret_path)
        payload = self._build_payload(filename, file_data)

        #Copy the original MP3 to the output path first, then tag it.
        shutil.copy2(self.audio_path, output_path)

        try:
            tags = ID3(output_path)
        except ID3NoHeaderError:
            tags = ID3()

        tags.add(TXXX(encoding=3, desc=self._TAG_DESCRIPTION, text=payload))
        tags.save(output_path)

        print(f"-- '{secret_path}' successfully hidden in '{output_path}'")
        print(f"    Payload size: {len(file_data)} bytes")

    # Extract secret file from the MP3's ID3 tags.
    def extract(self, output_dir: str = "."):
        try:
            tags = ID3(self.audio_path)
        except ID3NoHeaderError:
            raise ValueError(f"No ID3 tags found in '{self.audio_path}'.")

        tag_key = f"TXXX:{self._TAG_DESCRIPTION}"
        if tag_key not in tags:
            raise ValueError(f"No hidden data found in '{self.audio_path}'.")

        payload = tags[tag_key].text[0]
        filename, file_data = self._parse_payload(payload)

        output_path = os.path.join(output_dir, filename)
        with open(output_path, "wb") as f:
            f.write(file_data)

        print(f"-- Extracted '{filename}' ({len(file_data)} bytes) -> '{output_path}'")

    ########################## Payload helpers ##########################

    @staticmethod
    def _build_payload(filename: str, file_data: bytes) -> str:
        # Format: "<filename>\n<hex-encoded file data>"
        # Hex encoding keeps the payload safely inside a text ID3 field.
        hex_data = file_data.hex()
        return f"{filename}\n{hex_data}"

    @staticmethod
    def _parse_payload(payload: str) -> tuple[str, bytes]:
        filename, hex_data = payload.split("\n", 1)
        file_data = bytes.fromhex(hex_data)
        return filename, file_data