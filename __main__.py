import telebot
import langid
import os
import re
from dotenv import load_dotenv
from pydub import AudioSegment

import pdfplumber

def split_text(text, max_length=2000):
    # Разбиваем текст на предложения с использованием регулярных выражений
    sentences = re.split(r'(?<=[.!?]) +', text)
    parts = []
    current_part = ""

    for sentence in sentences:
        # Если добавление следующего предложения превышает максимальную длину, сохраняем текущую часть
        if len(current_part) + len(sentence) + 1 > max_length:  # +1 на пробел
            parts.append(current_part.strip())
            current_part = sentence
        else:
            if current_part:  # Если текущая часть не пустая, добавим пробел перед предложением
                current_part += " "
            current_part += sentence

    # Не забудем добавить последнюю часть, если она не пустая
    if current_part:
        parts.append(current_part.strip())

    return parts


# Загрузка переменных окружения из .env файла
load_dotenv()

bot = telebot.TeleBot(os.getenv('TG_KEY'))

# Для обеспечения воспроизводимости результатов
langid.set_languages(['en', 'ru'])

# Определение команд и их описаний
commands = [
    telebot.types.BotCommand("/start", "Главное меню")
]

with open('allowed_user.txt', 'r', encoding='utf-8') as file:
    # Читаем строки и убираем символы конца строк
    allowed_users = [line.strip() for line in file]
if os.getenv('ADMIN_TG_USERNAME') not in allowed_users:
    allowed_users.append(os.getenv('ADMIN_TG_USERNAME'))
print(allowed_users)

# Установка команд
bot.set_my_commands(commands)
user_states = {}

def add_line_to_file_and_list(new_line, filename='file.txt', lines=None):
    # Если lines не инициализирован, создаем пустой список
    if lines is None:
        lines = []

    # Добавляем новую строку в список
    lines.append(new_line)

    # Открываем файл в режиме добавления (append)
    with open(filename, 'a', encoding='utf-8') as file:
        # Записываем новую строку в файл с символом новой строки
        file.write(new_line + '\n')

    return lines

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda message: message.text == "Главное меню")
def send_welcome(message):

    # Отправка сообщения с картинкой (URL изображения)
    bot.send_message(message.chat.id,
                   "Привет! Присылай сюда тексты на русском и английском в форматах .pdf, .txt или просто сообщением. Я их озвучу!")

@bot.message_handler(commands=['add'])
def admin_to_all(message):
    if message.chat.username == os.getenv('ADMIN_TG_USERNAME'):
        keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(telebot.types.KeyboardButton("/back"))

        bot.send_message(message.chat.id,
                         "Введите нового пользователя (/back для отмены):",
                         reply_markup=keyboard)

        user_states[message.chat.id] = "waiting_for_add"

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_for_add")
def admin_add_send(message):
    if message.text == '/back':
        bot.send_message(message.chat.id,"Отмена")
    else:
        if message.text in allowed_users:
            bot.send_message(message.chat.id, "Пользователь уже в списке")
        else:
            allowed_users.append(message.text)
            with open('allowed_user.txt', 'a', encoding='utf-8') as file:
                # Записываем новую строку в файл с символом новой строки
                file.write(message.text + '\n')
            bot.send_message(message.chat.id, "Пользователь добавлен")

    user_states.pop(message.chat.id, None)
    print(allowed_users)
    send_welcome(message)
    return

@bot.message_handler(commands=['rm'])
def admin_to_all(message):
    if message.chat.username == os.getenv('ADMIN_TG_USERNAME'):
        keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(telebot.types.KeyboardButton("/back"))

        bot.send_message(message.chat.id,
                         "Введите ник удаляемого пользователя (/back для отмены):",
                         reply_markup=keyboard)

        user_states[message.chat.id] = "waiting_for_rm"

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_for_rm")
def admin_rm_send(message):
    if message.text == '/back':
        bot.send_message(message.chat.id,"Отмена")
    else:
        if message.text in allowed_users:
            allowed_users.remove(message.text)

            # Перезаписываем файл без удаляемой строки
            with open('allowed_user.txt', 'w', encoding='utf-8') as file:
                for user in allowed_users:
                    file.write(user + '\n')
            bot.send_message(message.chat.id, "Пользователь удален")
        else:
            bot.send_message(message.chat.id, "Пользователь не найден")

    user_states.pop(message.chat.id, None)
    print(allowed_users)
    send_welcome(message)
    return

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.chat.username not in allowed_users:
        bot.reply_to(message, f"Вас нет в списке пользователей")
        return
    user = message.chat.id

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Определение типа файла
    file_name = message.document.file_name
    file_extension = os.path.splitext(file_name)[1].lower()

    # Обработка TXT файлов
    if file_extension == '.txt':
        text = downloaded_file.decode('utf-8')
        echo_all(message, text=text)

    # Обработка PDF файлов
    elif file_extension == '.pdf':
        with open(f'tmp/temp_{user}.pdf', 'wb') as temp_pdf:
            temp_pdf.write(downloaded_file)
        with pdfplumber.open(f'tmp/temp_{user}.pdf') as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() + '\n'
        echo_all(message, text=text)
        os.remove(f'tmp/temp_{user}.pdf')

    else:
        bot.reply_to(message, f"Файл формата {file_extension} не поддерживается.")


from deepgram import DeepgramClient, SpeakOptions
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_KEY')

import json
import requests

