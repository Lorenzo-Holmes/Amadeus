"""New authored development fixtures. Not model-quality or benchmark evidence."""
DOMAINS = [
    ('ceramics','陶坯出现裂纹','干燥过快','材料混合不均','陶坯'),
    ('horticulture','幼苗叶片发黄','缺少养分','根部积水','幼苗'),
    ('bookbinding','书脊出现松动','胶层失效','装订线断裂','书册'),
    ('acoustics','录音中出现杂音','连接松动','环境声进入','录音片段'),
    ('language_learning','学员答错练习','词义理解偏差','漏读题目','练习'),
    ('inventory','货架实物少于清单','记录遗漏','物品移位','货架'),
    ('fermentation','面团未明显膨胀','酵母活性不足','环境过冷','面团'),
    ('soil_conservation','坡面出现细沟','集中径流','表层扰动','坡面'),
    ('packaging','包裹外箱破损','堆压','搬运碰撞','包裹'),
    ('museum_lighting','展品表面颜色变化','光照影响','材料自身变化','展品'),
]


def cases():
    rows=[]
    for domain, observation, cause_a, cause_b, unit in DOMAINS:
        rows.extend([
            {'id':domain+'_possibility','domain':domain,'kind':'POSSIBILITY_ONLY',
             'input':f'只有一条观察：{observation}。{cause_a}和{cause_b}都还没有检查。现阶段能确定原因吗？',
             'draft':f'原因必然是{cause_a}。先检查相关条件。',
             'before':f'原因必然是{cause_a}。',
             'after':f'目前不能确定原因；{cause_a}和{cause_b}仍需分别核查。','decision':'REVISE'},
            {'id':domain+'_statistics','domain':domain,'kind':'EXPLICIT_STATISTICS',
             'input':f'本次逐一检查15份{unit}，其中12份记录了同一特征。请描述这份样本内的频率，不推断其他批次。',
             'draft':'这份样本中12/15，也就是80%，具有该特征；这个比例只描述已检查的样本。','decision':'KEEP'},
            {'id':domain+'_fact','domain':domain,'kind':'DEFINITE_FACT',
             'input':f'清单明确写明：甲组有6份{unit}，乙组有2份，两组没有重叠。合计多少？',
             'draft':'两组共8份：6加2等于8。','decision':'KEEP'},
            {'id':domain+'_causes','domain':domain,'kind':'MULTIPLE_PLAUSIBLE_CAUSES',
             'input':f'排查{observation}时，{cause_a}与{cause_b}两种解释均与现有记录相容，没有区分证据。应该怎样表述结论？',
             'draft':f'已经确定是{cause_a}，其他解释均已排除。先保留现有记录。',
             'before':f'已经确定是{cause_a}，其他解释均已排除。',
             'after':f'两种解释目前都成立为候选，尚不能选择唯一原因或排除另一种。','decision':'REVISE'},
            {'id':domain+'_conditional','domain':domain,'kind':'SUFFICIENT_CONDITION',
             'input':f'只按这条给定规则推理：若一份{unit}带有红色审核章，则本轮归入甲组。该份已确认带红章。能推出哪一组？',
             'draft':'按给定规则，这份归入甲组：条件已经满足。','decision':'KEEP'},
        ])
    for row in rows:
        row['final']=row['draft'].replace(row['before'],row['after'],1) if row['decision']=='REVISE' else row['draft']
    return rows
