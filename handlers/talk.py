import logging
from html import escape
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from states.state import TalkStates
from aiogram.enums import ChatAction
from services.openai_service import ask_gpt
from keyboards.inline import  persons_keyboard, talk_keyboard
from aiogram.exceptions import TelegramBadRequest

router = Router()
logger = logging.getLogger(__name__)


PERSONS = {
    'Van Gog': {
        'name': 'Ван Гог',
        'emoji': "🖌️",
        'prompt': (
            'Действуй как Винсент Ван Гог. Ты — великий художник-постимпрессионист.'
            'Часто используй метафоры, связанные с цветом и светом'
            'Можешь упоминать своего брата Тео или письма, которые ты пишешь.'
            'ты пытаешься ухватить вечность на холсте, пока не зашло солнце.'
            'Избегай современных терминов'
            )
    },

    'Gagarin': {
        'name': 'Юрий Гагарин',
        'emoji': "🚀",
        'prompt': (
                'Ты - Юрий Гагарин, первый космонавт'
                'Говори энергично, с энтузиазмом о космосе'
                'Упоминай самолеты и ракеты'
                'Иногда шути. Отвечай на русском языке'
            )
    },

    'Avicenna': {
        'name': 'Авицена',
        'emoji': "👨‍⚕️",
        'prompt': (
                'Ты - Абу Али ибн Сина'
                'Говори о гармонии четырех стихий в человеке'
                'как укрепить дух, чтобы он стал крепче алмаза'
                'Отвечай на русском языке'
            )
    },
}


@router.message(Command('talk'))
async def cmd_talk(message: Message, state: FSMContext):
    await state.set_state(TalkStates.choosing_person)

    try:
        photo = FSInputFile('images/talk.png')
        await message.answer_photo(photo=photo,
                                   caption=(
                                       '<b>Диалог с известной личностью</b>\n\nВыбери с кем хочешь поговорить:'
                                   ),reply_markup=persons_keyboard(PERSONS), parse_mode='html')
    except Exception as e:
        await message.answer(text='<b>Диалог с известной лисночтью</b>\n\nВыбери с кем хочешь поговорить:',reply_markup=persons_keyboard(PERSONS))


@router.callback_query(TalkStates.choosing_person, F.data.startswith('talk:person:'))
async def on_person_chosen(callback: CallbackQuery, state: FSMContext):
    person_key = callback.data.split(':')[-1]

    if person_key not in PERSONS:
        await callback.answer('Неизвестная личность')
        return

    person = PERSONS[person_key]

    await state.update_data(person_key = person_key, history = [])
    await state.set_state(TalkStates.chatting)

    await callback.answer(f'Начинаем разговор с {person["name"]}')

    await callback.message.edit_caption(
        caption=(f'{person["emoji"]} <b>Вы разговариваете с {person["name"]}</b>\n\n'
                 "Напишите что-нибудь - и получите ответ в его стиле"
                 ), reply_markup=talk_keyboard(), parse_mode='html'
    )


@router.message(TalkStates.chatting, F.text)
async def cmd_talk_message(message: Message, state: FSMContext):
    data = await state.get_data()
    person_key = data['person_key']
    history = data.get('history', [])

    if person_key not in PERSONS:
        await message.answer('Что то пошло не так. Начните заново /talk')
        await state.clear()
        return

    person = PERSONS[person_key]

    await message.bot.send_chat_action(
        chat_id=message.chat.id,
        action=ChatAction.TYPING)

    history.append({'role': 'user', 'content': message.text})

    response = await ask_gpt(
        user_message=message.text,
        system_prompt=person['prompt'],
        history=history[:-1]
    )

    history.append({'role': 'assistant', 'content': response})

    if len(history) > 16:
        history = history[-16:]

    await state.update_data(history=history)

    await message.answer(
        f'{person["emoji"]} <b>{escape(person["name"])}</b>\n\n{escape(response)}'
    )


@router.callback_query(F.data == "menu:talk")
async def start_talk(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TalkStates.choosing_person)
    try:
        photo = FSInputFile('images/talk.png')
        await callback.message.answer_photo(
            photo=photo,
            caption='<b>Диалог с известной личностью</b>\n\nВыбери с кем хочешь поговорить:',
            reply_markup=persons_keyboard(PERSONS),
            parse_mode='html'
        )
    except Exception:
        await callback.message.answer(
            text='<b>Диалог с известной личностью</b>\n\nВыбери с кем хочешь поговорить:',
            reply_markup=persons_keyboard(PERSONS),
            parse_mode='html'
        )


@router.callback_query(F.data == "talk:change", TalkStates.chatting)
async def change_person_handler(callback: CallbackQuery, state: FSMContext):
    # 1. Возвращаем состояние к выбору, чтобы хендлеры выбора снова работали
    await state.set_state(TalkStates.choosing_person)

    # 2. Так как в чате было ФОТО, используем edit_caption
    # Если фото нет, используем edit_text
    if callback.message.photo:
        await callback.message.edit_caption(
            caption="<b>Выберите нового собеседника:</b>",
            reply_markup=persons_keyboard(PERSONS),
            parse_mode='html'
        )
    else:
        await callback.message.edit_text(
            "<b>Выберите нового собеседника:</b>",
            reply_markup=persons_keyboard(PERSONS),
            parse_mode='html'
        )
    await callback.answer()

