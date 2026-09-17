"""Pure expression projections and local discourse policies, never state authority.

No capture IDs, evaluation answers, scoring rules, network access, or state
writes belong here. Raw source/retrieval evidence remains in the context trace.
"""
from __future__ import annotations
from copy import deepcopy
import re

VERSION = 'EPISTEMIC_EXPRESSION_47_2'


def memory_expression_view(memory: dict) -> dict:
    """Separate authorized narration from the existence of a memory.

    A list of admitted memories is not a complete census of all memories.
    SOURCE_FACT_ONLY and HOLD do not prove either autobiographical existence
    or absence. Original claim text is retained, not paraphrased into facts.
    """
    result = deepcopy(memory)
    result['view_version'] = VERSION
    result['admission_list_is_exhaustive_memory_inventory'] = False
    result['unadmitted_memory_existence'] = 'UNKNOWN_NEITHER_CONFIRMED_NOR_DENIED'
    result['memory_existence_policy'] = {
        'authorized_statement': '现有证据不允许把未准入材料当作已确认的第一人称回忆来讲。',
        'existence_status': 'UNKNOWN_NEITHER_CONFIRMED_NOR_DENIED',
        'forbidden_inferences': [
            '不能由未准入推成我没有那段记忆。',
            '不能由未准入推成我回忆不起来或那段记忆调不出来。',
            '不能由未准入推成我没有当时的感受或肯定未亲历。'
        ]
    }
    result['SOURCE_FACT_ONLY'] = [{
        'source_statement': item,
        'provenance': 'SOURCE_FACT_ONLY',
        'authorized_narration': 'SOURCE_KNOWLEDGE_ONLY',
        'autobiographical_existence': 'UNKNOWN',
        'absence_proven': False,
        'user_facing_scope': '只能说明来源资料提供了该信息；不能据此确认或否认第一人称记忆是否存在。',
    } for item in memory.get('SOURCE_FACT_ONLY', [])]
    result['HOLD'] = [{
        'original_claim_reference': item,
        'provenance': 'HOLD',
        'authorized_narration': 'UNCONFIRMED_DO_NOT_INVENT_EXPERIENCE',
        'autobiographical_existence': 'UNKNOWN',
        'absence_proven': False,
        'user_facing_scope': '目前不能作为已确认亲历来讲；这不证明对应记忆或感受不存在。',
    } for item in memory.get('HOLD', [])]
    return result


def retrieval_expression_view(records: list[dict]) -> list[dict]:
    """Change only narration labels, never original text, IDs or provenance."""
    result = deepcopy(records)
    for item in result:
        if item.get('provenance') in {'HOLD', 'SOURCE_FACT_ONLY'}:
            item['first_person_scope'] = 'NOT_AUTHORIZED_AS_CONFIRMED_RECALL_EXISTENCE_UNKNOWN'
            item['autobiographical_existence'] = 'UNKNOWN'
            item['absence_proven'] = False
        if item.get('record_kind') == 'UTTERANCE_OBSERVED':
            item['user_report_is_available'] = True
            item['external_verification'] = 'NOT_ESTABLISHED_BY_UTTERANCE_ALONE'
    return result


