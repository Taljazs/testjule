import os
import argparse
from deepgram import DeepgramClient, PrerecordedOptions, DeepgramError # Added DeepgramError
from deepgram.clients.prerecorded.v1.response import PrerecordedTranscriptionResponse
import httpx # For potential network errors, as Deepgram SDK uses httpx

# Default dummy audio filename, used if specified as the input audio_file argument
DUMMY_AUDIO_DEFAULT_FILENAME = "dummy_audio.wav"

def transcribe_audio_local(api_key: str, audio_file_path: str) -> PrerecordedTranscriptionResponse | None:
    """
    Transcribes an audio file using the Deepgram API.

    Args:
        api_key: Your Deepgram API key.
        audio_file_path: Path to the local audio file.

    Returns:
        A PrerecordedTranscriptionResponse object, or None if an error occurred.
    """
    print(f"Attempting to transcribe audio file: {audio_file_path}")
    if not os.path.exists(audio_file_path):
        print(f"Error: Audio file not found at '{audio_file_path}'. Please check the path.")
        return None
    
    if not os.path.isfile(audio_file_path):
        print(f"Error: The path '{audio_file_path}' is not a file.")
        return None

    try:
        deepgram = DeepgramClient(api_key)

        print(f"Opening and reading audio file: {audio_file_path}...")
        with open(audio_file_path, "rb") as audio_file:
            payload_data = audio_file.read()
        
        payload = {'buffer': payload_data}

        options = PrerecordedOptions(
            smart_format=True,
            utterances=True,
            language="en",
        )
        
        print("Sending audio data to Deepgram for transcription...")
        response = deepgram.listen.prerecorded.v("1").transcribe_file(
            payload,
            options,
            timeout=300 
        )
        print("Transcription API call successful.")
        return response

    except DeepgramError as dg_error:
        print(f"Deepgram API Error for '{audio_file_path}': {dg_error}")
        if "auth" in str(dg_error).lower():
            print("Please check your Deepgram API key and permissions.")
        elif "billing" in str(dg_error).lower() or "credits" in str(dg_error).lower():
            print("There might be an issue with your Deepgram account billing or credits.")
        return None
    except httpx.RequestError as http_err: # Catching network-related errors from httpx
        print(f"Network Error during transcription for '{audio_file_path}': {http_err}")
        print("Please check your internet connection and Deepgram API status.")
        return None
    except FileNotFoundError: # Should be caught by os.path.exists, but as a safeguard
        print(f"Error: Audio file disappeared or became inaccessible at '{audio_file_path}' during processing.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during transcription of '{audio_file_path}': {e}")
        return None

