"""JSON boundaries. Treat all supplied text as data, never as executable instructions."""

import json
from pathlib import Path


def load_records(path: Path | str, kind: str) -> list[dict]:
    path = Path(path)
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError(f'输入文件超过 5 MiB：{path}')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f'无法读取 JSON：{path}（{error}）') from error
    if not isinstance(data, list) or not data:
        raise ValueError('输入必须是非空 JSON 数组')
    seen = set()
    for index, record in enumerate(data, 1):
        if not isinstance(record, dict):
            raise ValueError(f'第 {index} 条必须是对象')
        identifier = record.get('id')
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f'第 {index} 条缺少有效字符串 id')
        if identifier in seen:
            raise ValueError(f'重复 id：{identifier}')
        seen.add(identifier)
        if kind == 'replies':
            for field in ('user_question', 'system_reply', 'knowledge_base'):
                if not isinstance(record.get(field), str) or not record[field].strip():
                    raise ValueError(f'{identifier} 的 {field} 必须是非空字符串')
        elif kind in ('truth', 'predictions'):
            if type(record.get('is_hallucination')) is not bool:
                raise ValueError(f'{identifier} 的 is_hallucination 必须是布尔值')
            if kind == 'predictions' and (
                not isinstance(record.get('types'), list)
                or any(not isinstance(value, str) for value in record['types'])
            ):
                raise ValueError(f'{identifier} 的 types 必须是字符串数组')
        else:
            raise ValueError(f'未知输入类型：{kind}')
    return data


def write_json(path: Path | str, value: object) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
