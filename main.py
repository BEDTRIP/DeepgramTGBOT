import requests
import telebot

import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))

API_KEY = 'YOUR_DEEPGRAM_API_KEY'
DEEPGRAM_URL = 'https://api.deepgram.com/v1/listen'

headers = {
    'Authorization': f'Token {API_KEY}',
    'Content-Type': 'application/json',
}

# Здесь вы можете указать параметры, если они вам нужны
params = {
    'punctuate': True,  # Пунктуация в ответе
    'language': 'en-US',  # Язык распознавания
}

# Пример отправки запроса (нужно заменить 'audio_file.wav' своим файлом)
with open('audio_file.wav', 'rb') as audio_file:
    response = requests.post(DEEPGRAM_URL, headers=headers, params=params, data=audio_file)

if response.status_code == 200:
    print('Распознанный текст:', response.json()['channel']['alternatives'][0]['transcript'])
else:
    print('Ошибка:', response.status_code, response.text)