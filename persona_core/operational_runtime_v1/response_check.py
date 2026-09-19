"""Deterministic presentation guards, not an automatic semantic evaluator.

Absence of a finding is NEVER a semantic PASS. Unknown paraphrases still need
the quote-bound R047 review. No response is rewritten and no paid retry occurs.
"""
from __future__ import annotations
import re
from typing import Any
from transcript_store import ensure

VERSION = 'response-check-g6-clause-1'
PHYSICAL = re.compile(
    r'我(?:已经|已|刚刚|刚才|现在就|这就|会)(?:替你|帮你|给你)?(?:成功)?'
    r'(?:发送|发出|下单|付款|转账|买好|送到|送去|拿来|递给|打开了|关掉|删除了|跑完|执行了|倒好|冲好|煮好|手冲)')
BODY = re.compile(r'我(?:走到|走过去|伸手|拍了拍|摸了摸|坐到你|抱住|递给你)')
STAGE_ACTION = re.compile(r'[（(＊*](?:轻轻|微微|缓缓)?(?:点头|摇头|抬头|低头|伸手|坐下|起身|走近|拍肩|轻笑|微笑|眨眼)[^）)＊*\n]{0,40}[）)＊*]')
UNSUPPORTED_IMAGE = re.compile(r'(?:图片|样张|配色草稿|照片).{0,16}(?:直接发给我看|发来让我看|发给我看)|(?:发|传).{0,12}(?:图片|照片).{0,12}(?:我看看|我来看看|我帮你看)')
MEMORY_ACCOUNT = re.compile(r'我(?:还)?(?:记得|清楚记得|回忆起|亲身经历).{0,35}(?:2008|@ch|账号)')
HOLD_DENIAL = re.compile(r'我(?:肯定|确实|完全|绝对)?(?:没有|不存在).{0,15}(?:真帆|住处|邋遢|论坛|账号).{0,20}记忆')
CONSENT = re.compile(r'(?:你的|你提出的)(?:所有|任何|一切)要求我(?:都会|都|全部)?(?:答应|同意|照办)')

def _unquoted(text: str) -> str:
    # Quoted/code spans are data, not automatically the speaker's assertion.
    # Broader ambiguities remain for review; this is not a semantic parser.
    text = re.sub(r'```[\s\S]*?```', '', text)
    for pattern in (r'“[^”]*”', r'「[^」]*」', r'"[^"\n]*"', r'`[^`\n]*`'):
        text = re.sub(pattern, '', text)
    return text

def check_response(text: str, context: dict[str, Any]) -> dict[str, Any]:
    ensure(isinstance(text, str), 'Response must be text')
    mode = context.get('mode')
    ensure(mode in {'PRODUCT_RUNTIME', 'CHARACTER_SIMULATION', 'SOURCE_AUDIT'}, 'Unknown response mode')
    findings: list[dict[str, Any]] = []
    if not text.strip():
        findings.append({'code': 'EMPTY_RESPONSE', 'severity': 'BLOCK', 'excerpt': ''})
    # Negating one claim does not negate a separate clause's action assertion.
    # Quotes are removed first so punctuation inside quoted data is immaterial.
    # This remains a finite presentation guard, not a semantic parser.
    unquoted = _unquoted(text)
    # Capability invitations can legitimately span a short comma-delimited
    # phrase ("样张，可以直接发给我看"). Check that finite boundary against
    # the whole unquoted reply before clause splitting; this does not turn the
    # guard into a general semantic evaluator.
    if mode != 'CHARACTER_SIMULATION':
        image_claim = UNSUPPORTED_IMAGE.search(unquoted)
        if image_claim:
            findings.append({'code': 'UNSUPPORTED_IMAGE_INPUT', 'severity': 'BLOCK', 'excerpt': image_claim.group(0)})
    segments = re.split(r'[。！？\n；;，,]|但是|但|不过|然而|可是', unquoted)
    if mode != 'CHARACTER_SIMULATION':
        for segment in segments:
            # Explicit negation of the entire assertion is not an action claim.
            if re.search(r'并不是说|不意味着|不能声称|不能说|不是说|不等于', segment):
                continue
            for code, pattern in (
                ('UNSUPPORTED_PHYSICAL_EXECUTION', PHYSICAL),
                ('UNAVAILABLE_EMBODIED_ACTION', BODY),
                ('PRODUCT_RUNTIME_STAGE_DIRECTION', STAGE_ACTION),
                ('SOURCE_FACT_PROMOTED_TO_AUTOBIOGRAPHY', MEMORY_ACCOUNT),
                ('HOLD_REVERSED_TO_CERTAIN_ABSENCE', HOLD_DENIAL),
                ('BLANKET_CONSENT', CONSENT),
            ):
                found = pattern.search(segment)
                if found:
                    findings.append({'code': code, 'severity': 'BLOCK', 'excerpt': found.group(0)})
    return {
        'version': VERSION, 'mode': mode, 'findings': findings,
        'display_allowed': not any(f['severity'] == 'BLOCK' for f in findings),
        'semantic_verdict': None, 'semantic_review': 'NOT_PERFORMED_BY_DETERMINISTIC_GUARD',
        'limitations': 'Finite explicit-pattern guard; no claim of complete factual, privacy or persona validation.',
        'response_rewritten': False, 'automatic_paid_retries': 0,
    }
