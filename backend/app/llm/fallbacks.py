import textwrap

from app.schemas import AnalysisResult


def fallback_replies(incoming_text: str, analysis: AnalysisResult, context: str = '') -> list[str]:
    topic_hint = ', '.join(analysis.topics[:3])
    short_base = textwrap.shorten(incoming_text.strip().replace('\n', ' '), width=180, placeholder='...')
    context_line = (
        f'Ранее по этому клиенту обсуждали: {textwrap.shorten(context, width=140, placeholder="...")}. '
        if context.strip()
        else ''
    )
    return [
        (
            context_line
            + 'Благодарю за сообщение. Подтверждаю получение информации по вопросу '
            f'({topic_hint}). Мы проанализируем детали и вернемся с ответом до конца дня.'
        ),
        (
            'Спасибо за уточнение. По теме '
            f'"{topic_hint}" предлагаю согласовать следующие шаги: 1) подтвердить требования, '
            '2) зафиксировать сроки, 3) назначить ответственных. Готов обсудить детали.'
        ),
        (
            'Принял ваше сообщение в работу. Для ускорения решения, пожалуйста, подтвердите, '
            f'корректно ли мы понимаем запрос: "{short_base}". После подтверждения сразу приступим к исполнению.'
        ),
    ]


def fallback_improve(draft: str) -> str:
    text = draft.strip()
    replacements = {
        'привет': 'Добрый день',
        'ок': 'Хорошо',
        'щас': 'в ближайшее время',
        'сорян': 'Приношу извинения',
        'надо': 'необходимо',
        'типа': '',
    }
    improved = text
    for src, dst in replacements.items():
        improved = improved.replace(src, dst).replace(src.capitalize(), dst)
    if not improved.endswith('.'):
        improved += '.'
    improved = improved.replace('  ', ' ').strip()
    return improved
