import os
import numpy as np
import soundfile as sf


class CompressedSteganography:
    """
    Handles steganography for lossless compressed audio (OGG, FLAC).
    NOTE: Add support for lossy formats (like MP3) would require a completely different approach and is not covered in this implementation.
        Potential future enhancement: Add support for lossy formats using techniques like echo hiding or phase coding
        Echo could be potentially used but the values need to be recorded carefully to prevent accidental deletion during MP3 compression.
        This was an issue in the initial implementation which is why mp3 cannot be handled fully
    """

    SUPPORTED_EXTENSIONS = {".ogg", ".flac"}

    # Scale factor for converting float samples to integers for LSB manipulation.
    # 16-bit range: -32768 to 32767
    INT_SCALE = 32767

    def __init__(self, audio_path: str):
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        self.audio_path = audio_path
        self.extension = os.path.splitext(audio_path)[1].lower()

    #LSB Encoding
    def hide(self, secret_path: str, output_path: str):
        payload = self._build_payload(secret_path)
        payload_bits = self._bytes_to_bits(payload)

        samples, sample_rate = self._load_audio()
        flat_samples = samples.flatten()
        int_samples = self._to_int_array(flat_samples)

        if len(payload_bits) > len(int_samples):
            raise ValueError(
                f"Secret file is too large. "
                f"Need {len(payload_bits)} samples, audio only has {len(int_samples)}."
            )

        stego_int = self._embed_bits(int_samples, payload_bits)
        stego_float = self._to_float_array(stego_int)
        stego_samples = stego_float.reshape(samples.shape)
        self._save_audio(stego_samples, sample_rate, output_path)

        print(f"-- '{secret_path}' successfully hidden in '{output_path}'")
        self._print_capacity_info(len(payload_bits), len(int_samples))

    #LSB Decoding
    def extract(self, output_dir: str = "."):
        samples, _ = self._load_audio()
        flat_samples = samples.flatten()
        int_samples = self._to_int_array(flat_samples)

        filename_len = self._read_int_from_lsbs(int_samples, start_bit=0, num_bytes=2)
        filename = self._read_bytes_from_lsbs(
            int_samples, start_bit=16, num_bytes=filename_len
        ).decode("utf-8")

        size_start_bit = 16 + filename_len * 8
        file_size = self._read_int_from_lsbs(
            int_samples, start_bit=size_start_bit, num_bytes=8
        )

        data_start_bit = size_start_bit + 64
        secret_data = self._read_bytes_from_lsbs(
            int_samples, start_bit=data_start_bit, num_bytes=file_size
        )

        output_path = os.path.join(output_dir, filename)
        with open(output_path, "wb") as f:
            f.write(secret_data)

        print(f"-- Extracted '{filename}' ({file_size} bytes) -> '{output_path}'")


    ########################## Payload construction ############################

    def _build_payload(self, secret_path: str) -> bytes:
        with open(secret_path, "rb") as f:
            file_data = f.read()

        filename = os.path.basename(secret_path).encode("utf-8")
        filename_len = len(filename).to_bytes(2, "big")
        file_size = len(file_data).to_bytes(8, "big")

        return filename_len + filename + file_size + file_data

    ######################### LSB core ############################

    #Hiding bits in audio file
    @staticmethod
    def _embed_bits(samples: np.ndarray, bits: list[int]) -> np.ndarray:
        modified = samples.copy()
        for i, bit in enumerate(bits):
            modified[i] = (int(modified[i]) & ~1) | bit
        return modified

    
    @staticmethod
    def _read_bytes_from_lsbs(
        samples: np.ndarray, start_bit: int, num_bytes: int
    ) -> bytes:
        result = []
        for i in range(num_bytes):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | (int(samples[start_bit + i * 8 + j]) & 1)
            result.append(byte)
        return bytes(result)

    @classmethod
    def _read_int_from_lsbs(
        cls, samples: np.ndarray, start_bit: int, num_bytes: int
    ) -> int:
        return int.from_bytes(
            cls._read_bytes_from_lsbs(samples, start_bit, num_bytes), "big"
        )


    ########################## Audio I/O helpers ############################ 

    def _load_audio(self) -> tuple[np.ndarray, int]: 
        samples, sample_rate = sf.read(self.audio_path, dtype="float32")
        return samples, sample_rate

    def _save_audio(self, samples: np.ndarray, sample_rate: int, output_path: str):
        fmt = self.extension.lstrip(".")
        sf.write(output_path, samples, sample_rate, format=fmt)

    def _to_int_array(self, samples: np.ndarray) -> np.ndarray:
        return (samples * self.INT_SCALE).astype(np.int32)

    def _to_float_array(self, samples: np.ndarray) -> np.ndarray:
        return samples.astype(np.float32) / self.INT_SCALE


    ######################### Bit manipulation helpers ############################ 

    @staticmethod
    def _bytes_to_bits(data: bytes) -> list[int]:
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return bits

    @staticmethod
    def _print_capacity_info(bits_used: int, total_samples: int):
        print(
            f"    Samples used: {bits_used} / {total_samples} "
            f"({100 * bits_used / total_samples:.2f}%)"
        )
