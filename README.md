# Audio Translation Script

This script uses Azure Cognitive Services to transcribe and translate audio files into different languages. It takes input audio files, transcribes them using the Azure Speech Service, and then translates the transcriptions into the desired output language using the Azure Translator Service.

## Requirements

- Python 3.6 or higher
- Azure Cognitive Services Speech SDK
- Azure Translator Service

## Installation

1. Install the required Python packages:

```bash
pip install azure-cognitiveservices-speech python-dotenv
```

2. Sign up for an Azure account and create a Speech Service and a Translator Service. Note the keys and endpoints for each service.

3. Create a `.env` file in the same directory as the script and add the following environment variables:

```
AZURE_SPEECH_KEY=<your_speech_service_key>
AZURE_SERVICE_REGION=<your_speech_service_region>
AZURE_TRANSLATOR_KEY=<your_translator_service_key>
AZURE_TRANSLATOR_ENDPOINT=<your_translator_service_endpoint>
```

Replace `<your_speech_service_key>`, `<your_speech_service_region>`, `<your_translator_service_key>`, and `<your_translator_service_endpoint>` with the appropriate values from your Azure account.

## Usage

Run the script with the following command:

```bash
python audio_translation.py --in-lang <input_language> --out-lang <output_language> <input_audio_pattern> <output_file> [--transcription <transcription_output_file>]
```

- `<input_language>`: The input language (e.g., english, spanish, estonian, french, italian, german)
- `<output_language>`: The output language (e.g., english, spanish, estonian, french, italian, german)
- `<input_audio_pattern>`: The path to the input audio files with a wildcard pattern (e.g., ./*.wav)
- `<output_file>`: The path to the output file containing the translations
- `<transcription_output_file>` (optional): The path to the output file containing the transcriptions

Example:

```bash
python .\azure_translator.py --in-lang spanish --out-lang english '.\Spanish test.wav' .\translation.txt
```

This command will transcribe and translate the included test audio file from Spanish to English. The translation will be saved in `translation.txt` with the following output:

```bash
Processing audio file: .\Spanish test.wav
Transcribed text: Esta es una prueba del sistema de transmisión de emergencia. Solo es una prueba si esto fuera una emergencia real, estaría corriendo para salvar mi vida.
Translated text: This is a test of the emergency transmission system. It's just a test if this was a real emergency, I would be running for my life.
Continuous speech recognition session stopped.
```