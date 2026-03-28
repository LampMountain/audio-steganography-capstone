import sys
import os
from wav_stego import WavSteganography
from compressed_stego import CompressedSteganography
from lossy_stego import LossySteganography

#Used to route to the correct handler based on file extension. This keeps the main logic clean and allows for easy extension in the future if new formats are added.
WAV_EXTENSIONS = WavSteganography.SUPPORTED_EXTENSIONS
COMPRESSED_EXTENSIONS = CompressedSteganography.SUPPORTED_EXTENSIONS
LOSSY_EXTENSIONS = LossySteganography.SUPPORTED_EXTENSIONS
ALL_SUPPORTED = WAV_EXTENSIONS | COMPRESSED_EXTENSIONS | LOSSY_EXTENSIONS

#Returns the appropriate handler class instance based on the audio file extension.
def get_handler(audio_path: str):
    ext = os.path.splitext(audio_path)[1].lower()
    if ext in WAV_EXTENSIONS:
        return WavSteganography(audio_path)
    if ext in COMPRESSED_EXTENSIONS:
        return CompressedSteganography(audio_path)
    if ext in LOSSY_EXTENSIONS:
        return LossySteganography(audio_path)
    raise ValueError(
        f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(ALL_SUPPORTED))}"
    )


def print_usage():
    print("Instructions:")
    print("  Hide:    python main.py hide <audio_file> <secret_file> <output_file>")
    print("  Extract: python main.py extract <stego_audio_file> [output_dir]")
    print()
    print(f"Supported audio types: {', '.join(sorted(ALL_SUPPORTED))}")


def main():
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "hide": #Check Input
        if len(sys.argv) < 5:
            print("Hide requires: <audio_file> <secret_file> <output_file>")
            sys.exit(1)
        audio_path, secret_path, output_path = sys.argv[2], sys.argv[3], sys.argv[4]
        handler = get_handler(audio_path)
        handler.hide(secret_path, output_path)

    elif mode == "extract": #Check Input
        audio_path = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "."
        handler = get_handler(audio_path)
        handler.extract(output_dir)

    else:
        print(f"Unknown mode '{mode}'. Use 'hide' or 'extract'.")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