def save_caption_file(
    transcription_response: PrerecordedTranscriptionResponse, 
    input_audio_path: str, 
    output_format: str,
    output_file_path: str | None = None
) -> bool:
    """
    Saves the transcription result to an SRT or WebVTT file.
    (Error handling and feedback improvements made)
    """
    output_filename_final: str
    if output_file_path:
        output_filename_final = output_file_path
        output_dir = os.path.dirname(output_filename_final)
        if output_dir and not os.path.exists(output_dir):
            print(f"Output directory '{output_dir}' does not exist. Attempting to create it...")
            try:
                os.makedirs(output_dir, exist_ok=True)
                print(f"Successfully created directory: {output_dir}")
            except PermissionError:
                print(f"Error: Permission denied to create directory '{output_dir}'.")
                return False
            except Exception as e_mkdir:
                print(f"Error creating directory '{output_dir}': {e_mkdir}")
                return False
    else:
        base, orig_ext = os.path.splitext(input_audio_path)
        output_filename_final = f"{base}.{output_format.lower()}"
    
    caption_content = ""
    print(f"Preparing to save caption file in {output_format.upper()} format to: {output_filename_final}")

    try:
        if output_format.lower() == "srt":
            caption_content = transcription_response.to_srt()
        elif output_format.lower() == "webvtt":
            caption_content = transcription_response.to_vtt()
        else:
            # This should be caught by argparse, but defensive check.
            print(f"Error: Invalid output format '{output_format}' specified for saving. Choose 'srt' or 'webvtt'.")
            return False

        print(f"Writing caption content to {output_filename_final}...")
        with open(output_filename_final, "w", encoding="utf-8") as f:
            f.write(caption_content)
        
        print(f"Caption file successfully saved to: {output_filename_final}")
        return True

    except AttributeError as ae: # If .to_srt() or .to_vtt() is missing from response
        print(f"Error generating caption content: The transcription response object may be malformed or missing necessary data/methods. Detail: {ae}")
        return False
    except (IOError, OSError, PermissionError) as file_io_error: # More specific file operation errors
        print(f"Error writing caption file to '{output_filename_final}': {file_io_error}")
        print("Please check file permissions and available disk space.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while saving the caption file to '{output_filename_final}': {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe local audio files using Deepgram API and save captions.",
        formatter_class=argparse.RawTextHelpFormatter # For better help text formatting
    )
    parser.add_argument(
        "audio_file", 
        help="Path to the local audio file to transcribe (e.g., audio.wav)."
    )
    parser.add_argument(
        "--format", "-f",
        choices=["srt", "webvtt"],
        default="srt",
        type=str.lower,
        help="Desired output caption format (srt or webvtt).\nDefault: srt."
    )
    parser.add_argument(
        "--output", "-o",
        help="Optional path to save the output caption file.\nIf not provided, it's saved next to the input audio file\n(e.g., input_audio.srt)."
    )
    parser.add_argument(
        "--api_key", "-k",
        default=os.environ.get("DEEPGRAM_API_KEY", "11744f05947dfaa404d823bfb6fec6f29284704b"), # Try env var first
        help="Deepgram API Key.\nDefaults to DEEPGRAM_API_KEY environment variable if set, \notherwise uses a placeholder key."
    )

    try:
        args = parser.parse_args()

        print(f"--- Starting Transcription Process ---")
        print(f"Input audio file: {args.audio_file}")
        print(f"Requested caption format: {args.format.upper()}")
        if args.output:
            print(f"Specified output file path: {args.output}")
        if args.api_key == "11744f05947dfaa404d823bfb6fec6f29284704b":
             print("Using default/placeholder API Key. For real use, provide your own via --api_key or DEEPGRAM_API_KEY env var.")


        # Conditional dummy file creation
        if args.audio_file == DUMMY_AUDIO_DEFAULT_FILENAME and not os.path.exists(args.audio_file):
            print(f"Notice: Input file '{args.audio_file}' not found. Creating a dummy WAV file for demonstration...")
            try:
                import wave
                import array
                nchannels = 1; sampwidth = 2; framerate = 16000; nframes = framerate * 2
                data = array.array('h', [0] * nframes)
                with wave.open(args.audio_file, 'wb') as wf:
                    wf.setnchannels(nchannels); wf.setsampwidth(sampwidth)
                    wf.setframerate(framerate); wf.writeframes(data.tobytes())
                print(f"Successfully created dummy audio file: {args.audio_file}")
            except ImportError:
                print("Error: Could not import 'wave' module. Cannot create dummy file. Please provide an existing audio file.")
                exit(1)
            except Exception as e_wave:
                print(f"Error creating dummy audio file '{args.audio_file}': {e_wave}")
                exit(1)
        
        transcription_response_obj = transcribe_audio_local(args.api_key, args.audio_file)

        if transcription_response_obj:
            print("Transcription completed. Proceeding to save caption file.")
            
            saved_successfully = save_caption_file(
                transcription_response_obj, 
                args.audio_file, 
                args.format,
                args.output 
            )
            if saved_successfully:
                print("--- Process Completed Successfully ---")
            else:
                print("Caption file saving failed. Please check previous error messages.")
                print("--- Process Completed with Errors ---")
                exit(1) # Exit with error status
        else:
            print("Transcription failed or returned no result. Cannot proceed to save captions.")
            print("--- Process Terminated Due to Transcription Error ---")
            exit(1) # Exit with error status

    except FileNotFoundError as e_fnf: # Catching if argparse input file doesn't exist (less likely with argparse)
        print(f"Error: The specified audio file '{e_fnf.filename}' was not found.")
        parser.print_help()
        exit(1)
    except Exception as e_main:
        print(f"An unexpected critical error occurred in the main execution block: {e_main}")
        print("If this issue persists, please report it with the steps to reproduce.")
        print("--- Process Terminated Due to Unexpected Error ---")
        exit(1)
```
