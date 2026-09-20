# APCORE_OPENAI_USAGE_ACCOUNTING_1

合同状态：FROZEN_DESIGN_ONLY；适用于scope-7，旧费率、旧scope-6 usage语义不改。官方资料于执行当天重新GET抓取，出处与SHA-256见OFFICIAL_PRICING_EVIDENCE.json。响应usage与实际账单分开；任何本合同估算都不是已支付金额，billing_certified=false。

保留原生response usage object、response ID、request hash、requested/returned model、service tier、terminal、wire hash及native receipt version。原生字段不得先转成旧hit/miss而丢失cache_write_tokens；normalized兼容投影和native原件独立保存、互相hash绑定。scope-7的provider_call_contracts可以保存这些附加字段；不修改旧行，不给旧scope补造原生usage。

令I=input_tokens，C=input_tokens_details.cached_tokens，W=input_tokens_details.cache_write_tokens，O=output_tokens，R=output_tokens_details.reasoning_tokens，T=total_tokens。所有计数必须是非负整数（不接受bool），T=I+O，0≤C+W≤I，0≤R≤O，I≤本次可信输入预留上界，O≤32768。U=I−C−W是普通未缓存输入。三个input桶互斥，不能按全额input再叠加cache write。

USD estimate=(U×input_rate+C×cached_rate+W×write_rate+O×output_rate)/1,000,000。
reasoning在O之内，不能再加R×output_rate。max_output_tokens限制visible、reasoning及不可见格式token总量。记录 output_total_tokens=O、reasoning_tokens=R、nonreasoning_output_tokens=O−R、visible_text_utf8_bytes，以及 visible_text_tokens_local（只有具名本地tokenizer时才可填）。official_visible_tokens若无官方独立字段则null/UNKNOWN；O−R可能含格式token，不得命名为精确visible tokens。

完整usage才标ESTIMATED_FROM_COMPLETE_USAGE。若I/O有效而W缺失：W=UNKNOWN，不伪填0；已知C时输入费用上界=C×cached_rate+(I−C)×max(input_rate,write_rate)，C也缺失则I×max(input_rate,write_rate)。标BOUNDED_ESTIMATE_INCOMPLETE_CACHE_USAGE；正式receipt不接受，停止后续提交，保留本槽全预留。缺R则R和visible均UNKNOWN；缺I/O、负数、不一致、身份冲突均不得给完整费用估算或正式验收PASS。

有限预留：单槽USD上界=(I_bound×max(input_rate,write_rate)+32768×output_rate)/1e6，不假设cache hit。CNY整数预留=ceil(USD_bound×FX_cap×(1+fee_cap)×1e6)。42 PRIMARY和2 SECONDARY之和先于首笔提交证明不超过精确批准的整批guard；原150 CNY保护只留旧scope，新scope按独立approval receipt核验，不拆批。Decimal计算、不用float舍入。费用原单位USD、FX及费用条件、micro-CNY分别保存。

每槽在调用前同一SQLite事务内固化request/context、scope hash、slot和generation identity、input-bound receipt、rate/FX/approval身份及reservation。并发者重查slot唯一性、未决UNKNOWN和guard。完整usage不回写预留或将预留当消费；保留reserve用于上界，另列usage estimate。UNKNOWN/终态缺usage保留全额预留；不重试、不补槽、不释放额度后再抽样。

若服务端I超出证明上界或O超32768，记录ACCOUNTING_BOUND_VIOLATION、真实回执及新估算，立即停批；不截低usage、不宣称原上界仍成立、不通过追加预算掩盖已发生越界。无terminal的传输UNKNOWN和有terminal但accounting无效必须分别标记。已知terminal不因缺usage变成伪UNKNOWN，正式qualification仍NOT_ACCEPTED。

可信输入计数合同见INPUT_BOUND_CONTRACT.md。本轮未证明tokenizer/framing界，不能凭24576 bytes+4096这个算式解除执行阻塞。

官方依据：[定价](https://developers.openai.com/api/docs/pricing)、[缓存桶与计费](https://developers.openai.com/api/docs/guides/prompt-caching)、[输出与reasoning cap](https://developers.openai.com/api/docs/guides/reasoning)、[格式token与输入计数](https://developers.openai.com/api/docs/guides/token-counting)。
