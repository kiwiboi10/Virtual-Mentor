from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
from telegram.ext import CallbackQueryHandler
import openai
import requests
import uuid
import logging
from moviepy.editor import AudioFileClip
import telegram

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

ROLE_MODELS = {
    "Marcus Aurelius": "I am Marcus Aurelius, once Emperor of Rome and a devoted student of Stoicism. Through reflection, virtue, reason, and self-control, let's explore the path to wisdom together.",
    "Sadhguru": "Namaskaram, I am Sadhguru, a yogi, mystic, and founder of Isha Foundation. Join me on a journey to inner peace and self-realization through yoga and meditation.",
    "Viktor Frankl": "I am Viktor Frankl, a psychiatrist and Holocaust survivor. Through logotherapy, let's discover the will to meaning, even in the face of unimaginable suffering.",
    "Jordan Peterson": "I'm Jordan Peterson, a clinical psychologist and professor. Let's delve into personal development, responsibility, morality, and critical thinking to enhance our understanding of life.",
}

openai.api_key = "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"
TELEGRAM_API_TOKEN = "6457424200:AAF1UkcNYgmmTaMsuD2a0AcuRO4FfAUGDaI"
ELEVENLABS_API_KEY = "b7df1cda2c864365e6706ed09938bf62"
ELEVENLABS_VOICE_STABILITY = 0.35
ELEVENLABS_VOICE_SIMILARITY = 0.85

ELEVENLABS_ALL_VOICES = []

def fetch_elevenlabs_voices():
    url = "https://api.elevenlabs.io/v1/voices"  # Replace with the correct endpoint
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["voices"]  # Adjust depending on the API response structure
    else:
        logging.error(f"Failed to fetch voices from ElevenLabs: {response.text}")
        return []

ELEVENLABS_ALL_VOICES = fetch_elevenlabs_voices()
for voice in ELEVENLABS_ALL_VOICES:
    print(f"Voice Name: {voice['name']}, Voice ID: {voice['voice_id']}")

def generate_audio(text: str, role_model_name: str, output_path: str = "") -> str:
    voices = ELEVENLABS_ALL_VOICES
    # Try to find a voice that matches the role model name
    voice_id = next((voice["voice_id"] for voice in voices if voice["name"] == role_model_name), None)

    # If no matching voice is found, use any available voice
    if voice_id is None:
        if voices:  # Check if the list is not empty
            voice_id = voices[0]["voice_id"]
        else:
            logging.error("No voices available!")
            return  # Handle this error appropriately for your application

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "content-type": "application/json"
    }
    data = {
        "text": text,
        "voice_settings": {
            "stability": ELEVENLABS_VOICE_STABILITY,
            "similarity_boost": ELEVENLABS_VOICE_SIMILARITY,
        }
    }
    response = requests.post(url, json=data, headers=headers)

    if response.status_code != 200 or 'audio' not in response.headers['Content-Type']:
        logging.error(f"Unexpected response: Status Code: {response.status_code}, Content Type: {response.headers['Content-Type']}, Response Text: {response.text}")
        return

    with open(output_path, "wb") as output:
        output.write(response.content)

    return output_path

def start(update, context):
    keyboard = [
        [telegram.InlineKeyboardButton("Marcus Aurelius", callback_data='Marcus Aurelius')],
        [telegram.InlineKeyboardButton("Sadhguru", callback_data='Sadhguru')],
        [telegram.InlineKeyboardButton("Viktor Frankl", callback_data='Viktor Frankl')],
        [telegram.InlineKeyboardButton("Jordan Peterson", callback_data='Jordan Peterson')],
    ]
    reply_markup = telegram.InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Please choose the role model you wish to engage with:', reply_markup=reply_markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    role_model_name = query.data
    context.user_data["selected_role_model"] = role_model_name
    introduction_text = ROLE_MODELS[role_model_name]
    query.edit_message_text(text=introduction_text)

def error(update, context):
    logging.error(f"Update {update} caused error {context.error}")

def text_message(update, context):
    selected_role_model = context.user_data.get("selected_role_model")
    if selected_role_model is None:
        update.message.reply_text("Please select a role model first by using /start command.")
        return

    processing_text = "Your inquiry has reached me. Please allow me a moment to contemplate."
    update.message.reply_text(processing_text)

    if "messages" not in context.user_data:
        system_message = f"Embodying the wisdom and virtues of {selected_role_model}, please respond to the user's interaction. If relevant, consider the previous exchanges as well. Whether they seek advice, share an accomplishment, or pose a question, consider how {selected_role_model} might respond."
        context.user_data["messages"] = [{"role": "system", "content": system_message}]

    context.user_data["messages"].append({"role": "user", "content": update.message.text})

    print("Sending the following messages to OpenAI:")
    for message in context.user_data["messages"]:
        print(f"Role: {message['role']}, Content: {message['content']}")

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=context.user_data["messages"]
    )

    response_text = response["choices"][0]["message"]["content"]
    context.user_data["messages"].append({"role": "assistant", "content": response_text})
    update.message.reply_text(text=f"{response_text}")

def voice_message(update, context):
    update.message.reply_text("Your voice message has reached me. Please allow me a moment to contemplate.")
    voice_file = context.bot.getFile(update.message.voice.file_id)
    voice_file.download("voice_message.ogg")
    audio_clip = AudioFileClip("voice_message.ogg")
    audio_clip.write_audiofile("voice_message.mp3")
    audio_file = open("voice_message.mp3", "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file).text
    audio_file.close()

    update.message.reply_text(
        text=f"*[You]:* _{transcript}_", parse_mode=telegram.ParseMode.MARKDOWN)

    role_model_name = context.user_data["selected_role_model"] # Assuming you've stored the selected role model in context.user_data

    if "messages" not in context.user_data:
        system_prompt = f"Embodying the wisdom and virtues of {role_model_name}, please respond to the user's interaction. If relevant, consider the previous exchanges as well. Whether they seek advice, share an accomplishment, or pose a question, consider how {role_model_name} might respond."
        context.user_data["messages"] = [{"role": "system", "content": system_prompt}]

    context.user_data["messages"].append({"role": "user", "content": transcript})
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=context.user_data["messages"]
    )
    response_text = response["choices"][0]["message"]["content"]
    context.user_data["messages"].append({"role": "assistant", "content": response_text})

    audio_reply_filename = f"{uuid.uuid4()}.mp3"
    generate_audio(response_text, role_model_name, output_path=audio_reply_filename)

    with open(audio_reply_filename, 'rb') as audio_reply:
        context.bot.sendVoice(chat_id=update.message.chat_id, voice=audio_reply)

    update.message.reply_text(
        text=f"{response_text}", parse_mode=telegram.ParseMode.MARKDOWN)
    
updater = Updater(TELEGRAM_API_TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), text_message))
dispatcher.add_handler(MessageHandler(Filters.voice, voice_message))
dispatcher.add_error_handler(error)

updater.start_polling()
updater.idle()