# Copyright (c) 2023 Mario Guerra
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
import argparse
import glob
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from requests import post
import uuid
import time

# Set up argument parser
parser = argparse.ArgumentParser(description="Translates audio files using Azure Cognitive Services.")
parser.add_argument("--in-lang", required=True, help="Input language (e.g., english, spanish, estonian, french, italian, german)")
parser.add_argument("--out-lang", required=True, help="Output language (e.g., english, spanish, estonian, french, italian, german)")
parser.add_argument("input_audio_pattern", help="Path to the input audio files with wildcard pattern (e.g., ./*.wav)")
parser.add_argument("output_file", help="Path to the output file")
parser.add_argument("--transcription", help="Path to the transcription output file", default=None)

cmd_line_args = parser.parse_args()

# Load environment variables from .env file
load_dotenv()

# Set up your Azure Speech Service and Translator credentials
speech_key = os.getenv("AZURE_SPEECH_KEY")
service_region = os.getenv("AZURE_SERVICE_REGION")
translator_key = os.getenv("AZURE_TRANSLATOR_KEY")
translator_endpoint = os.getenv("AZURE_TRANSLATOR_ENDPOINT")

# See https://docs.microsoft.com/azure/cognitive-services/speech-service/language-support#speech-to-text
# for a list of supported languages for Speech Service
language_codes = {
    "english": "en-US",
    "spanish": "es-ES",
    "estonian": "et-EE",
    "french": "fr-FR",
    "italian": "it-IT",
    "german": "de-DE"
}

# See https://learn.microsoft.com/azure/ai-services/translator/language-support
# for a list of supported languages for Translator service
translator_language_codes = {
    "english": "en",
    "spanish": "es",
    "estonian": "et",
    "french": "fr",
    "italian": "it",
    "german": "de"
}

if cmd_line_args.in_lang not in language_codes:
    print("Invalid input language. Supported languages: english, spanish, estonian, french, italian, german")
    sys.exit(1)

if cmd_line_args.out_lang not in language_codes:
    print("Invalid output language. Supported languages: english, spanish, estonian, french, italian, german")
    sys.exit(1)

speech_recognition_language = language_codes[cmd_line_args.in_lang]

# Configure the Speech Service. The timeout values can be tweaked to improve translation accuracy.
# See https://learn.microsoft.com/dotnet/api/microsoft.cognitiveservices.speech.propertyid
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
speech_config.speech_recognition_language = speech_recognition_language
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "15000")
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "10000")
speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "5000")

# Define the event handlers
def on_recognized(recognition_args, in_lang, out_lang):
    source_text = recognition_args.result.text
    print(f"Transcribed text: {source_text}")

    # Write the transcribed text to the transcription output file if specified
    if cmd_line_args.transcription:
        with open(cmd_line_args.transcription, 'a', encoding='utf-8') as f:
            f.write(f"{source_text}\n")

    # Translate the source text to the specified output language
    headers = {
        'Ocp-Apim-Subscription-Key': translator_key,
        'Ocp-Apim-Subscription-Region': 'eastus',
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': source_text}]
    params = {
        'api-version': '3.0',
        'from': translator_language_codes[in_lang],
        'to': translator_language_codes[out_lang]
    }
    translate_api_path = "translate"
    api_version = "3.0"
    full_translator_endpoint = f"{translator_endpoint}/{translate_api_path}?api-version={api_version}"
    response = post(full_translator_endpoint, headers=headers, json=body, params=params)
    
    translation = response.json()[0]['translations'][0]['text']
    print(f"Translated text: {translation}")

    # Write the translated text to the output file
    with open(cmd_line_args.output_file, 'a', encoding='utf-8') as f:
        f.write(f"{translation}\n")

def on_session_stopped(args):
    print("Continuous speech recognition session stopped.")
    global session_stopped
    session_stopped = True

# Find all matching audio files
input_audio_files = glob.glob(cmd_line_args.input_audio_pattern)

# Initialize the translations list
translations = []

# Process each audio file in sequence
for input_audio_file in input_audio_files:
    print(f"Processing audio file: {input_audio_file}")

    # Read the input audio file
    with open(input_audio_file, "rb") as f:
        audio_data = f.read()

    # Transcribe the audio data
    audio_input = speechsdk.audio.AudioConfig(filename=input_audio_file)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)

    # Start continuous recognition and handle events
    session_stopped = False
    speech_recognizer.recognized.connect(lambda recognition_args: on_recognized(recognition_args, cmd_line_args.in_lang, cmd_line_args.out_lang))
    speech_recognizer.session_stopped.connect(on_session_stopped)
    speech_recognizer.start_continuous_recognition_async().get()

    # Wait for the session_stopped event to be triggered
    while not session_stopped:
        time.sleep(0.5)