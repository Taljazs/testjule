# Deepgram Audio Transcription CLI

A Python command-line tool to transcribe local audio files into SRT (.srt) or WebVTT (.vtt) caption formats using the Deepgram Speech-to-Text API.

## Features

-   Transcribe local audio files.
-   Output in SRT or WebVTT caption formats.
-   Process multiple files in a single run (batch processing).
-   Flexible API key handling (environment variable or command-line argument).
-   Clear command-line interface.
-   Robust error handling, especially for batch operations.
-   Includes a self-generating silent dummy audio file for quick testing.
-   Defaults to using Deepgram's "nova-2" model for transcription.

## Requirements

-   Python 3.7 or higher.
-   `deepgram-sdk` Python package.
-   `httpx` Python package (usually a dependency of `deepgram-sdk`).

## Setup

1.  **Clone the repository or download `transcribe_audio.py`**.

2.  **Install dependencies**:
    Open your terminal and run:
    ```bash
    pip install deepgram-sdk httpx
    ```

3.  **Set your Deepgram API Key**:
    You need a Deepgram API key to use this script. You can provide it in one of two ways:

    *   **Environment Variable (Recommended)**:
        Set the `DEEPGRAM_API_KEY` environment variable to your API key.
        -   On Linux/macOS: `export DEEPGRAM_API_KEY="YOUR_API_KEY"` (add to your shell profile like `.bashrc` or `.zshrc` for persistence).
        -   On Windows (PowerShell): `$env:DEEPGRAM_API_KEY="YOUR_API_KEY"` (use "SetX" command for persistence).
    *   **Command-Line Argument**:
        Use the `--api_key YOUR_API_KEY` argument when running the script. This will override the environment variable if set.
        If no API key is provided via these methods, the script will use a placeholder key which will likely result in authentication errors.

## Usage

Navigate to the directory containing `transcribe_audio.py` in your terminal.

**Basic Command Structure:**

```bash
python transcribe_audio.py [options] <audio_file_path(s)>
```

**Arguments:**

*   `audio_file`: (Required) Path(s) to the local audio file(s) to transcribe. Separate multiple files with spaces.
*   `-f, --format {srt,webvtt}`: (Optional) Desired output caption format. Default is `srt`.
*   `-o, --output <output_path>`: (Optional) Path to save the output caption file.
    *   **Single input file**: If provided, the caption file is saved to this path.
    *   **Multiple input files**: This argument is ignored if provided. Output files will be saved in the same directories as their respective input audio files, with the chosen format extension.
*   `-k, --api_key <your_api_key>`: (Optional) Your Deepgram API Key. Overrides the `DEEPGRAM_API_KEY` environment variable if set.
*   `--paragraphs`: (Optional, flag) Enable paragraph segmentation. Captions will be based on Deepgram's sentence splits within identified paragraphs. When this option is used, `--max_caption_chars` and `--split_on_sentences` are IGNORED. 启用段落分割，字幕将基于段落中的句子进行分割。启用此选项后，`--max_caption_chars` 和 `--split_on_sentences` 将被忽略。
*   `--diarize`: (Optional, flag) Enable speaker diarization. This identifies different speakers. It may also influence how paragraphs are segmented if `--paragraphs` is also enabled. (Note: Diarization output is not directly rendered in the captions by this script, but enabling it can affect other results like paragraphing).
*   `--max_caption_chars <int>`: (Optional, default: 100) Maximum characters per caption segment when processing utterances. This setting is IGNORED if `--paragraphs` is enabled (as paragraph mode uses sentence-based segmentation). 字幕分段最大字符数（处理utterances时生效），默认100。若启用 --paragraphs 则此设置无效。
*   `--split_on_sentences`: (Optional, flag) When processing utterances, attempt to split segments at sentence endings (e.g., '.', '?', '!') if it generally respects `--max_caption_chars`. This setting is IGNORED if `--paragraphs` is enabled. 处理utterances时，尝试在句尾分割字幕。若启用 --paragraphs 则此设置无效。

**Examples:**

1.  **Transcribe a single audio file to SRT (default format):**
    ```bash
    python transcribe_audio.py my_audio.wav
    ```
    *(Output: `my_audio.srt` in the same directory)*

2.  **Transcribe a single audio file to WebVTT:**
    ```bash
    python transcribe_audio.py my_talk.mp3 --format webvtt
    ```
    *(Output: `my_talk.vtt` in the same directory)*

3.  **Transcribe multiple audio files (batch processing) to SRT:**
    ```bash
    python transcribe_audio.py meeting_notes.wav podcast_episode.mp3 interview.m4a
    ```
    *(Outputs: `meeting_notes.srt`, `podcast_episode.srt`, `interview.srt` in their respective original directories)*

4.  **Specify a custom output path for a single file:**
    ```bash
    python transcribe_audio.py my_audio.wav --output /path/to/save/captions/final_captions.srt
    ```

5.  **Using the built-in dummy audio file for testing:**
    If you provide `dummy_audio.wav` as an input file and it doesn't exist, the script will generate a short, silent WAV file named `dummy_audio.wav` in the current directory and then transcribe it.
    ```bash
    python transcribe_audio.py dummy_audio.wav --format srt
    ```
    *(Output: `dummy_audio.srt` containing no actual speech captions, as the input is silent)*

6.  **Transcribe with paragraph segmentation and diarization enabled:**
    ```bash
    python transcribe_audio.py my_long_talk.wav --paragraphs --diarize --format srt
    ```

7.  **Transcribe utterances with a max character limit per caption:**
    ```bash
    python transcribe_audio.py my_talk.wav --max_caption_chars 80 --format srt
    ```

## Error Handling

-   The script provides feedback on the success or failure of each operation.
-   In batch mode, if an error occurs while processing one file (e.g., file not found, API error), the script will report the error for that file and continue to process the remaining files.
-   A summary of successfully processed and failed files is provided at the end of a batch run.
-   The script will exit with a status code `1` if any files failed to process or if critical errors occurred, and `0` if all operations were successful.

```
