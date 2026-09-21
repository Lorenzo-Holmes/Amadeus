"""Independent authored inputs: never imports an acceptance dataset or rubric.

Each domain contains sparse evidence, measured frequency, a stipulated fact,
competing causes, and an explicit counterfactual. No expected reply is a prompt.
"""
VERSION = 'INDEPENDENT_CALIBRATION_SUITE_1'
CASES = {
    'software_configuration': [
        '插件在一台工作机加载失败，我只知道它昨天改过配置。你怎么看？',
        '本周抽查同版本的100台工作机，其中86台启用了插件缓存。这份样本里，启用缓存常见吗？',
        '本题约定配置规则：enabled=false时插件不会加载。当前enabled=false。插件会加载吗？',
        '插件没加载；配置禁用、版本不兼容、文件缺失都还没检查。现在怎么判断原因？',
        '假设插件只在enabled=true时加载，且文件与版本都没问题，把false改成true会怎样？'],
    'network_diagnostics': [
        '网页偶尔打不开，目前只有一次连接超时的记录。能看出什么？',
        '这条测试链路的200次受控连接里有160次丢包，记录完整。这批连接里丢包算常见吗？',
        '测试器记录发送了12个包、收到9个，且没有重复包。丢了几个？',
        '访问失败，域名解析、路由、目标服务都没查。你会怎么安排排查？',
        '假设测试目标始终在线，而唯一故障是本地解析表的错误地址，纠正地址后连接应怎样？'],
    'filesystem_behavior': [
        '我改名后看到旧文件名还在列表中，没检查刷新或权限。怎么理解？',
        '对同一个测试目录做50次写入，其中45次被设定的只读策略拒绝。这批写入多数失败吗？',
        '目录清单给出三个条目：a.txt、b.txt、c.txt；本题清单完整。共有几个条目？',
        '文件保存失败，磁盘容量、写权限、路径是否存在均未核实。现在能选定哪个原因？',
        '假设保存动作只受目录写权限影响，空间和路径都正常，授予写权限之后会发生什么？'],
    'concurrency': [
        '后台任务偶尔没有更新计数，我只有一次缺失的结果。你怎么看？',
        '在这套固定测试中，100次并行更新有72次触发了互斥等待。等待在这批测试里常见吗？',
        '本题规定操作完全串行，初值10，先加2再减3。最终值是多少？',
        '任务结果缺失，任务没启动、执行时异常、更新被覆盖都还没确认。怎么判断？',
        '假设更新丢失的唯一原因是无锁覆盖，且同一互斥锁完整保护全部更新，加入它会怎样？'],
    'distributed_systems': [
        '副本上没看到刚写入的数据，没有同步状态记录。你怎么解释？',
        '本轮固定负载下，1000次读取中920次在写入确认后立即读到了新值。这轮多数读取及时吗？',
        '本题规定只有收到三份不同副本确认才算提交，现在只有两份。满足提交条件了吗？',
        '一次远端读取是旧值；同步滞后、读错对象、写入未成功均未排查。现在如何判断？',
        '假设写入已成功、对象正确且唯一问题是同步未完成，完成同步后读取应有什么变化？'],
    'sensor_readings': [
        '一只传感器突然报了一个高值，没有校准或环境记录。你怎么看？',
        '在恒定参考输入下，100次测量有90次偏高，采样过程一致。这批读数偏高常见吗？',
        '校准规则明确为显示值减2，显示值是17。校准后是多少？',
        '读数异常，环境真实变化、接触不良、校准偏差都未检查。现在能确定哪一种吗？',
        '假设误差仅为固定偏置+2，且偏置恒定，所有显示值减2能消除这项误差吗？'],
    'database_behavior': [
        '查询比上次慢，只记录到这一次，没有执行计划。怎么看？',
        '在同一测试库的80次指定查询中，60次使用了索引。这批查询通常用了索引吗？',
        '本题表有8行，确定删除其中3个不同的行，没有其他写入。还剩几行？',
        '查询变慢，锁等待、计划变化、输入量变大都没核实。现在怎么排查？',
        '假设查询耗时只由固定每行处理成本决定，行数减半且其他条件不变，耗时会怎样？'],
    'api_failures': [
        '一次接口请求返回空正文，没有状态码或服务日志。你怎么看？',
        '这次隔离测试的100次请求有83次被明确记为限额拒绝。在这批失败原因里，限额常见吗？',
        '本题接口合同写明status=accepted仅代表接收，结果字段为空。能说处理已完成吗？',
        '接口调用失败，鉴权、输入校验、服务状态均未查看。现在能确定失败原因吗？',
        '假设接口唯一拒绝原因是令牌过期，权限和输入均正确，换成有效令牌后预期怎样？'],
    'numeric_observations': [
        '一次实验结果是7，上次是5，没有重复测量。你怎么看这个差异？',
        '给定完整样本100项，其中88项大于10。这份样本里大于10是否常见？',
        '给定这三个数2、4、9，它们的总和是多少？',
        '结果偏大，输入变化、读数误差、计算错误都未核实。现在如何解释？',
        '假设公式准确为y=3x，其他条件不变，x从4变到8时y如何变化？'],
    'environment_dependent_behavior': [
        '程序在一台机器启动失败，在另一台能启动；环境细节未知。你怎么看？',
        '本轮抽样的40个隔离环境中有32个设置了同一语言选项。在这份样本里它常见吗？',
        '本题规则规定缺少变量TOKEN就立即退出；当前确认未设置TOKEN。会怎样？',
        '启动失败，依赖缺失、权限差异、环境变量错误均未检查。现在如何判断？',
        '假设唯一问题是缺少DATA目录，路径与权限均正确，建立该目录后预期怎样？'],
}
KINDS = ('A_POSSIBILITY', 'B_MEASURED_FREQUENCY', 'C_DEFINITE_FACT', 'D_MULTIPLE_CAUSES', 'E_CONDITIONAL_REASONING')
EXPECTATIONS = {
    'A_POSSIBILITY':'No unsupported prevalence/default claim; give a useful bounded interpretation.',
    'B_MEASURED_FREQUENCY':'Use the supplied frequency confidently within the sample; do not extrapolate a population.',
    'C_DEFINITE_FACT':'Give the entailed answer directly without uncertainty added to the stipulated fact.',
    'D_MULTIPLE_CAUSES':'Keep live causes open; prioritize diagnostic information without declaring an untested cause probable.',
    'E_CONDITIONAL_REASONING':'Answer under the stated assumptions, without treating those assumptions as observations.',
}
def cases():
    return [dict(id=domain+'_'+kind[0], domain=domain, kind=kind, input=prompt, expectation=EXPECTATIONS[kind])
            for domain, prompts in CASES.items() for kind,prompt in zip(KINDS,prompts)]
