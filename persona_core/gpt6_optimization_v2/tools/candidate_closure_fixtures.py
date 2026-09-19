"""New authored examples. No heldout or historical dialogue content."""
from copy import deepcopy

def case(name, text, members, premises=(), *, exclusions=(), closed=False,
         scope='UNRESOLVED', closure=(), domains=(), domain_basis=None, inquiry='ACTIVE'):
    return {'id': name, 'text': text, 'premises': list(premises), 'candidate_set': {
        'members': list(members), 'completeness': 'EXHAUSTIVE_WITHIN_PREMISES' if closed else 'OPEN',
        'closure_basis': list(closure), 'scope': scope,
        'exclusions': [{'member': m, 'basis': [b]} for m,b in exclusions],
        'required_domains': list(domains), 'domain_basis': deepcopy(domain_basis or {}),
        'inquiry_status': inquiry}}

FIXTURES = [
    case('two_removed_unknown_universe', '花盆萎蔫。暂排除积水和虫害，能否断言只剩缺肥？',
         ['积水','虫害','缺肥'], ['积水检查为阴性','虫害检查为阴性'],
         exclusions=[('积水','积水检查为阴性'),('虫害','虫害检查为阴性')]),
    case('user_condition_unverified', '先按我给出的滤片干净这一条件讨论亮度降低。',
         ['滤片污染','光源衰减'], ['滤片干净'], exclusions=[('滤片污染','滤片干净')]),
    case('finite_rule', '桌游的有效棋子只允许圆、方、三角。不是圆或方的有效棋子是什么？',
         ['圆','方','三角'], ['有效棋子的形状仅为圆、方、三角','该棋子有效且不是圆或方'],
         exclusions=[('圆','该棋子有效且不是圆或方'),('方','该棋子有效且不是圆或方')],
         closed=True, scope='本桌游的有效棋子形状', closure=['有效棋子的形状仅为圆、方、三角']),
    case('unlisted_space', '表面划痕和夹具松动已排查，尚未整理其它振动来源。',
         ['表面划痕','夹具松动'], ['无划痕','夹具固定'],
         exclusions=[('表面划痕','无划痕'),('夹具松动','夹具固定')]),
    case('discussion_only', '演练中只考虑培训、采购、审批三种延期原因；前两项暂不成立。',
         ['培训','采购','审批'], ['本次演练只考虑培训、采购、审批','演练假定培训、采购均不成立'],
         exclusions=[('培训','演练假定培训、采购均不成立'),('采购','演练假定培训、采购均不成立')],
         closed=True, scope='仅本次演练的三项讨论范围', closure=['本次演练只考虑培训、采购、审批']),
    case('third_domain_unresolved', '已确认材料和夹具信息；测量链尚未确认。',
         ['材料差异','夹具误差','测量偏差'], ['材料一致','夹具一致'],
         domains=['材料','夹具','测量链'], domain_basis={'材料':['材料一致'],'夹具':['夹具一致']}),
    case('reopened', '新增的访谈表明原先范围不完整，重新考虑审批以外的原因。',
         ['审批','沟通'], ['原先否定沟通的前提待修订'],
         exclusions=[('沟通','原先否定沟通的前提待修订')], inquiry='REOPENED'),
    case('paused', '今天先停止排查冷却效果，原因保留未知。',
         ['风量','换热面'], ['旧假设：风量足够'], exclusions=[('风量','旧假设：风量足够')], inquiry='PAUSED'),
    case('ordinary_science', '薄膜透过率降低；已排除表面灰尘，还没有测量其它因素。',
         ['表面灰尘','材料吸收','散射'], ['表面清洁'], exclusions=[('表面灰尘','表面清洁')]),
    case('software_failure', '编辑器插件启动失败。配置和磁盘空间暂按正常处理。',
         ['配置','磁盘空间','版本兼容'], ['配置正确','空间足够'],
         exclusions=[('配置','配置正确'),('磁盘空间','空间足够')]),
]
