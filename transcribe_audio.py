import os
import argparse
from typing import Any, Optional, Dict # Ensured Optional and Dict are imported
from deepgram import DeepgramClient, PrerecordedOptions, DeepgramError
# from deepgram.utils import Srt, WebVTT # Removed old import
# from deepgram.utils.srt import SRT # Removed SRT utility import
# from deepgram.utils.vtt import WebVTT # Removed WebVTT utility import
# from deepgram.clients.prerecorded.v1.response import PrerecordedResponse # Removed problematic import
import httpx # For potential network errors, as Deepgram SDK uses httpx
import math # Added for timestamp formatting

DUMMY_AUDIO_DEFAULT_FILENAME = "dummy_audio.wav"

# Default REQUEST_TIMEOUT_SECONDS for Deepgram API call - can be adjusted
REQUEST_TIMEOUT_SECONDS = 300

def format_timestamp(total_seconds: float, srt_format: bool = True) -> str:
    if total_seconds < 0:
        total_seconds = 0 # Ensure non-negative time

    hours = int(total_seconds / 3600)
    minutes = int((total_seconds % 3600) / 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds - int(total_seconds)) * 1000) # More precise way to get milliseconds

    separator = ',' if srt_format else '.'
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{milliseconds:03d}"

# Helper function to generate a single caption block
def _generate_caption_block(words_in_block: list, sequence_num: int, output_format: str) -> str:
    if not words_in_block:
        return ""

    first_word_obj = words_in_block[0]
    last_word_obj = words_in_block[-1]

    start_time_val = 0.0
    try:
        start_time_val = float(getattr(first_word_obj, 'start', 0.0))
    except (ValueError, TypeError):
        print(f"WARNING (_generate_caption_block): Invalid start time for first word '{getattr(first_word_obj, 'word', 'N/A')}'. Defaulting to 0.0.")

    end_time_val = start_time_val # Default end to start
    try:
        end_time_val = float(getattr(last_word_obj, 'end', start_time_val))
        if end_time_val < start_time_val: # Ensure end is not before start
             print(f"WARNING (_generate_caption_block): End time {end_time_val} is before start time {start_time_val} for block. Adjusting end time.")
             end_time_val = start_time_val
    except (ValueError, TypeError):
        print(f"WARNING (_generate_caption_block): Invalid end time for last word '{getattr(last_word_obj, 'word', 'N/A')}'. Defaulting to start time {start_time_val:.3f}.")

    text_parts = []
    for w_obj in words_in_block:
        p_word = getattr(w_obj, 'punctuated_word', None)
        word_val = getattr(w_obj, 'word', "") # Default to empty string if 'word' is also missing
        text_parts.append(p_word if p_word is not None else word_val)
    text = " ".join(text_parts)

    is_srt = (output_format.lower() == "srt")
    start_ts = format_timestamp(start_time_val, srt_format=is_srt)
    end_ts = format_timestamp(end_time_val, srt_format=is_srt)

    if is_srt:
        return f"{sequence_num}\n{start_ts} --> {end_ts}\n{text}"
    else: # WebVTT
        return f"{start_ts} --> {end_ts}\n{text}"