def synthesize(folder_id, iam_token, text):
    url = 'https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize'
    headers = {
        'Authorization': 'Bearer ' + iam_token,
    }

    data = {
        'text': text,
        'lang': 'ru-RU',
        'voice': 'ermil',
        'emotion': 'good',
        'folderId': folder_id,
        'sampleRateHertz': 48000,
    }

    with requests.post(url, headers=headers, data=data, stream=True) as resp:
        if resp.status_code != 200:
            raise RuntimeError("Invalid response received: code: %d, message: %s" % (resp.status_code, resp.text))

        for chunk in resp.iter_content(chunk_size=None):
            yield chunk


def get_yndx_api():
    oauth_token = os.getenv('YNDX_OATH')
    url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "yandexPassportOauthToken": oauth_token
    }

    response = requests.post(url, headers=headers, data=json.dumps(data)).json()

    return response['iamToken']

@bot.message_handler(func=lambda message: True)
def echo_all(message, text = ''):
    if message.chat.username not in allowed_users:
        bot.reply_to(message, f"Вас нет в списке пользователей")
        return

    if text == '':
        text = message.text

    reply = message.content_type

    try:
        # Определяем язык текста
        language, score = langid.classify(text)
        reply += f'\nЯзык текста: {language}'

        if language == 'en':
            try:
                last_message_id = bot.reply_to(message, reply+'\nРазбивка файла...').message_id

                texts = split_text(text, 2000)
                print(f'requesting english voiceover. text splitted to list of {len(texts)}')

                bot.edit_message_text(reply+f'\nФайл разбит на {len(texts)} сегмент(ов)', chat_id=message.chat.id, message_id=last_message_id)

                deepgram = DeepgramClient(DEEPGRAM_API_KEY)
                user = message.chat.id

                options = SpeakOptions(
                    model="aura-orpheus-en",
                )

                filename = f'tmp/output_{user}.mp3'
                audio_segments = []
                i = 0
                for text in texts:
                    bot.edit_message_text(reply + f'\nОзвучиваю ({i+1} / {len(texts)}) ...', chat_id=message.chat.id,
                                          message_id=last_message_id)

                    tmp_filename = f'tmp/output_{user}_{i}.mp3'
                    response = deepgram.speak.rest.v("1").save(tmp_filename, {"text": text}, options)
                    print(response.to_json(indent=4))

                    audio_segments.append(AudioSegment.from_file(tmp_filename))
                    i+=1

                combined = sum(audio_segments)

                # Сохранение объединенного файла
                combined.export(filename, format='mp3')

                # STEP 4: Отправить голосовое сообщение пользователю
                with open(filename, 'rb') as voice:
                    bot.edit_message_text(reply + f'\nОтправляю озвучку ...', chat_id=message.chat.id,
                                          message_id=last_message_id)
                    bot.send_voice(chat_id=message.chat.id, voice=voice, reply_to_message_id=message.message_id)

                os.remove(f'tmp/output_{user}.mp3')
                for j in range(i):
                    os.remove(f'tmp/output_{user}_{j}.mp3')

                reply += '\nОзвучено успешно с помощью Deepgram'
                bot.edit_message_text(reply, chat_id=message.chat.id, message_id=last_message_id)
                print(f'English voiceover sucsessfully sent.')

            except Exception as e:
                reply += f'\nНе удалось озвучить текст. \nОшибка {e}'
                bot.reply_to(message, reply)
        else:
            try:
                last_message_id = bot.reply_to(message, reply + '\nРазбивка файла...').message_id

                texts = split_text(text, 5000)

                print(f'requesting russian voiceover. text splitted to list of {len(texts)}')
                bot.edit_message_text(reply+f'\nФайл разбит на {len(texts)} сегмент(ов)', chat_id=message.chat.id, message_id=last_message_id)

                token = get_yndx_api()
                user = message.chat.id
                filename = f'tmp/output_{user}.mp3'
                audio_segments = []
                i = 0
                for text in texts:
                    bot.edit_message_text(reply + f'\nОзвучиваю ({i+1} / {len(texts)}) ...', chat_id=message.chat.id,
                                          message_id=last_message_id)

                    tmp_filename = f'tmp/output_{user}_{i}.mp3'

                    with open(tmp_filename, "wb") as f:
                        for audio_content in synthesize(os.getenv('YNDX_FOLDER'), token, text):
                            f.write(audio_content)

                    print(f'{i} is ok')

                    audio_segments.append(AudioSegment.from_file(tmp_filename))
                    i+=1

                combined = sum(audio_segments)

                # Сохранение объединенного файла
                combined.export(filename, format='mp3')

                # STEP 4: Отправить голосовое сообщение пользователю
                with open(filename, 'rb') as voice:
                    bot.edit_message_text(reply + f'\nОтправляю озвучку ...', chat_id=message.chat.id,
                                          message_id=last_message_id)
                    bot.send_voice(chat_id=message.chat.id, voice=voice, reply_to_message_id=message.message_id)

                os.remove(f'tmp/output_{user}.mp3')
                for j in range(i):
                    os.remove(f'tmp/output_{user}_{j}.mp3')

                reply += '\nОзвучено успешно с помощью Yandex SpeechKit'
                bot.edit_message_text(reply, chat_id=message.chat.id, message_id=last_message_id)
                print(f'Russian voiceover sucsessfully sent.')

            except Exception as e:
                reply += f'\nНе удалось озвучить текст. \nОшибка {e}'
                bot.reply_to(message, reply)
            pass

    except Exception as e:
        reply += f'\nНе удалось определить язык текста.'
        bot.reply_to(message, reply)

# Запускаем бота
bot.infinity_polling()

if __name__ == "__main__":
    # Запускаем бота
    bot.infinity_polling()