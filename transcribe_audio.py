import os
import argparse
from typing import Any # Import Any for type hinting
from deepgram import DeepgramClient, PrerecordedOptions, DeepgramError
# from deepgram.clients.prerecorded.v1.response import PrerecordedTranscriptionResponse # Removed problematic import
import httpx # For potential network errors, as Deepgram SDK uses httpx

DUMMY_AUDIO_DEFAULT_FILENAME = "dummy_audio.wav"

def transcribe_audio_local(api_key: str, audio_file_path: str) -> Any | None: # Changed type hint to Any
    print(f"\nAttempting to transcribe audio file: {audio_file_path}")
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
        options = PrerecordedOptions(smart_format=True, utterances=True, language="en")
        
        print(f"Sending audio data from '{audio_file_path}' to Deepgram for transcription...")
        # Updated to use listen.rest as per deprecation warning
        response = deepgram.listen.rest.v("1").transcribe_file(payload, options, timeout=300)
        print(f"Transcription API call successful for '{audio_file_path}'.")
        return response # This will be 'Any' type
    except DeepgramError as dg_error:
        print(f"Deepgram API Error for '{audio_file_path}': {dg_error}")
        if "auth" in str(dg_error).lower():
            print("Please check your Deepgram API key and permissions.")
        elif "billing" in str(dg_error).lower() or "credits" in str(dg_error).lower():
            print("There might be an issue with your Deepgram account billing or credits.")
        return None
    except httpx.RequestError as http_err:
        print(f"Network Error during transcription for '{audio_file_path}': {http_err}")
        print("Please check your internet connection and Deepgram API status.")
        return None
    except FileNotFoundError:
        print(f"Error: Audio file disappeared or became inaccessible at '{audio_file_path}' during processing.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during transcription of '{audio_file_path}': {e}")
        return None

def save_caption_file(
    transcription_response: Any, # Changed type hint to Any
    input_audio_path: str, 
    output_format: str,
    output_file_path: str | None = None
) -> bool:
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
                print(f"Error: Permission denied to create directory '{output_dir}' for file '{output_filename_final}'.")
                return False
            except Exception as e_mkdir:
                print(f"Error creating directory '{output_dir}' for file '{output_filename_final}': {e_mkdir}")
                return False
    else:
        base, _ = os.path.splitext(input_audio_path)
        output_filename_final = f"{base}.{output_format.lower()}"
    
    caption_content = ""
    print(f"Preparing to save caption file in {output_format.upper()} format to: {output_filename_final}")

    try:
        if output_format.lower() == "srt":
            caption_content = transcription_response.to_srt()
        elif output_format.lower() == "webvtt":
            caption_content = transcription_response.to_vtt()
        else:
            print(f"Error: Invalid output format '{output_format}' specified for saving. Choose 'srt' or 'webvtt'.")
            return False

        print(f"Writing caption content to {output_filename_final}...")
        with open(output_filename_final, "w", encoding="utf-8") as f:
            f.write(caption_content)
        print(f"Caption file successfully saved to: {output_filename_final}")
        return True
    except AttributeError as ae:
        print(f"Error generating caption content for '{input_audio_path}': The transcription response object may be malformed or not the expected PrerecordedTranscriptionResponse. Detail: {ae}")
        return False
    except (IOError, OSError, PermissionError) as file_io_error:
        print(f"Error writing caption file to '{output_filename_final}': {file_io_error}")
        print("Please check file permissions and available disk space.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while saving the caption file for '{input_audio_path}' to '{output_filename_final}': {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe local audio files using Deepgram API and save captions.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "audio_file",
        nargs='+', # Accept one or more audio files
        help="Path(s) to the local audio file(s) to transcribe (e.g., audio1.wav audio2.mp3)."
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
        help="Optional path to save the output caption file.\nIf processing multiple input files, this argument is ignored\nand outputs are saved next to their respective input files.\nIf processing a single file, this path is used directly."
    )
    parser.add_argument(
        "--api_key", "-k",
        default=os.environ.get("DEEPGRAM_API_KEY", "11744f05947dfaa404d823bfb6fec6f29284704b"),
        help="Deepgram API Key.\nDefaults to DEEPGRAM_API_KEY environment variable if set, \notherwise uses a placeholder key."
    )

    args = parser.parse_args()
    
    print(f"--- Starting Transcription Process for {len(args.audio_file)} file(s) ---")
    if args.api_key == "11744f05947dfaa404d823bfb6fec6f29284704b":
        print("INFO: Using default/placeholder API Key. For real use, provide your own via --api_key or DEEPGRAM_API_KEY env var.")

    files_processed_successfully = 0
    files_failed = 0

    # output_path_for_saving = args.output # This was for the initial warning logic, not directly used for saving
    if len(args.audio_file) > 1 and args.output is not None:
        print("Warning: The --output argument is ignored when processing multiple input files. Output files will be saved in the same directories as their respective input files (e.g. input.srt).")

    for i, input_path in enumerate(args.audio_file):
        print(f"\n--- Processing file {i+1} of {len(args.audio_file)}: {input_path} ---")
        
        current_file_output_path = None
        if len(args.audio_file) == 1: # Only use args.output if single file
            current_file_output_path = args.output
        # Else, for multiple files, current_file_output_path remains None, so save_caption_file saves next to input

        try:
            # Conditional dummy file creation
            if input_path == DUMMY_AUDIO_DEFAULT_FILENAME and not os.path.exists(input_path):
                print(f"Notice: Input file '{input_path}' not found. Creating a dummy WAV file for demonstration...")
                try:
                    import wave; import array
                    nc=1; sw=2; fr=16000; nf=fr*2; d=array.array('h',[0]*nf)
                    with wave.open(input_path,'wb') as wf: wf.setnchannels(nc);wf.setsampwidth(sw);wf.setframerate(fr);wf.writeframes(d.tobytes())
                    print(f"Successfully created dummy audio file: {input_path}")
                except ImportError:
                    print(f"Error: Could not import 'wave' module. Cannot create dummy file '{input_path}'. Skipping this file.")
                    files_failed += 1
                    continue # Skip to next file
                except Exception as e_wave:
                    print(f"Error creating dummy audio file '{input_path}': {e_wave}. Skipping this file.")
                    files_failed += 1
                    continue # Skip to next file
            
            transcription_response_obj = transcribe_audio_local(args.api_key, input_path)

            if transcription_response_obj:
                print(f"Transcription completed for '{input_path}'. Proceeding to save caption file.")
                
                saved_successfully = save_caption_file(
                    transcription_response_obj, 
                    input_path, 
                    args.format, # Already lowercased
                    current_file_output_path 
                )
                if saved_successfully:
                    files_processed_successfully += 1
                else:
                    print(f"Caption file saving failed for '{input_path}'.")
                    files_failed += 1
            else:
                print(f"Transcription failed for '{input_path}'. Cannot save captions.")
                files_failed += 1
        
        except Exception as e_file_processing: # Catch unexpected errors during single file processing
            print(f"An unexpected error occurred while processing file '{input_path}': {e_file_processing}")
            files_failed += 1
            # Continue to the next file

    print(f"\n--- Batch Process Summary ---")
    print(f"Total files attempted: {len(args.audio_file)}")
    print(f"Successfully processed: {files_processed_successfully}")
    print(f"Failed to process: {files_failed}")
    
    if files_failed > 0:
        print("--- Process Completed with Errors ---")
        exit(1)
    elif files_processed_successfully == 0 and len(args.audio_file) > 0 :
        print("--- No files were successfully processed ---")
        exit(1)
    else:
        print("--- Process Completed Successfully ---")
