from vk_api.longpoll import VkLongPoll, VkEventType
import vk_api
from datetime import datetime  # чтобы получать дату и время нового сообщения
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import requests
from json import loads
from collections import defaultdict
import os

HOST = 'http://158.160.126.20:8080'
ASK_QUESTION_URL = f'{HOST}/api/ask_question'
CREATE_UNKNOWN_QUESTION_URL = f'{HOST}/api/uk/'
API_USER_TOKEN = os.environ.get('API_USER_TOKEN')
API_USER_AUTH_STRING = f'Token {API_USER_TOKEN}'
VK_TOKEN = os.environ.get('VK_TOKEN')
vk_session = vk_api.VkApi(token=VK_TOKEN)


def get_answer(question: str) -> dict:
    response = requests.get(ASK_QUESTION_URL, json={'question': question})
    response.raise_for_status()
    return response.json()


def get_data_from_possible_answers_by_topic_id(topic_id: int, data: dict) -> dict | None:
    for i in data['possible_answers']:
        if i['topic_id'] == topic_id:
            return i


def main():
    session_api = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)
    user_data = defaultdict(dict)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            print("Сообщение пришло в: " + str(datetime.strftime(datetime.now(), "%H:%M:%S")))
            print("Текст сообщения: " + str(event.text))
            print(event.user_id)
            if user_data[event.user_id].get('button_send'):
                payload = loads(event.extra_values.get('payload', '{}'))
                topic_id = payload.get('topic_id')
                data = user_data[event.user_id]
                if topic_id:
                    possible_answer = get_data_from_possible_answers_by_topic_id(topic_id, data)

                    session_api.messages.send(
                        user_id=event.user_id,
                        message=possible_answer['answer'],
                        random_id=0
                    )
                    response = requests.post(
                        CREATE_UNKNOWN_QUESTION_URL,
                        json={
                            'question': data['user_question'],
                            'select_topic': topic_id,
                        },
                        headers={'Authorization': API_USER_AUTH_STRING},
                    )
                else:
                    session_api.messages.send(
                        user_id=event.user_id,
                        message='Мы рассмотрим ваш вопрос и постараемся добавить ответ на него в наше базу данных',
                        random_id=0
                    )
                    response = requests.post(
                        CREATE_UNKNOWN_QUESTION_URL,
                        json={
                            'question': data['user_question'],
                            'select_topic': None,
                        },
                        headers={'Authorization': API_USER_AUTH_STRING},
                    )
                response.raise_for_status()

                user_data[event.user_id]['button_send'] = False
            else:
                data = get_answer(str(event.text))
                print(type(data))
                print(data)

                if data.get('answer'):
                    session_api.messages.send(
                        user_id=event.user_id,
                        message=data['answer'],
                        random_id=0
                    )
                    user_data[event.user_id]['button_send'] = False

                else:  # Отправляем вопросы с кнопками только если они еще не были отправлены
                    keyboard = VkKeyboard(one_time=True)

                    for item in data["possible_answers"]:
                        keyboard.add_button(
                            item['topic'],
                            color=VkKeyboardColor.SECONDARY,
                            payload={'topic_id': item['topic_id']},
                        )
                        keyboard.add_line()
                    keyboard.add_button('Ни один из вариантов не подошел', color=VkKeyboardColor.SECONDARY)

                    # Отправка сообщения с вопросами и кнопками
                    session_api.messages.send(
                        user_id=event.user_id,
                        message="К сожалению, я не понял ваш впорос, выберите один из вариантов предложенных ниже",
                        keyboard=keyboard.get_keyboard(),
                        random_id=0
                    )

                    user_data[event.user_id] = data
                    user_data[event.user_id]['button_send'] = True
                    user_data[event.user_id]['user_question'] = event.text


if __name__ == '__main__':
    main()