def transcribe_audio_local(api_key: str, audio_file_path: str, enable_paragraphs: bool, enable_diarization: bool) -> Optional[Any]: # Added paragraph/diarize flags
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
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            utterances=True, # Keep utterances=True for fallback or if paragraphs don't replace it
            language="en",
            paragraphs=enable_paragraphs,
            diarize=enable_diarization
        )

        print(f"Sending audio data from '{audio_file_path}' to Deepgram for transcription with options: paragraphs={enable_paragraphs}, diarize={enable_diarization}...")
        response = deepgram.listen.rest.v("1").transcribe_file(payload, options, timeout=REQUEST_TIMEOUT_SECONDS)
        print(f"Transcription API call successful for '{audio_file_path}'.")
        return response
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
    transcription_response: Any,
    input_audio_path: str,
    output_format: str,
    output_file_path: Optional[str] = None,
    enable_paragraphs_option_used: bool = False,
    cli_args: Optional[argparse.Namespace] = None # Added cli_args for splitting options
) -> bool:
    if cli_args is None: # Should not happen if called from __main__
        class MockArgs:
            max_caption_chars = 100
            split_on_sentences = False
        cli_args = MockArgs()

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
    results_data = None

    # First, try to access a 'results' attribute, which often holds the main transcription data.
    if hasattr(transcription_response, 'results'):
        results_data = transcription_response.results
        # print(f"DEBUG: Successfully accessed transcription_response.results") # Removed
    else:
        if hasattr(transcription_response, 'utterances') and hasattr(transcription_response, 'channels'):
             results_data = transcription_response
             # print(f"DEBUG: Using transcription_response directly as results_data") # Removed
        else:
            print(f"ERROR: Could not find .results on the transcription_response object, nor does it appear to be the results data itself (missing .utterances or .channels). Dir: {dir(transcription_response)}")
            return False

    if results_data is None:
        print(f"ERROR: results_data is None after attempting to access from transcription_response. Cannot generate captions.")
        return False

    # print(f"DEBUG: Type of results_data passed to Srt/WebVTT: {type(results_data)}") # Removed
    # if hasattr(results_data, 'keys') and callable(getattr(results_data, 'keys', None)):
    #     try:
    #         # print(f"DEBUG: Keys of results_data: {results_data.keys()}") # Removed
    #     except Exception as e_keys_results:
    #          # print(f"DEBUG: Could not get keys from results_data (it might not be a dict): {e_keys_results}") # Removed
    # elif isinstance(results_data, list) and results_data:
    #     # print(f"DEBUG: results_data is a list, first element type: {type(results_data[0]) if results_data else 'empty list'}") # Removed
    #     pass # No specific action if it's a list here, utterance access handles it

    utterances = None
    # print(f"DEBUG: Attempting to access utterances from results_data (type: {type(results_data)})...") # Removed

    if hasattr(results_data, 'utterances'):
        candidate_utterances = results_data.utterances
        if isinstance(candidate_utterances, list):
            utterances = candidate_utterances
            # print(f"DEBUG: Accessed utterances via results_data.utterances. Count: {len(utterances)}") # Removed
        else:
            # print(f"DEBUG: results_data.utterances is present but not a list (type: {type(candidate_utterances)}). Value: {candidate_utterances}") # Removed
            if candidate_utterances is not None:
                 print(f"WARNING: results_data.utterances was expected to be a list or None, but got {type(candidate_utterances)}")

    if utterances is None or (isinstance(utterances, list) and not utterances):
        # if utterances is None:
        #      print(f"DEBUG: Primary utterance access (results_data.utterances) yielded None or was not a list. Attempting nested path...") # Removed
        # else:
        #      print(f"DEBUG: Primary utterance access (results_data.utterances) yielded an empty list. Attempting nested path as fallback...") # Removed

        if hasattr(results_data, 'channels') and results_data.channels:
            try:
                if (len(results_data.channels) > 0 and
                        hasattr(results_data.channels[0], 'alternatives') and
                        results_data.channels[0].alternatives and
                        len(results_data.channels[0].alternatives) > 0 and
                        hasattr(results_data.channels[0].alternatives[0], 'utterances')):

                    candidate_nested_utterances = results_data.channels[0].alternatives[0].utterances
                    if isinstance(candidate_nested_utterances, list):
                        if candidate_nested_utterances:
                            utterances = candidate_nested_utterances
                            # print(f"DEBUG: Accessed utterances via results_data.channels[0].alternatives[0].utterances. Count: {len(utterances)}") # Removed
                        elif not utterances:
                            utterances = candidate_nested_utterances
                            # print(f"DEBUG: Nested utterances path (results_data.channels[0].alternatives[0].utterances) yielded an empty list. Using this empty list.") # Removed
                        # else:
                            # print(f"DEBUG: Nested utterances path also yielded an empty list. Sticking with primary empty list.") # Removed
                            pass # No change if primary was empty and nested is also empty
                    else:
                        # print(f"DEBUG: Nested utterances path (results_data.channels[0].alternatives[0].utterances) is present but not a list (type: {type(candidate_nested_utterances)}). Value: {candidate_nested_utterances}") # Removed
                        if candidate_nested_utterances is not None:
                             print(f"WARNING: Nested utterances path was expected to be a list or None, but got {type(candidate_nested_utterances)}")
                # else:
                    # print("DEBUG: Nested utterance path check failed: channels, alternatives, or utterances attribute missing or empty at some level.") # Removed
            except (AttributeError, IndexError, TypeError) as e_nested:
                # print(f"DEBUG: Error while trying to access nested utterances: {e_nested}") # Removed
                pass # Silently ignore if nested path fails, primary result (None or empty list) will be used
        # elif utterances is None:
        #      print(f"DEBUG: No .channels attribute found or channels list empty on results_data. Cannot attempt nested path.") # Removed
        pass


    if utterances is None:
        print("WARNING: No utterances found after checking primary and nested paths. Caption generation will result in empty content.")
        utterances = []
    elif not isinstance(utterances, list):
        print(f"ERROR: 'utterances' was expected to be a list but ended up as {type(utterances)}. Value: {str(utterances)[:200]}. Cannot proceed.")
        return False

    # print(f"DEBUG: Final utterances list for generation - Type: {type(utterances)}, Length: {len(utterances)}") # Removed

    caption_source_is_paragraphs = False
    paragraph_segments = [] # Will hold paragraph objects if used
    original_segments = utterances # Renamed from utterances_for_fallback for clarity

    if enable_paragraphs_option_used:
        print("INFO: --paragraphs option enabled. Attempting to use paragraph segments for captions.")
        try:
            if (hasattr(results_data, 'channels') and results_data.channels and
                len(results_data.channels) > 0 and hasattr(results_data.channels[0], 'alternatives') and
                results_data.channels[0].alternatives and len(results_data.channels[0].alternatives) > 0 and
                hasattr(results_data.channels[0].alternatives[0], 'paragraphs') and
                results_data.channels[0].alternatives[0].paragraphs and
                hasattr(results_data.channels[0].alternatives[0].paragraphs, 'paragraphs')):

                paragraph_segments_candidate = results_data.channels[0].alternatives[0].paragraphs.paragraphs
                if isinstance(paragraph_segments_candidate, list) and paragraph_segments_candidate:
                    paragraph_segments = paragraph_segments_candidate
                    caption_source_is_paragraphs = True
                    print(f"INFO: Using {len(paragraph_segments)} paragraph segments for caption generation.")
                else:
                    print("WARNING: --paragraphs enabled, but no valid paragraph segments found in the expected path. Falling back to utterances.")
                    caption_source_is_paragraphs = False # Explicitly set fallback
            else:
                print("WARNING: --paragraphs enabled, but paragraph data structure not found in response. Falling back to utterances.")
                caption_source_is_paragraphs = False # Explicitly set fallback
        except Exception as e_pg:
            print(f"WARNING: Error accessing paragraph data: {e_pg}. Falling back to utterances.")
            caption_source_is_paragraphs = False # Explicitly set fallback

    # Determine the actual segments to process based on paragraph logic outcome
    segments_to_process = paragraph_segments if caption_source_is_paragraphs else original_segments

    try:
        final_caption_blocks = [] # Unified list for SRT/WebVTT blocks
        srt_sequence_number = 1
        processed_segments_count = 0 # Counts original segments that yield at least one caption block

        if not segments_to_process:
            print(f"WARNING: No segments (paragraphs/utterances) available for {output_format} generation.")
            # caption_content will be empty or just WebVTT header
        else:
            for segment_idx, segment_data in enumerate(segments_to_process):
                segment_processed_successfully = False # Flag for this original segment
                if caption_source_is_paragraphs:
                    # Path A: Process paragraph segments by sentence
                    try:
                        pg_start_time = segment_data['start'] if isinstance(segment_data, dict) else segment_data.start
                        pg_end_time = segment_data['end'] if isinstance(segment_data, dict) else segment_data.end
                        sentences_list = segment_data['sentences'] if isinstance(segment_data, dict) else segment_data.sentences

                        for sentence_data in sentences_list:
                            sentence_text = (sentence_data['text'] if isinstance(sentence_data, dict) else sentence_data.text).strip()
                            if not sentence_text:
                                continue

                            # For paragraphs, use sentence start/end times directly.
                            # If sentence-level timestamps aren't available, use paragraph start/end as a fallback (less ideal).
                            start_seconds = sentence_data.get('start', pg_start_time) if isinstance(sentence_data, dict) else getattr(sentence_data, 'start', pg_start_time)
                            end_seconds = sentence_data.get('end', pg_end_time) if isinstance(sentence_data, dict) else getattr(sentence_data, 'end', pg_end_time)

                            start_ts = format_timestamp(start_seconds, srt_format=(output_format.lower() == "srt"))
                            end_ts = format_timestamp(end_seconds, srt_format=(output_format.lower() == "srt"))

                            if output_format.lower() == "srt":
                                final_caption_blocks.append(f"{srt_sequence_number}\n{start_ts} --> {end_ts}\n{sentence_text}")
                                srt_sequence_number += 1
                            else: # WebVTT
                                final_caption_blocks.append(f"{start_ts} --> {end_ts}\n{sentence_text}")
                            segment_processed_successfully = True
                    except (KeyError, AttributeError, TypeError) as e:
                        print(f"WARNING: Skipping sentence in paragraph segment {segment_idx+1} due to error: {e}. Sentence data: {str(sentence_data)[:200]}...")
                        continue

                else: # Path B: Process utterances with splitting logic
                    try:
                        utterance_transcript_text = (segment_data['transcript'] if isinstance(segment_data, dict) else segment_data.transcript).strip()
                        # Utterances are expected to have 'words' for splitting.
                        # If 'words' are missing, treat the utterance as a single block subject to max_chars (if sentence splitting not forced).
                        words_list = segment_data.get('words', []) if isinstance(segment_data, dict) else getattr(segment_data, 'words', [])

                        if not utterance_transcript_text:
                            print(f"INFO: Utterance {segment_idx+1} has no text content. Skipping.")
                            continue

                        # If no words_list, or if simple processing is chosen:
                        if not words_list or (not cli_args.split_on_sentences and len(utterance_transcript_text) <= cli_args.max_caption_chars):
                            # Use the utterance's own start/end times
                            start_seconds = segment_data['start'] if isinstance(segment_data, dict) else segment_data.start
                            end_seconds = segment_data['end'] if isinstance(segment_data, dict) else segment_data.end

                            # Create a mock word list for _generate_caption_block if no actual words
                            mock_words_for_block = [{'start': start_seconds, 'end': end_seconds, 'word': utterance_transcript_text, 'punctuated_word': utterance_transcript_text}]

                            block_text = _generate_caption_block(mock_words_for_block, srt_sequence_number, output_format)
                            if block_text:
                                final_caption_blocks.append(block_text)
                                if output_format.lower() == "srt": srt_sequence_number += 1
                                segment_processed_successfully = True
                        else: # Apply splitting logic using words_list
                            current_line_words = []
                            current_char_count = 0

                            for word_idx, word_info_raw in enumerate(words_list):
                                word_info = word_info_raw # Using raw object, assuming it's ListenRESTWord

                                try:
                                    if hasattr(word_info, 'punctuated_word') and word_info.punctuated_word is not None:
                                        word_text_for_line = word_info.punctuated_word
                                    elif hasattr(word_info, 'word') and word_info.word is not None:
                                        word_text_for_line = word_info.word
                                    else:
                                        word_text_for_line = ""

                                    if hasattr(word_info, 'start') and word_info.start is not None:
                                        word_start_val = float(word_info.start)
                                    else:
                                        print(f"WARNING: Skipping word {word_idx} (text: '{word_text_for_line}') in utterance {segment_idx+1} due to missing 'start' time. Word data: {repr(word_info)}")
                                        continue

                                    if hasattr(word_info, 'end') and word_info.end is not None:
                                        word_end_val = float(word_info.end)
                                    else:
                                        print(f"WARNING: Skipping word {word_idx} (text: '{word_text_for_line}') in utterance {segment_idx+1} due to missing 'end' time. Word data: {repr(word_info)}")
                                        continue

                                    if word_end_val < word_start_val: # Check after float conversion
                                        print(f"WARNING: Skipping word {word_idx} (text: '{word_text_for_line}') in utterance {segment_idx+1} due to end time < start time. Start: {word_start_val}, End: {word_end_val}. Word data: {repr(word_info)}")
                                        word_end_val = word_start_val # Correct to start_time or skip: continue (choosing to correct for now)
                                        # continue

                                except AttributeError as e_attr:
                                    print(f"WARNING: Skipping word {word_idx} in utterance {segment_idx+1} due to AttributeError: {e_attr}. Word data: {repr(word_info)}")
                                    continue
                                except (ValueError, TypeError) as e_conv:
                                    print(f"WARNING: Skipping word {word_idx} in utterance {segment_idx+1} due to timestamp conversion error: {e_conv}. Word data: {repr(word_info)}")
                                    continue

                                word_len = len(word_text_for_line)

                                if cli_args.split_on_sentences and word_text_for_line and word_text_for_line[-1] in ".?!":
                                    current_line_words.append(word_info) # word_info is the ListenRESTWord object

                                    block_text = _generate_caption_block(current_line_words, srt_sequence_number, output_format)
                                    if block_text:
                                        final_caption_blocks.append(block_text)
                                        if output_format.lower() == "srt": srt_sequence_number += 1
                                        segment_processed_successfully = True
                                    current_line_words = []
                                    current_char_count = 0
                                    continue

                                potential_new_char_count = current_char_count + word_len + (1 if current_line_words else 0)
                                if current_line_words and potential_new_char_count > cli_args.max_caption_chars:
                                    block_text = _generate_caption_block(current_line_words, srt_sequence_number, output_format)
                                    if block_text:
                                        final_caption_blocks.append(block_text)
                                        if output_format.lower() == "srt": srt_sequence_number += 1
                                        segment_processed_successfully = True
                                    current_line_words = []
                                    current_char_count = 0

                                current_line_words.append(word_info) # Append the original word_info object
                                current_char_count += word_len + (1 if current_line_words else 0)

                            if current_line_words:
                                block_text = _generate_caption_block(current_line_words, srt_sequence_number, output_format)
                                if block_text:
                                    final_caption_blocks.append(block_text)
                                    if output_format.lower() == "srt": srt_sequence_number += 1
                                    segment_processed_successfully = True
                    except Exception as e: # Catch-all for the segment, including word processing
                        print(f"DEBUG_EXCEPTION_CONTEXT: Caught exception while processing segment_idx: {segment_idx}")
                        if 'words_list' in locals() or 'words_list' in globals():
                            print(f"DEBUG_EXCEPTION_CONTEXT: type(words_list) = {type(words_list)}")
                            if isinstance(words_list, list):
                                print(f"DEBUG_EXCEPTION_CONTEXT: len(words_list) = {len(words_list)}")
                                if 'word_idx' in locals() or 'word_idx' in globals(): # Check if word_idx was defined
                                    # Ensure word_idx is within bounds if words_list is not empty
                                    if words_list and word_idx < len(words_list):
                                        current_word_info_raw_at_error = words_list[word_idx]
                                        print(f"DEBUG_EXCEPTION_CONTEXT: Current word_idx = {word_idx}")
                                        print(f"DEBUG_EXCEPTION_CONTEXT: type(current_word_info_raw_at_error) = {type(current_word_info_raw_at_error)}")
                                        print(f"DEBUG_EXCEPTION_CONTEXT: repr(current_word_info_raw_at_error) = {repr(current_word_info_raw_at_error)}")
                                    elif not words_list and word_idx == 0: # word_idx might be 0 if words_list was empty
                                         print(f"DEBUG_EXCEPTION_CONTEXT: word_idx is {word_idx}, but words_list is empty.")
                                    else: # word_idx might be out of bounds if error happened after loop finished or words_list modified
                                        print(f"DEBUG_EXCEPTION_CONTEXT: word_idx {word_idx} may be out of bounds for words_list (len {len(words_list)}).")
                                else:
                                    print(f"DEBUG_EXCEPTION_CONTEXT: word_idx not in scope (error likely before or after word loop).")
                            else:
                                print(f"DEBUG_EXCEPTION_CONTEXT: words_list is not a list.")
                        else:
                            print(f"DEBUG_EXCEPTION_CONTEXT: words_list not in scope.")

                        # If word_info is defined from word_info = word_info_raw, also print its state
                        if 'word_info' in locals() or 'word_info' in globals():
                            print(f"DEBUG_EXCEPTION_CONTEXT: type(word_info) = {type(word_info)}")
                            print(f"DEBUG_EXCEPTION_CONTEXT: repr(word_info) = {repr(word_info)}")
                        else:
                            print(f"DEBUG_EXCEPTION_CONTEXT: word_info not in scope (error might have occurred before its assignment in the loop).")

                        print(f"WARNING: Error processing utterance segment {segment_idx+1}. ExceptionType: {type(e).__name__}, ExceptionStr: {str(e)}, ExceptionRepr: {repr(e)}. Data: {str(segment_data)[:200]}")
                        continue

                if segment_processed_successfully:
                    processed_segments_count +=1

            if processed_segments_count == 0 and len(segments_to_process) > 0:
                source_type = "paragraphs" if caption_source_is_paragraphs else "utterances"
                print(f"WARNING: All {source_type} were skipped or resulted in no valid caption blocks. Resulting file may be empty or incomplete.")

            if output_format.lower() == "srt":
                caption_content = "\n\n".join(final_caption_blocks)
                if caption_content: caption_content += "\n\n"
            elif output_format.lower() == "webvtt":
                caption_content = "WEBVTT\n\n" + "\n\n".join(final_caption_blocks)
                if final_caption_blocks: caption_content += "\n\n" # Ensure trailing newlines if content exists

    except Exception as e_caption_gen:
        print(f"ERROR: General failure during {output_format} content generation: {e_caption_gen}")
        return False

    print(f"Preparing to save caption file in {output_format.upper()} format to: {output_filename_final}")
    try:
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
        nargs='+',
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
    parser.add_argument(
        "--paragraphs",
        action="store_true",
        help="Enable paragraph segmentation. Captions will be based on paragraphs if enabled and available."
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Enable speaker diarization. May improve paragraph segmentation if --paragraphs is also enabled."
    )
    parser.add_argument(
        "--max_caption_chars",
        type=int,
        default=100,
        help="Maximum characters per caption segment (default: 100). 字幕分段最大字符数，默认100。"
    )
    parser.add_argument(
        "--split_on_sentences",
        action="store_true", # Makes it a boolean flag, True if present, False otherwise
        help="Attempt to split segments at sentence endings (e.g., '.', '?', '!') if it generally respects --max_caption_chars. 尝试在句尾分割字幕，如果这样做能大致符合最大字符限制。"
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
        if len(args.audio_file) == 1:
            current_file_output_path = args.output

        try:
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
                    continue
                except Exception as e_wave:
                    print(f"Error creating dummy audio file '{input_path}': {e_wave}. Skipping this file.")
                    files_failed += 1
                    continue

            transcription_response_obj = transcribe_audio_local(
                args.api_key,
                input_path,
                args.paragraphs,
                args.diarize
            )

            if transcription_response_obj:
                print(f"Transcription completed for '{input_path}'. Proceeding to save caption file.")

                saved_successfully = save_caption_file(
                    transcription_response_obj,
                    input_path,
                    args.format,
                    current_file_output_path,
                    enable_paragraphs_option_used=args.paragraphs,
                    cli_args=args # Pass all CLI args
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
