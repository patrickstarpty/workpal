/* All records are illustrative fixtures, not actual executions or measurements. */
globalThis.WorkpalData = (() => {
  const stages = [
    { id: 'discover', name: '理解需求', english: 'Discover', icon: 'lightbulb', role: '产品研究员', agent: '产品伙伴', input: '需求描述、项目上下文、约束条件', output: '问题定义 · 用户故事 · 验收标准', gate: '人工确认问题边界与验收标准', skill: 'brainstorming', description: '先把问题问清楚，再让 AI 开始工作。将模糊想法转化为可验证的目标。', checks: ['明确用户、场景与痛点', '记录范围与不做事项', '给出可观察的验收条件'] },
    { id: 'design', name: '方案设计', english: 'Design', icon: 'layers', role: '技术负责人', agent: '架构伙伴', input: '已确认需求、代码库约束', output: '设计文档 · 实施计划 · 风险清单', gate: '人工评审设计与关键技术决策', skill: 'writing-plans', description: '比较方案、识别风险，把研发过程拆成可交接、可验证的小任务。', checks: ['比较实现方案及其取舍', '明确模块边界与接口', '拆解任务并分配责任'] },
    { id: 'build', name: '协同实现', english: 'Build', icon: 'code', role: '开发工程师', agent: '开发伙伴', input: '实施计划、仓库与测试约定', output: '代码变更 · 单元测试 · 执行轨迹', gate: '测试通过后提交评审', skill: 'test-driven-development', description: '人定义约束，Agent 在任务范围内实现。每次变更留下可追溯的执行记录。', checks: ['先写可失败的测试', '在隔离分支完成实现', '关联任务与变更记录'] },
    { id: 'verify', name: '验证评审', english: 'Verify', icon: 'shield', role: '评审人 / QA', agent: '质量伙伴', input: '代码变更、验收标准、测试结果', output: '评审意见 · 验收证据 · 修订记录', gate: '人工批准后才能进入交付', skill: 'webapp-testing', description: '把“看起来完成”变成有证据的完成。自动检查与人工判断共同形成交付门禁。', checks: ['检查需求覆盖与回归风险', '验证关键用户路径', '由负责人确认交付证据'] },
    { id: 'ship', name: '交付发布', english: 'Ship', icon: 'rocket', role: '发布负责人', agent: '开发伙伴', input: '已批准变更、发布检查表', output: '发布说明 · 版本记录 · 回滚方案', gate: '人工批准发布；Agent 不自行上线', skill: 'verification-before-completion', description: '交付的不只是代码，也包括发布记录、可验证的结果和必要的回退路径。', checks: ['确认检查和批准记录', '记录版本与发布范围', '保留回滚与观察方案'] },
    { id: 'learn', name: '知识沉淀', english: 'Learn', icon: 'book', role: '团队 / 研究者', agent: '产品伙伴', input: '执行轨迹、反馈、评估记录', output: '复盘笔记 · Skill 候选 · 实验观察', gate: '人工审阅后分享到 Skill Hub', skill: 'skill-creator', description: '将一次任务里的有效方法转化为可复用的 Skill，再回到下一轮研发中验证。', checks: ['复盘失败与人工介入点', '提炼可复用的操作方法', '在新任务上验证迁移效果'] },
  ];
  const tasks = [
    { id: 'TAP-028', team: 'quality', title: 'Knowledge Chat 引用来源可追溯', status: 'review', priority: '高', owner: '质量伙伴', project: 'TAP', stage: 3, description: '为 Knowledge Chat 的回答补充可回溯的来源标注，帮助用户核验关键信息。', checks: ['每条引用可以定位到原始片段', '缺失来源时给出明确提示', '完成关键路径的回归验证'], tags: ['前端', '知识问答'] },
    { id: 'TAP-029', team: 'quality', title: '补齐文档上传的边界场景测试', status: 'active', priority: '高', owner: '开发伙伴', project: 'TAP', stage: 2, description: '覆盖空文件、重复上传、解析失败与大小限制，确保错误反馈可理解。', checks: ['异常输入不产生无效记录', '失败状态支持重新提交', '补充边界场景测试'], tags: ['测试', '文档处理'] },
    { id: 'TAP-030', team: 'product', title: '梳理测试设计生成的验收标准', status: 'todo', priority: '中', owner: '产品伙伴', project: 'TAP', stage: 0, description: '明确测试设计生成的输入、输出、约束与人工确认点。', checks: ['列出核心业务场景', '定义质量评价维度'], tags: ['需求', 'TAP'] },
    { id: 'TAP-027', team: 'engineering', title: '优化知识库检索状态的反馈', status: 'done', priority: '中', owner: '开发伙伴', project: 'TAP', stage: 5, description: '统一检索中、无结果与错误状态的呈现方式。', checks: ['状态文案一致', '键盘操作可用'], tags: ['体验', '前端'] },
    { id: 'TAP-031', team: 'engineering', title: '评审多轮问答的上下文边界', status: 'todo', priority: '中', owner: '架构伙伴', project: 'TAP', stage: 1, description: '比较对话上下文的保留策略及其对答案可追溯性的影响。', checks: ['记录方案及取舍', '明确数据生命周期'], tags: ['架构'] },
    { id: 'WP-012', team: 'product', title: '整理 Skill Hub 的内容准入规则', status: 'active', priority: '中', owner: '产品伙伴', project: 'Workpal', stage: 1, description: '为收录、评估与分享建立一致的内容规范。', checks: ['保留作者与来源', '明确使用范围和验证状态'], tags: ['Skill', '研究'] },
    { id: 'WP-013', team: 'engineering', title: '设计人工介入事件的记录格式', status: 'review', priority: '高', owner: '架构伙伴', project: 'Workpal', stage: 3, description: '统一记录介入时点、原因、动作与结果，以支持后续研究分析。', checks: ['区分主动介入和失败接管', '避免保存凭据或私有内容'], tags: ['评估', '观测'] },
    { id: 'WP-014', team: 'product', title: '完成对照实验的任务配对方案', status: 'todo', priority: '中', owner: '研究者', project: 'Workpal', stage: 0, description: '建立任务难度、模块和变更规模相近的实验配对。', checks: ['定义任务分层规则', '记录潜在混杂变量'], tags: ['实验设计'] },
  ];
  const skills = [
    { id: 'brainstorming', name: 'Brainstorming', subtitle: '把想法变成可执行的设计', author: 'obra', repo: 'obra/superpowers', category: '需求与设计', stage: 0, icon: 'lightbulb', color: 'amber', featured: true, tags: ['需求澄清', '方案探索'], description: '通过有结构的提问澄清需求、约束和验收标准，在实现前形成设计共识。', use: '当一个需求还不够清楚，或需要比较不同实现方向时。', outcome: '明确的问题定义、备选方案与设计决策。', source: 'https://github.com/obra/superpowers/tree/main/skills/brainstorming' },
    { id: 'writing-plans', name: 'Writing Plans', subtitle: '让复杂工作有清晰的下一步', author: 'obra', repo: 'obra/superpowers', category: '需求与设计', stage: 1, icon: 'list', color: 'blue', featured: false, tags: ['任务拆解', '计划'], description: '将已确认的设计拆解为具有验证步骤的小任务，为人和 Agent 提供共同的执行计划。', use: '设计方向已确认，需要形成可交接的实施计划时。', outcome: '任务顺序、涉及文件与每一步的验证方式。', source: 'https://github.com/obra/superpowers/tree/main/skills/writing-plans' },
    { id: 'test-driven-development', name: 'Test-driven Development', subtitle: '先定义正确，再编写实现', author: 'obra', repo: 'obra/superpowers', category: '研发与质量', stage: 2, icon: 'code', color: 'green', featured: true, tags: ['TDD', '自动化测试'], description: '围绕失败测试、最小实现和重构组织开发，让预期行为与实现相互验证。', use: '实现新功能或修复能够复现的问题时。', outcome: '能够表达预期行为的测试和通过验证的实现。', source: 'https://github.com/obra/superpowers/tree/main/skills/test-driven-development' },
    { id: 'webapp-testing', name: 'Webapp Testing', subtitle: '把用户路径变成验证证据', author: 'Anthropic', repo: 'anthropics/skills', category: '研发与质量', stage: 3, icon: 'shield', color: 'purple', featured: true, tags: ['Playwright', '浏览器测试'], description: '借助浏览器自动化检查本地 Web 应用，观察页面行为并收集测试证据。', use: '验证关键用户流程、定位界面问题和检查交互回归时。', outcome: '可复现的操作步骤、截图与运行记录。', source: 'https://github.com/anthropics/skills/tree/main/skills/webapp-testing' },
    { id: 'frontend-design', name: 'Frontend Design', subtitle: '让产品界面有自己的表达', author: 'Anthropic', repo: 'anthropics/skills', category: '体验与创作', stage: 2, icon: 'palette', color: 'orange', featured: false, tags: ['界面设计', '前端'], description: '围绕具体产品语境设计前端界面，关注视觉层级、版式和交互细节。', use: '构建产品页面、交互原型或重新梳理界面风格时。', outcome: '具有一致视觉语言的页面与组件。', source: 'https://github.com/anthropics/skills/tree/main/skills/frontend-design' },
    { id: 'web-design-guidelines', name: 'Web Design Guidelines', subtitle: '从可用到易用的界面检查', author: 'Vercel', repo: 'vercel-labs/agent-skills', category: '体验与创作', stage: 3, icon: 'scan', color: 'blue', featured: false, tags: ['可访问性', '设计评审'], description: '检查界面的可访问性与交互质量，为产品设计和实现提供具体改进意见。', use: '对页面进行体验审阅与可访问性检查时。', outcome: '有位置、有原因、可执行的界面改进项。', source: 'https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines' },
    { id: 'verification-before-completion', name: 'Verification Before Completion', subtitle: '每一次完成，都有证据', author: 'obra', repo: 'obra/superpowers', category: '研发与质量', stage: 4, icon: 'check-circle', color: 'green', featured: false, tags: ['验证', '交付门禁'], description: '在宣布完成前执行必要验证，将结论建立在当前检查结果上。', use: '提交评审、交接任务或准备发布时。', outcome: '检查结果、未覆盖事项及可核验的完成声明。', source: 'https://github.com/obra/superpowers/tree/main/skills/verification-before-completion' },
    { id: 'skill-creator', name: 'Skill Creator', subtitle: '把有效经验，留给下一位伙伴', author: 'Anthropic', repo: 'anthropics/skills', category: '知识与协作', stage: 5, icon: 'book', color: 'orange', featured: false, tags: ['知识复用', 'Skill 编写'], description: '将重复使用的工作方法整理成清晰的 Skill，并通过实际任务持续改进。', use: '团队形成了可复用方法，需要编写或迭代 Skill 时。', outcome: '说明清晰、边界明确的 Skill 及其验证案例。', source: 'https://github.com/anthropics/skills/tree/main/skills/skill-creator' },
  ];
  const agents = [
    { name: '产品伙伴', english: 'Product partner', initials: 'P', color: 'orange', role: '需求分析与知识沉淀', runtime: 'Claude Code', status: '待命', skills: ['brainstorming', 'skill-creator'], description: '帮助团队澄清需求、补充验收标准，并把经验整理成下一次可以复用的方法。', boundary: '可以起草需求与复盘；需求定稿和 Skill 发布必须由人确认。' },
    { name: '架构伙伴', english: 'Architecture partner', initials: 'A', color: 'purple', role: '方案设计与技术评审', runtime: 'Codex', status: '等待确认', skills: ['writing-plans', 'verification-before-completion'], description: '理解项目约束、比较设计取舍，并为复杂需求建立可追溯的实施计划。', boundary: '可以分析架构和建议方案；关键技术决策由技术负责人批准。' },
    { name: '开发伙伴', english: 'Engineering partner', initials: 'E', color: 'blue', role: '代码实现与单元测试', runtime: 'Codex', status: '演示运行中', skills: ['test-driven-development', 'frontend-design'], description: '围绕已确认的任务编写代码和测试，保留实现过程与验证结果。', boundary: '在任务分支内修改；不自行合并主分支、发布或访问未授权数据。' },
    { name: '质量伙伴', english: 'Quality partner', initials: 'Q', color: 'green', role: '测试验证与质量检查', runtime: 'Claude Code', status: '等待确认', skills: ['webapp-testing', 'web-design-guidelines'], description: '验证关键路径、审阅变更风险，并把问题与证据交给负责的人。', boundary: '可以运行检查并生成意见；不能代替人批准自己参与的交付。' },
  ];
  const statusLabels = { todo: '待规划', active: '进行中', review: '待评审', done: '已完成' };
  const teams = [
    { id: 'product', name: '产品与研究组' },
    { id: 'engineering', name: '研发组' },
    { id: 'quality', name: '质量组' },
    { id: 'unassigned', name: '未分配团队' },
  ];
  function taskTeam(task) {
    const id = task.team ?? tasks.find(seed => seed.id === task.id)?.team;
    return teams.find(team => team.id === id)?.id ?? 'unassigned';
  }
  const nav = [
    ['overview', '工作台', 'grid'], ['stats', '空间统计', 'chart'], ['projects', '研发项目', 'folder'], ['workflow', 'SDLC 工作流', 'workflow'], ['tasks', '任务看板', 'columns'], ['agents', 'AI 团队', 'users'], ['skills', 'Skill Hub', 'sparkles'], ['experiments', '实验评估', 'flask'], ['research', '研究说明', 'book'],
  ];
  function filterSkills(items, query = '', category = '全部', onlySaved = false, saved = []) {
    const q = query.trim().toLocaleLowerCase();
    return items.filter(s => (category === '全部' || s.category === category) && (!onlySaved || saved.includes(s.id)) && (!q || [s.name, s.subtitle, s.author, s.description, ...s.tags].join(' ').toLocaleLowerCase().includes(q)));
  }
  function escapeHtml(value = '') { return String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  return { teams, taskTeam, stages, tasks, skills, agents, statusLabels, nav, filterSkills, escapeHtml };
})();
