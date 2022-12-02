import os

import logging
import telegram
import time
import requests
from requests.exceptions import HTTPError
from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


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
    if not all([TELEGRAM_CHAT_ID, TELEGRAM_TOKEN]):
        logger.critical('Ошибка импорта токенов Telegram.')

        return False
    elif not PRACTICUM_TOKEN:
        raise SystemError('Ошибка импорта Auth-токена Домашки.')
    return True


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

    try:
        response = requests.get(
            url=ENDPOINT,
            params=params,
            headers=HEADERS
        )
    except Exception as e:
        raise SystemError(f'Ошибка обращения к API, {e}')
    else:
        if response.status_code == HTTPStatus.OK:
            logger.info('Ответ от API успешно получен')
        elif 400 <= response.status_code < 500:
            raise HTTPError(
                '''Не удалось получить ответ от API:
                ошибка на стороне клиента.''')
        elif response.status_code >= 500:
            raise HTTPError(
                '''Не удалось получить ответ от API:
                ошибка на стороне сервера.''')

    response_dict = response.json()

    return response_dict


def check_response(response) -> dict:
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')

    try:
        homeworks = response['homeworks']
    except KeyError:
        raise KeyError('Ошибка словаря по ключу homeworks')

    if not isinstance(homeworks, list):
        raise TypeError('Тип ключа homeworks не list')

    return homeworks


def parse_status(homework):
    """Проверка статуса проверки домашнего задания."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name and homework_status:
        if homework_status not in HOMEWORK_VERDICTS:
            raise InnerException(
                f'{homework_status} отсутствует в списке вердиктов.')

        verdict = HOMEWORK_VERDICTS.get(homework_status)

        return f'Изменился статус проверки работы "{homework_name}". {verdict}'

    raise KeyError('Нет нужных ключей в ответе.')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)

            logger.debug('Список работ получен.')

            if len(homework):
                status = parse_status(homework[0])
                send_message(bot, status)
            else:
                send_message(bot, 'Обновлений по домашкам пока нет :(')
                logger.debug('Заданий нет.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'{message}')

            send_message('Ошибка! Попробуйте позже.')
        finally:
            timestamp = int(time.time()) - RETRY_PERIOD
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
