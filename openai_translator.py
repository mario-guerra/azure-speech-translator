import argparse
import asyncio
import os
import re
import tiktoken
import PyPDF2
import docx
import requests
from bs4 import BeautifulSoup
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.chat_request_settings import ChatRequestSettings
from semantic_kernel.connectors.ai.ai_exception import AIException

# Dictionary defining chunk sizes, which influence verbosity of the chat model output.
# The larger the chunk size, the more verbose the output. The chunk size is
# used to determine the number of characters to process in a given text during a
# single request to the chat model.
translation_levels = {
    "verbose": 5000,
    "concise": 10000,
    "terse": 20000,
}

# Dictionary defining request token sizes, which influence verbosity of the chat model output.
# The larger the request token size, the more verbose the output. The request token size is
# used to determine the number of tokens to request from the chat model during a single request.
request_token_sizes = {
    "verbose": 3000,
    "concise": 2000,
    "terse": 1000,
}

translation_prompts = {
    # "verbose": """Translate Estonian text to English. Create a cohesive narrative while retaining the narrative point of view, tone, meaning, and flow of the original text. Don't embellish the translation. Include details like names, places, events, and amounts. Remove labels in '[]' brackets, add paragraph breaks for readability.""",
    "verbose": """Richly translate from Spanish to English, retaining key details like names, dates, locations, and amounts, and incorporating new information from [CURRENT_CHUNK] into [PREVIOUS_TRANSLATION]. Retain the first two paragraphs of [PREVIOUS_TRANSLATION]. Remove labels, add paragraph breaks for readability. Focus on creating a cohesive narrative that flows as if someone is speaking in English without embellishment. Retain the narrative point of view from the original text.""",
    # "concise": """Translate from Estonian to English, retaining details like names, dates, places, and amounts. Integrate translated text from [CURRENT_CHUNK] into [PREVIOUS_TRANSLATION]. Retain the first two paragraphs of [PREVIOUS_TRANSLATION], update other paragraphs with new context as appropriate. Remove labels, add paragraph breaks for readability. Create a cohesive narrative without embellishing the translated text. Retain the narrative point of view from the original text.""",
    # "concise": """Translate from Estonian to English, keeping details such as names, dates, places, and amounts. Seamlessly integrate the translated text from the current section into the existing translation while maintaining the first two paragraphs of the existing translation. Update other paragraphs with new context as needed. Remove labels and add paragraph breaks for readability. Craft a smooth and natural narrative flow, as if someone is speaking, without embellishing the translation. Retain the narrative point of view from the original text.""",
    "concise": """Richly translate from Spanish to English, retaining key details like names, dates, locations, and amounts, and incorporating new information from [CURRENT_CHUNK] into [PREVIOUS_TRANSLATION]. Retain the first two paragraphs of [PREVIOUS_TRANSLATION]. Remove labels, add paragraph breaks for readability. Focus on creating a cohesive narrative that flows as if someone is speaking in English without embellishment. Retain the narrative point of view from the original text.""",
    "terse": """Translate to English tersely, retaining details including names, and incorporating new information from [CURRENT_CHUNK] into [PREVIOUS_TRANSLATION]. Retain the first two paragraphs of [PREVIOUS_TRANSLATION]. Remove labels, add paragraph breaks for readability. Create a cohesive narrative without embellishing the translated text. Retain the narrative point of view from the original text.""",
}

# Initialize the semantic kernel for use in getting settings from .env file.
# I'm not using the semantic kernel pipeline for communicating with the GPT models,
# I'm using the semantic kernel service connectors directly for simplicity.
kernel = sk.Kernel()

# Get deployment, API key, and endpoint from environment variables
deployment, api_key, endpoint = sk.azure_openai_settings_from_dot_env()

# Using the chat completion service for summarizing text. 
# Initialize the translation service with the deployment, endpoint, and API key
translation_service = AzureChatCompletion(deployment, endpoint, api_key)

# Get the encoding model for token estimation. This is needed to estimate the number of tokens the
# text chunk will take up, so that we can process the text in chunks that fit within the context window.
# gpt-3.5-turbo uses the same encoding model as gpt-4, so we can use the same encoding model for token estimation.
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

# Estimate the token count of a given text
def estimate_token_count(text):
    tokens = encoding.encode(text)
    length = len(tokens)
    return length

# Define a method for creating a translation asynchronously. Each time this method is called,
# a list of messages is created and seeded with the system prompt, along with the user input.
# The user input consists of a portion of the previous translation, along with the current text chunk
# being processed.
#
# The number of tokens requested from the model is based on the tokenized size of the
# input text plus the system prompt tokens. The larger the chunk size, the fewer tokens
# we can request from the model to fit within the context window. Therefore the model
# will be less verbose with larger chunk sizes.
async def create_translation(input, translation_level):
    messages = [("system", translation_prompts[translation_level]), ("user", input)]
    request_size = request_token_sizes[translation_level]
    reply = await translation_service.complete_chat_async(messages=messages,request_settings=ChatRequestSettings(temperature=0.4, top_p=0.4, max_tokens=request_size))
    return(reply)

# Extract text from a PDF file
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
    return text

