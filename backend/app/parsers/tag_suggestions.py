from typing import Any
import json

def tag_suggestion_schema() -> dict[str, Any]:
    return {
        'type': 'object',
        'properties': {
            'auto_tags': {'type': 'array', 'items': {'type': 'string'}},
            'suggested_tags': {'type': 'array', 'items': {'type': 'string'}},
            'priority': {'type': 'boolean'},
        },
        'required': ['auto_tags', 'suggested_tags', 'priority'],
    }

def parse_tag_suggestions(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    auto_tags = [str(tag).strip().capitalize() for tag in parsed.get('auto_tags', []) if str(tag).strip()][:2]
    suggested_tags = [str(tag).strip().capitalize() for tag in parsed.get('suggested_tags', []) if str(tag).strip()][:2]
    priority = bool(parsed.get('priority', False))
    return {
        'auto_tags': auto_tags,
        'suggested_tags': suggested_tags,
        'priority': priority,
    }


def empty_tag_suggestions() -> dict[str, Any]:
    return {'auto_tags': [], 'suggested_tags': [], 'priority': False}
