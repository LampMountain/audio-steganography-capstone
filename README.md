# audio-steganography-capstone

A Python program that hides files inside audio files using steganography. The current methods used do not affect audio quality but they are easily detectable when examining the file since the least significant bits or echos leave a distinct pattern.

## How It Works
- **WAV files (Uncompressed)** use LSB (Least Significant Bit) substitution on raw data
- **OGG/FLAC files (Compressed-Lossless)** use LSB (Least Significant Bit) substitution with soundfile to read

- **MP3,etc. files (Compressed-Lossy)** use Mutagen currently and will use Huffman coding in future implementation

## Files
- `main.py` — Entry point / driver
- `wav_stego.py` — Handles uncompressed WAV steganography
- `compressed_stego.py` — Handles compressed audio steganography

## Requirements
- Python 3.13+
- numpy
- soundfile

Install dependencies:
    pip install numpy soundfile mutagen

## Usage/Instructions
Hide a file:
    python main.py hide <audio_file> <secret_file> <output_file>

Extract a file:
    python main.py extract <stego_audio_file> [output_dir]

## Supported Formats (.mp3 currently being worked on)
- .wav (uncompressed)
- .ogg (compressed)
- .flac (compressed)
- .mp3  (lossy)

## Additional Notes
- Will print error if secret file is too large to be hid with current implementation.
