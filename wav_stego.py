import wave
import struct
import os


class WavSteganography:
    #Handles LSB (Least-Significant Bit)steganography for uncompressed WAV audio files.

    SUPPORTED_EXTENSIONS = {".wav"}
    SAMPLE_WIDTH_BITS = 16  # Only 16-bit WAV supported
                            # Other Formats (like 24-bit) would require more complex handling and are not supported in this implementation.
                            # Potential future enhancement: Add support for more formats and bit depths.

    def __init__(self, audio_path: str):
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        self.audio_path = audio_path
        self._validate_audio()

    # Return error for non 16-Bit WAV files.
    def _validate_audio(self):
        with wave.open(self.audio_path, "rb") as wav:
            if wav.getsampwidth() * 8 != self.SAMPLE_WIDTH_BITS:
                raise ValueError(
                    f"Only {self.SAMPLE_WIDTH_BITS}-bit WAV files are supported. "
                    f"This file is {wav.getsampwidth() * 8}-bit."
                )


    #LSB Encoding
    def hide(self, secret_path: str, output_path: str):
        
        payload = self._build_payload(secret_path)
        payload_bits = self._bytes_to_bits(payload)
        samples, params = self._read_samples()

        if len(payload_bits) > len(samples): # File too large to hide in the audio.
            raise ValueError(
                f"Secret file is too large to hide. "
                f"Need {len(payload_bits)} sample slots, audio only has {len(samples)}."
            )

        modified_samples = self._embed_bits(samples, payload_bits)
        self._write_wav(output_path, modified_samples, params)

        print(f"-- '{secret_path}' successfully hidden in '{output_path}'")
        self._print_capacity_info(len(payload_bits), len(samples))

    #LSB Decoding
    def extract(self, output_dir: str = "."):
        samples, _ = self._read_samples()

        filename_len = self._read_int_from_lsbs(samples, start_bit=0, num_bytes=2)
        filename = self._read_bytes_from_lsbs(
            samples, start_bit=16, num_bytes=filename_len
        ).decode("utf-8")

        #16-bit based decoding
        size_start_bit = 16 + filename_len * 8
        file_size = self._read_int_from_lsbs(
            samples, start_bit=size_start_bit, num_bytes=8
        )

        data_start_bit = size_start_bit + 64
        secret_data = self._read_bytes_from_lsbs(
            samples, start_bit=data_start_bit, num_bytes=file_size
        )

        output_path = os.path.join(output_dir, filename)
        with open(output_path, "wb") as f:
            f.write(secret_data)

        print(f"-- Extracted '{filename}' ({file_size} bytes) -> '{output_path}'")

    ############################ Payload construction ############################

    def _build_payload(self, secret_path: str) -> bytes:
        """
        Build the full payload to embed.
        Format: [2B filename_len][filename][8B file_size][file_data]
        """
        with open(secret_path, "rb") as f:
            file_data = f.read()

        filename = os.path.basename(secret_path).encode("utf-8")
        filename_len = len(filename).to_bytes(2, "big")
        file_size = len(file_data).to_bytes(8, "big")

        return filename_len + filename + file_size + file_data

    ############################ Bit-level helpers ############################ 

    @staticmethod
    def _bytes_to_bits(data: bytes) -> list[int]:
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return bits

    @staticmethod
    def _embed_bits(samples: list[int], bits: list[int]) -> list[int]:
        modified = samples[:]
        for i, bit in enumerate(bits):
            modified[i] = (modified[i] & ~1) | bit
        return modified

    @staticmethod
    def _read_bytes_from_lsbs(
        samples: tuple[int, ...], start_bit: int, num_bytes: int
    ) -> bytes:
        result = []
        for i in range(num_bytes):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | (samples[start_bit + i * 8 + j] & 1)
            result.append(byte)
        return bytes(result)

    @classmethod
    def _read_int_from_lsbs(
        cls, samples: tuple[int, ...], start_bit: int, num_bytes: int
    ) -> int:
        return int.from_bytes(
            cls._read_bytes_from_lsbs(samples, start_bit, num_bytes), "big"
        )

    ############################ WAV I/O ############################

    def _read_samples(self) -> tuple[list[int], wave._wave_params]:
        with wave.open(self.audio_path, "rb") as wav:
            params = wav.getparams()
            n_channels = params.nchannels
            n_frames = wav.getnframes()
            raw_frames = wav.readframes(n_frames)

        total_samples = n_frames * n_channels
        samples = list(struct.unpack(f"<{total_samples}h", raw_frames))
        return samples, params

    @staticmethod
    def _write_wav(output_path: str, samples: list[int], params: wave._wave_params):
        raw_frames = struct.pack(f"<{len(samples)}h", *samples)
        with wave.open(output_path, "wb") as out_wav:
            out_wav.setparams(params)
            out_wav.writeframes(raw_frames)

    @staticmethod
    def _print_capacity_info(bits_used: int, total_samples: int):
        print(
            f"    Samples used: {bits_used} / {total_samples} "
            f"({100 * bits_used / total_samples:.2f}%)"
        )