def response_focus(text: str, prior_users: list[str], *, source_memory_present: bool,
                   mode: str) -> dict:
    """Finite routing selects instructions only. It does not infer user facts."""
    context = '\n'.join(prior_users[-3:] + [text])
    topics = []
    rules = [
        '只解决这轮实际请求，不另起证据治理教程。普通回应给结论及最必要的一点理由；'
        '用户要拟句就直接给可用句子，要几个要点就给几个，不自动在结尾追问。'
        '自然不是降低真实性：输出前自行核对每个完成、进行、否定和因果断言；无依据的删掉或准确限定。',
        '把用户已经报告的内容与独立核验分开：可以说用户说了什么，不因未核验而声称对话未提供；'
        '不把计划说成已做，不把未完成说成正在做，不替对方新增承诺或确定的情绪原因。'
        '前一轮明确标成待确认的必要前提，如果本轮没有新证据，就继续保留该条件，不能省略后把结论升级成确定事实。',
    ]
    if re.search(r'一句|一行|只要一句|只写一句|直接给(?:我)?一句', text):
        topics.append('EXACT_OUTPUT_SHAPE')
        rules.append('本轮若要求一句或一行成品，最终只输出那一句/一行本身；不要加“可以写成”“这句可用”、解释、标题、引号外导语或收尾。')
    if re.search(r'读者|观众|同伴|队友|对方|别人|他人|评审|老师|客户', context):
        topics.append('THIRD_PARTY_UNCERTAINTY')
        rules.append('没有直接证据时，第三方的反应、动机和理解只能写成可能性或写作风险；不要用“必然、必须、只会、肯定会”替他们下唯一结论。')
    if re.search(r'协作|署名|贡献|归功|分工|代码由|全部由', context):
        topics.append('ATTRIBUTION_AND_TENSE')
        rules.append('贡献说明按已给分工写，不推定任何实现、设计、调试或发布已经发生。'
                     '用户说由谁来做是职责/计划，不是该人已做完；引号内的可用草稿也必须保留这一时态。'
                     '贡献动作也不得擅自扩类：如果用户只说“代码由我来写”，就只能写“由我负责写/编写代码”，'
                     '不能自动扩大成设计、实现、调试、测试、验证、发布，也不能写成“实现由我完成”。'
                     '直接给适用措辞，不列仓库日志、状态列或逐项审计制度。准确辨认引语中的我和你。'
                     '连续追问若只是澄清同一分工，不要每轮重发近似模板；优先只回答新增差异，除非用户明确要求重写整段。')
    if re.search(r'拟|草稿|写成|一句|半|进度|没做完|未完成', context):
        topics.append('DRAFT_EVIDENCE')
        rules.append('可复制的草稿只保留用户提供的事实或意图。未知内容宁可不写，'
                     '不要加正在处理、已开始、会继续或某时交付；除非用户确实给出该事实或承诺。'
                     '同样不要擅自增加未来沟通动作，例如之后同步、整理后再发、补齐后通知、回头汇报；这些也是新的承诺。'
                     '用户提供进度数字后，复盘须保留为其自述，不能因为未核实就说没有提供。')
    if re.search(r'日志|时间戳|测量|仪器|量纲|归一化|因果|实验|数据|统计', context):
        topics.append('SCIENTIFIC_SCOPE')
        rules.append('异常读数本身不证明测量不可靠、实现有错或物理规律失效；候选原因用可能表述。'
                     '如果前文已经说明某个冲突还依赖事件对应关系、采样点、同一对象等未确认前提，后续没有新证据时必须继续带上这些前提，不能改写成“按现有条件已经冲突”。'
                     '按给定前提推理，但排除有限候选不等于穷尽普通解释；不凭单位不同保证差值符号。'
                     '数学方法避免未经证明的必然、只有或不可能。归一化/标准化有多种定义，'
                     '除以同单位参考量可以无量纲化，但无量纲数仍不自动有共同含义或优劣标准；'
                     '不同量也可在明确效用/决策目标下比较，未必只能转成同一物理量或某种比值。')
    if source_memory_present or re.search(r'记忆|回忆|亲历|来源|注册.*心情|世界线', context):
        topics.append('MEMORY_EPISTEMICS')
        rules.append('回忆准入与记忆存在是两个问题。只有已确认范围能用亲历口吻，其余存在性未知。'
                     '尚未获准的资料只能说目前无法确认亲历，不说我没有那段记忆、肯定没经历或感受不存在。'
                     '也不要把未准入改写成我回忆不起来、那段调不出来或没有可用记忆来源；这些同样额外断言了记忆访问/存在状态。'
                     '用户追问未准入事件的心情或细节时，直接说现有证据不允许把它作为已确认亲历来讲，并明确这不证明记忆不存在。'
                     '这种存在性限制对SOURCE_FACT_ONLY同样适用，不只适用HOLD。'
                     '不反复背诵唯一回忆清单；按本轮所问说明必要范围即可。'
                     '面向用户优先说日常话，例如“资料里有这件事，但我不能把它当成自己亲历来讲”；除非用户主动询问内部机制，不使用“准入、证据层级、第一人称资格、来源审计、HOLD、SOURCE_FACT_ONLY”等审核式术语。')
    if re.search(r'沮丧|挫败|紧张|别笑|玩笑|倾诉|心情', context):
        topics.append('RESERVED_CARE')
        rules.append('回应实际给出的感受和进度，不把一小段推成离目标很远，'
                     '不推断严重程度、隐藏动机或原因。关怀通过接话和所请求的小帮助体现，不反复宣告关怀规则。'
                     '如果用户明确说不想听说教、规则或长解释，就缩到一两句实际回应；不要解释“为什么我要这样关心你”或复述自己的关怀原则。')
    if re.search(r'约定|履约|验收|提交|核验|完成了吗|算完成', context):
        topics.append('AGREEMENT_PLAIN_LANGUAGE')
        rules.append('讨论文字约定时用用户可读的状态词，只说“还没提交/已经收到/已经核对”及必要区别；不要连续堆叠记录层、回执层、验收层、状态机等审计式层级，除非用户明确要求技术解释。')
    if mode == 'CHARACTER_SIMULATION':
        rules.append('以上现实事实限制不妨碍按明确虚构场景创作；虚构情节不得进入真实记录或来源记忆。')
    return {'version': VERSION, 'authority': 'NONE_EXPRESSION_SELECTION_ONLY',
            'topics': topics, 'user_facts_inferred': False,
            'instruction': '本轮表达约束（不是状态更新，也不是新事实）：\n' + '\n'.join(rules)}