# Extract text from a Word document
def extract_text_from_word(doc_path):
    doc = docx.Document(doc_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

# Extract text from a URL
def extract_text_from_url(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    text = soup.get_text(separator="\n")
    return text

# Process text and handle ChatGPT rate limit errors with retries. Rate limit errors
# are passed as a string in the translation text rather than thrown as an exception, which
# is why we need to check for the error message in the translation text. If a rate limit
# error is encountered, the method will retry the request after the specified delay.
# The delay is extracted from the error message, since it explicitly states how long
#  to wait before a retry.
async def process_text(input_text, translation_level):
    MAX_RETRIES = 5
    retry_count = 0
    TIMEOUT_DELAY = 5  # Adjust the delay as needed

    request_size = request_token_sizes[translation_level]

    while retry_count < MAX_RETRIES:
        try:
            translation = await create_translation(input_text, translation_level)
            if "exceeded token rate limit" in str(translation):
                error_message = str(translation)
                delay_str = re.search(r'Please retry after (\d+)', error_message)
                if delay_str:
                    delay = int(delay_str.group(1))
                    print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    retry_count += 1
                else:
                    raise Exception("Unknown error message when processing text.")
            else:
                return translation
        except AIException as e:
            if "Request timed out" in str(e):
                print(f"Timeout error occurred. Retrying in {TIMEOUT_DELAY} seconds...")
                await asyncio.sleep(TIMEOUT_DELAY)
                retry_count += 1
            elif "exceeded token rate limit" in str(e):
                error_message = str(e)
                delay_str = re.search(r'Please retry after (\d+)', error_message)
                if delay_str:
                    delay = int(delay_str.group(1))
                    print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    retry_count += 1
            else:
                raise
    if retry_count == MAX_RETRIES:
        if "Request timed out" in str(e):
            raise Exception("Timeout error. All retries failed.")
        else:
            raise Exception("Rate limit error. All retries failed.")

# Write paragraphs to the output file
def write_paragraphs(out_f, paragraphs):
    for p in paragraphs:
        out_f.write(p + "\n\n")
        out_f.flush()

# Extract translation paragraphs from the translation text
def extract_translation_paragraphs(translation_text):
    paragraphs = str(translation_text).split('\n\n')
    return [p.strip() for p in paragraphs]

# translate a document asynchronously
async def translate_document(input_path, output_path, translation_level):
    max_context_paragraphs = 3
    PREVIOUS_TRANSLATION_paragraphs = []

    # Set the chunk size for processing text based on translation level.
    chunk_size = translation_levels[translation_level]

    # Remove the output file if it already exists
    if os.path.exists(output_path):
        os.remove(output_path)

    # Check the input file type and extract text accordingly
    if input_path.lower().startswith("http"):
        input_text = extract_text_from_url(input_path)
    else:
        file_extension = input_path.lower().split('.')[-1]
        if file_extension == "pdf":
            input_text = extract_text_from_pdf(input_path)
        elif file_extension == "docx":
            input_text = extract_text_from_word(input_path)
        else:
            with open(input_path, "r", encoding="utf-8") as f:
                input_text = f.read()

    total_chars = len(input_text)

    # Process the input text in chunks and generate the translation
    with open(output_path, "a", encoding="utf-8") as out_f:
        processed_chars = 0
        while True:
            print("Translating...")
            # Read a chunk of text from the input_text
            chunk = input_text[processed_chars:processed_chars+chunk_size]
            processed_chars += len(chunk)

            # Break the loop if there's no more text to process
            if not chunk:
                break

            # Combine previous translation paragraphs and the current chunk
            input_text_chunk = "[PREVIOUS_TRANSLATION]\n\n" + "\n\n".join(
                PREVIOUS_TRANSLATION_paragraphs) + "\n\n" + "[CURRENT_CHUNK]\n\n" + chunk

            # Process the text chunk and generate a translation
            translation_ctx = await process_text(input_text_chunk, translation_level)

            translation = str(translation_ctx)

            # Update the previous translation paragraphs based on the new translation.
            # If the translation has more than max_context_paragraphs, remove the first
            # paragraph until the translation is within the limit. As paragraphs are removed,
            # they are written to the output file.
            if translation:
                translation_paragraphs = extract_translation_paragraphs(translation)
                while len(translation_paragraphs) > max_context_paragraphs:
                    out_f.write(translation_paragraphs.pop(0) + "\n\n")
                    out_f.flush()
                PREVIOUS_TRANSLATION_paragraphs = translation_paragraphs
                print("\Translation window: \n", translation)
            else:
                print("No translation generated for the current chunk.")

            # Calculate and display the progress of the summarization
            progress = (processed_chars / total_chars) * 100
            print(
                f"\nProgress: {processed_chars}/{total_chars} ({progress:.2f}%)")

        # Write the remaining translation paragraphs to the output file
        # write_paragraphs(out_f, PREVIOUS_TRANSLATION_paragraphs)
        while PREVIOUS_TRANSLATION_paragraphs:
            out_f.write(PREVIOUS_TRANSLATION_paragraphs.pop(0) + "\n\n")
            out_f.flush()
    print("translation complete!")

# Define command-line argument parser
parser = argparse.ArgumentParser(description="Document Translator")
parser.add_argument("input_path", help="Path to the input text file")
parser.add_argument("output_path", help="Path to the output translation file")
parser.add_argument("--translation-level", choices=["verbose", "concise", "terse"],
                    default="concise", help="Configure translation level, concise is default")

# Parse command-line arguments
args = parser.parse_args()

# Run the summarization process
if __name__ == "__main__":

    asyncio.run(translate_document(
        args.input_path, args.output_path, translation_level=args.translation_level))
