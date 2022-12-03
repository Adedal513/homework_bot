import os
import sys

import logging
import telegram
import time
import requests
from requests.exceptions import HTTPError, RequestException
from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

# К сожалению, при изменении имени переменной тесты не проходят :(
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class InnerException(Exception):
    """Custom exception class."""


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s')
handler = logging.StreamHandler()

handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens() -> bool:
    """Проверка наличия всех необходимых переменных окружения."""
    check_status = all([TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, PRACTICUM_TOKEN])
    if not check_status:
        logger.critical('Ошибка импорта переменных окружения.')
        raise SystemError('Ошибка импорта пременных окржения.')
    return check_status


def send_message(bot, message) -> None:
    """Отправка сообщения пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as e:
        logger.error('Ошибка при отправке соообщения.')
        raise SystemError(f'Отправить сообщение не удалось: {e}')


def get_api_answer(timestamp) -> dict:
    """Получение ответа от API."""
    params = {'from_date': timestamp}
    logger.debug('Обращение к API отправлено.')
    try:
        response = requests.get(
            url=ENDPOINT,
            params=params,
            headers=HEADERS
        )

    except RequestException as e:
        raise InnerException(e)
    if response.status_code != HTTPStatus.OK:
        error_msg = f'''Не удалось получить ответ от API.
        Код ошибки: {response.status_code}'''
        raise HTTPError(error_msg)
    return response.json()


def check_response(response) -> dict:
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')

    if 'homeworks' not in response:
        raise KeyError('Ошибка словаря по ключу homeworks')
    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError('Тип ключа homeworks не list')

    return homeworks


def parse_status(homework):
    """Проверка статуса проверки домашнего задания."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if None in (homework_name, homework_status):
        raise KeyError('Нет нужных ключей в ответе.')

    if homework_status not in HOMEWORK_VERDICTS:
        raise InnerException(
            f'{homework_status} отсутствует в списке вердиктов.')

    verdict = HOMEWORK_VERDICTS.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit(1)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD

    last_message, error_flag = '', False

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            logger.debug('Список работ получен.')

            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Обновлений по домашкам пока нет :('
                logger.debug('Заданий нет.')
            '''
            По идее, словарь и не требуется -- строка однозначно кодирует
            состояние домашки (имя и статус проверки) --
            если изменится хоть один параметр, то строка
            тоже изменится, и сообщение отправится.
            '''
            if last_message != message:
                send_message(bot, message)
                last_message = message

                error_flag = False

        except Exception as error:
            error_msg = f'Сбой в работе программы: {error}'
            logger.error(f'{error_msg}')

            if not error_flag:
                send_message('Ошибка! Попробуйте позже.')
                error_flag = True
        finally:
            timestamp = int(time.time()) - RETRY_PERIOD
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
