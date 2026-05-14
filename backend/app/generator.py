import textwrap

from app.schemas import AnalysisResult


class BusinessTextGenerator:
    async def suggest_replies(self, incoming_text: str, analysis: AnalysisResult, context: str = '') -> list[str]:
        topic_hint = ', '.join(analysis.topics[:3])
        base = incoming_text.strip().replace('\n', ' ')
        short_base = textwrap.shorten(base, width=180, placeholder='...')

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

    async def improve_draft(self, draft: str, analysis: AnalysisResult) -> str:
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

        if analysis.formality != 'high':
            improved = (
                'Коллеги, ' + improved[0].lower() + improved[1:]
                if improved and improved[0].isalpha()
                else 'Коллеги, ' + improved
            )

        improved = improved.replace('  ', ' ').strip()
        return improved


generator_service = BusinessTextGenerator()
