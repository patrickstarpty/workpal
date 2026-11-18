(() => {
  'use strict';
  const D = globalThis.WorkpalData;
  const e = D.escapeHtml;
  const $ = (selector, root = document) => root.querySelector(selector);
  const STORAGE_KEY = 'workpal.prototype.v1';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}; } catch { /* Private browsing can disable storage. */ }
  const state = {
    tasks: Array.isArray(saved.tasks) ? saved.tasks.filter(t => t && typeof t.id === 'string' && typeof t.title === 'string' && typeof t.owner === 'string' && typeof t.description === 'string' && typeof t.priority === 'string' && ['TAP', 'Workpal'].includes(t.project) && D.statusLabels[t.status] && Array.isArray(t.checks) && t.checks.every(c => typeof c === 'string') && Array.isArray(t.tags) && t.tags.every(c => typeof c === 'string')) : structuredClone(D.tasks),
    bookmarks: Array.isArray(saved.bookmarks) ? saved.bookmarks.filter(id => D.skills.some(s => s.id === id)) : ['brainstorming', 'webapp-testing'],
    notes: Array.isArray(saved.notes) ? saved.notes.filter(n => n && typeof n.text === 'string' && typeof n.page === 'string') : [],
    project: '全部项目', taskQuery: '', skillQuery: '', category: '全部', onlySaved: false,
    stage: 3, runStage: 3, running: false, flowComplete: false, selectedExperiment: 'E01', mobileNav: false, tour: false,
  };
  let toastTimer;
  let lastFocus;
  const icons = {
    chart: '<path d="M3 3v18h18M7 16V9m5 7V5m5 11v-5"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    folder: '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    workflow: '<rect x="3" y="3" width="6" height="6" rx="1.5"/><rect x="15" y="15" width="6" height="6" rx="1.5"/><path d="M6 9v6a3 3 0 0 0 3 3h6M9 6h6a3 3 0 0 1 3 3v6"/>',
    columns: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18M15 3v18M5.5 7h1M11.5 7h1M17.5 7h1"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 4v2"/>',
    sparkles: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4M18 4h4"/>',
    flask: '<path d="M9 3h6M10 3v6l-6 10a1.4 1.4 0 0 0 1 2h14a1.4 1.4 0 0 0 1-2L14 9V3M7 15h10"/>',
    book: '<path d="M12 5v16M12 5C9 3 5 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 1Z"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    bell: '<path d="M6 9a6 6 0 0 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9M10 21h4"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    arrowup: '<path d="M6 18 18 6M6 6h12v12"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    play: '<path d="m8 4 13 8-13 8Z"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    'check-circle': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    code: '<path d="m7 6-6 6 6 6M17 6l6 6-6 6M14 3l-4 18"/>',
    shield: '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6ZM8 12l3 3 5-6"/>',
    lightbulb: '<path d="M9 18h6M10 22h4M8 15a7 7 0 1 1 8 0l-1 3H9Z"/>',
    layers: '<path d="m12 3 10 5-10 5L2 8ZM2 12l10 5 10-5M2 16l10 5 10-5"/>',
    rocket: '<path d="M14 4c3-2 7-2 7-2s0 4-2 7l-7 7-4-4ZM8 12H3l4-6h5M12 16v5l6-4v-5M7 17l-4 4M16 7h.01"/>',
    list: '<path d="M9 6h12M9 12h12M9 18h12M3 6h.01M3 12h.01M3 18h.01"/>',
    palette: '<path d="M12 3a9 9 0 1 0 0 18c3 0 1-4 4-4h2c5 0 4-14-6-14Z"/><path d="M7 8h.01M12 6h.01M17 9h.01M6 13h.01"/>',
    scan: '<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5M7 12h10M12 7v10"/>',
    bookmark: '<path d="M6 3h12v18l-6-4-6 4Z"/>',
    share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.5 10.5 7-4M8.5 13.5l7 4"/>',
    copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M3 16v5h18v-5"/>',
    settings: '<path d="m10 3-1 3-3 1-3 3 2 2-2 2 3 3 3 1 1 3h4l1-3 3-1 3-3-2-2 2-2-3-3-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
    message: '<path d="M21 15a3 3 0 0 1-3 3H9l-6 4V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3Z"/>',
    menu: '<path d="M3 6h18M3 12h18M3 18h18"/>',
    monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M12 17v4M7 21h10"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  };
  const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.sparkles}</svg>`;
  const badge = (text, tone = 'neutral') => `<span class="badge ${tone}">${e(text)}</span>`;
  const link = (href, text, cls = 'btn secondary') => `<a class="${cls}" href="#${href}">${text}</a>`;
  const button = (action, text, cls = 'btn secondary', extra = '') => `<button type="button" class="${cls}" data-action="${action}" ${extra}>${text}</button>`;
  const avatar = (name, color = 'orange', size = '') => `<span class="avatar ${color} ${size}">${e(name.slice(0, 1))}</span>`;
  const route = () => {
    const [page = 'overview', params = ''] = location.hash.slice(1).split('?');
    return { page: D.nav.some(n => n[0] === page) || page === 'settings' ? page : 'overview', params: new URLSearchParams(params) };
  };
  const go = (page) => { location.hash = page; };
  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ tasks: state.tasks, bookmarks: state.bookmarks, notes: state.notes })); }
    catch { toast('浏览器未允许保存；本次操作仍在当前页面有效。'); }
  }
  function toast(message) {
    const el = $('#toast'); el.textContent = message; el.classList.add('visible');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 3500);
  }
  function modal(title, body, wide = false) {
    const dialog = $('#dialog');
    if (!dialog.open) lastFocus = document.activeElement;
    dialog.className = wide ? 'wide' : '';
    dialog.innerHTML = `<div class="modal-head"><h2 id="dialog-title">${title}</h2>${button('close-modal', icon('close'), 'icon-btn', 'aria-label="关闭对话框"')}</div><div class="modal-body">${body}</div>`;
    if (!dialog.open) dialog.showModal();
  }
  function closeModal() { $('#dialog').close(); if (lastFocus?.isConnected) lastFocus.focus(); }
  function pageHead(eyebrow, title, description, actions = '') {
    return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div><div class="heading-actions">${actions}</div></div>`;
  }
  function panelHead(title, subtitle = '', action = '') { return `<div class="panel-heading"><div><h2>${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}</div>${action}</div>`; }
  function render() {
    const { page, params } = route();
    const title = D.nav.find(n => n[0] === page)?.[1] || '原型设置';
    document.title = `${title} · Workpal`;
    const pages = { overview, stats, projects, workflow, tasks, agents, skills, experiments, research, settings };
    $('#app').innerHTML = `<div class="app-shell ${state.mobileNav ? 'nav-open' : ''}">
      <aside class="sidebar" aria-label="主导航">
        <a class="brand" href="#overview" aria-label="Workpal 工作台"><span class="brand-mark">w<span>·</span></span><span>Workpal<span class="brand-dot">.</span></span></a>
        <div class="workspace-card"><span class="workspace-icon">W</span><div><strong>Workpal Lab</strong><small>AI 原生研发研究空间</small></div>${icon('down')}</div>
        <div class="nav-label">WORKSPACE</div><nav>${D.nav.map(([id, name, glyph]) => `${id === 'experiments' ? '<div class="nav-label research-label">RESEARCH</div>' : ''}<a href="#${id}" class="nav-item ${page === id ? 'active' : ''}" ${page === id ? 'aria-current="page"' : ''}>${icon(glyph)}<span>${name}</span>${id === 'skills' ? '<span class="nav-new">精选</span>' : id === 'tasks' ? `<span class="nav-count">${state.tasks.filter(t => t.status !== 'done').length}</span>` : ''}</a>`).join('')}</nav>
        <div class="sidebar-bottom"><div class="research-card"><span class="dot orange-dot"></span>让研发过程，成为研究对象<p>从一次协作，到可复用的方法。</p>${link('research', '了解研究设计 ' + icon('arrow'), 'text-link')}</div>${button('review', icon('message') + '留下审阅意见', 'sidebar-review')}<a href="#settings" class="nav-item ${page === 'settings' ? 'active' : ''}">${icon('settings')}原型设置</a><div class="profile">${avatar('P', 'neutral')}<div><strong>Patrick</strong><small>研究者 · 空间管理员</small></div><span class="dot green-dot"></span></div></div>
      </aside>
      <div class="main-shell"><header class="topbar"><div class="breadcrumbs">${button('mobile-nav', icon('menu'), 'icon-btn mobile-menu', 'aria-label="切换导航"')}<span>Workpal Lab</span>${icon('chevron')}<strong>${title}</strong></div><div class="top-actions"><span class="prototype-label"><span class="dot orange-dot"></span>交互原型 · 示例数据</span>${button('search', icon('search') + '<span>搜索</span><kbd>⌘ K</kbd>', 'search-trigger')}${button('notifications', icon('bell'), 'icon-btn notification-btn', 'aria-label="查看演示通知"')}${avatar('P', 'neutral', 'small')}</div></header>
      <main id="main" tabindex="-1">${state.tour ? tourBar(page) : ''}${pages[page]()}</main><footer class="page-footer"><span>Workpal · Make work a shared journey.</span><span>研究原型 v0.1 <span class="footer-dot">·</span> ${button('review', '审阅反馈', 'text-link')}</span></footer></div>
    </div>`;
    if (page === 'skills' && params.has('id')) {
      const skill = D.skills.find(s => s.id === params.get('id'));
      if (skill) skillDetail(skill.id);
      else toast('未找到这个 Skill，可以在目录中继续查找。');
    }
  }
  function tourBar(page) {
    const steps = ['research', 'overview', 'workflow', 'skills', 'experiments'];
    const index = steps.indexOf(page);
    return `<div class="tour-bar"><span>${icon('play')} 审阅导览 <strong>${index >= 0 ? index + 1 : '—'} / 5</strong></span><span class="tour-caption">研究设想 → 产品场景 → 协作流程 → 知识复用 → 实验设计</span><div>${link(steps[(index + 1) % steps.length], index === 4 ? '回到研究说明' : '下一站 ' + icon('arrow'), 'btn small secondary')}${button('end-tour', icon('close'), 'icon-btn', 'aria-label="退出导览"')}</div></div>`;
  }
  function overview() {
    const done = state.tasks.filter(t => t.status === 'done').length;
    const review = state.tasks.filter(t => t.status === 'review');
    return `${pageHead('YOUR HUMAN + AI WORKSPACE', '好的协作，让想法更进一步。', '从需求到交付，与 AI 伙伴一起，把每次研发变成可沉淀的经验。', button('start-tour', icon('play') + '审阅导览', 'btn secondary') + button('new-task', icon('plus') + '创建任务', 'btn primary'))}
      <div class="overview-hero"><div class="hero-copy"><span class="hero-label"><span class="dot"></span> WORKPAL RESEARCH LAB</span><h2>人负责方向，<br>AI 参与过程。</h2><p>一个研究 AI 原生软件研发的协作空间。<br>在真实项目中探索协作方式，在共享 Skill 中积累团队经验。</p><div>${link('workflow', '探索研发工作流 ' + icon('arrow'), 'btn ink')}${link('research', '查看研究说明', 'hero-text-link')}</div></div><div class="hero-diagram" aria-label="需求、实现、验证、沉淀组成协作闭环"><div class="orbit orbit-outer"></div><div class="orbit orbit-inner"></div><div class="orbit-center"><span class="hero-w">w<span>·</span></span><small>WORK TOGETHER</small></div><span class="orbit-node node-top">${icon('lightbulb')} 理解需求</span><span class="orbit-node node-right">${icon('code')} 协同实现</span><span class="orbit-node node-bottom">${icon('shield')} 人工验证</span><span class="orbit-node node-left">${icon('book')} 知识沉淀</span><span class="orbit-spark spark-one">+</span><span class="orbit-spark spark-two">+</span></div></div>
      <div class="stats-grid"><div class="stat-card"><span>进行中的项目 ${icon('folder')}</span><strong>2<small>个研究场景</small></strong><p>TAP 产品研发 · Workpal 平台研究</p></div><div class="stat-card"><span>任务进展 ${icon('columns')}</span><strong>${done}<small>/ ${state.tasks.length} 已完成</small></strong><div class="progress"><i style="width:${done / state.tasks.length * 100}%"></i></div></div><div class="stat-card"><span>等待你的判断 ${icon('shield')}</span><strong>${review.length}<small>个人工评审点</small></strong><p>让关键决策始终由人掌握</p></div><div class="stat-card"><span>共享 Skill 目录 ${icon('sparkles')}</span><strong>${D.skills.length}<small>个精选条目</small></strong><p>覆盖需求、开发、验证与知识沉淀</p></div></div>
      <div class="two-col overview-columns"><section class="panel">${panelHead('继续推进你的项目', 'TAP / Knowledge Chat', link('projects', '全部项目 ' + icon('arrow'), 'text-link'))}<div class="project-focus"><div class="project-identity"><span class="project-logo">T</span><div><h3>让知识问答的每个答案都有据可查</h3><p>TAP · 引用来源可追溯</p></div>${badge('待人工评审', 'amber')}</div><div class="mini-pipeline">${D.stages.map((s, i) => `<a href="#workflow" class="${(i < state.runStage || state.flowComplete) ? 'complete' : i === state.runStage ? 'current' : ''}"><span>${(i < state.runStage || state.flowComplete) ? icon('check') : String(i + 1).padStart(2, '0')}</span>${s.name}</a>`).join('')}</div><div class="project-bottom"><span>${avatar('质', 'green', 'tiny')} 质量伙伴已整理验收材料 <span class="muted">· 演示场景</span></span>${link('workflow', '查看流程 ' + icon('arrow'), 'text-link')}</div></div><div class="section-divider"></div><div class="subsection-title"><h3>需要你的关注</h3><span>${review.length} 个任务</span></div>${review.map(t => `<button class="attention-row" data-action="task" data-id="${e(t.id)}"><span class="attention-icon">${icon('shield')}</span><div><strong>${e(t.title)}</strong><small>${e(t.id)} · ${e(t.owner)} · 请确认验收证据</small></div>${icon('arrow')}</button>`).join('') || '<p class="empty-inline">所有评审已处理，可以继续推进任务。</p>'}</section>
      <section class="panel activity-panel">${panelHead('协作动态', '一条可追溯的人机协作轨迹', badge('示例'))}<div class="timeline">${[['green', '质量伙伴', '已提交引用来源的验收记录', '等待 Patrick 确认', '刚刚'], ['blue', '开发伙伴', '开始补齐文档上传边界测试', 'TAP-029 · 协同实现', '12 分钟前'], ['orange', 'Patrick', '确认 Knowledge Chat 的设计范围', '人工决策 · 方案设计', '35 分钟前'], ['purple', '架构伙伴', '整理了两种上下文保留方案', '附带方案取舍与待确认问题', '1 小时前']].map(([c, n, title, sub, time]) => `<div class="timeline-item">${avatar(n, c, 'small')}<div><div class="timeline-name">${n}<time>${time}</time></div><p>${title}</p><small>${sub}</small></div></div>`).join('')}</div>${button('activity', '查看完整示例轨迹 ' + icon('arrow'), 'btn secondary full')}</section></div>
      <section class="recommendations">${panelHead('从一个好用的 Skill 开始', '把个人经验，变成团队共同的方法。', link('skills', '探索 Skill Hub ' + icon('arrow'), 'text-link'))}<div class="skill-mini-grid">${D.skills.filter(s => s.featured).map(s => `<button class="skill-mini" data-action="skill" data-id="${s.id}"><span class="skill-icon ${s.color}">${icon(s.icon)}</span><div><h3>${s.name}</h3><p>${s.subtitle}</p><small>${s.author} <span>·</span> ${s.category}</small></div>${icon('arrowup')}</button>`).join('')}</div></section>`;
  }
  function projects() {
    return `${pageHead('PROJECTS', '把研究，放进真实的项目。', '以 TAP 为应用场景，以 Workpal 自身迭代为方法试验场。', button('project-guide', icon('plus') + '新建项目', 'btn primary'))}<div class="project-grid">${[['TAP', 'T', '产品研发场景', '围绕知识问答、文档处理和测试设计，观察 AI 参与真实研发任务的协作过程。', 'orange'], ['Workpal', 'W', '研究平台场景', '设计工作流、积累可复用 Skill，建立人机协作的观测与评估方法。', 'green']].map(([name, mark, label, desc, color]) => { const ts = state.tasks.filter(t => t.project === name); return `<article class="panel project-card"><div class="project-card-top"><span class="project-logo ${color}">${mark}</span>${badge('研究中', 'green')}</div><div class="eyebrow">${label}</div><h2>${name}</h2><p>${desc}</p><div class="project-meta"><span>${icon('columns')} ${ts.length} 个任务</span><span>${icon('users')} 人 + 4 位 AI 伙伴</span></div><div class="section-divider"></div><div class="project-stage"><span>当前关注</span><strong>${name === 'TAP' ? '需求到交付的可追溯协作' : '人工介入与 Skill 复用'}</strong></div><div class="project-card-footer">${button('project-tasks', '进入任务看板 ' + icon('arrow'), 'btn secondary', `data-project="${name}"`)}${button('project-detail', '项目说明', 'text-link', `data-project="${name}"`)}</div></article>`; }).join('')}</div><section class="panel project-research">${panelHead('同一套流程，两种观察视角', '项目完成不是唯一目标，协作过程本身也是研究材料。')}<div class="three-col"><div class="principle">${icon('target')}<h3>任务有明确边界</h3><p>记录输入、验收标准和完成证据，避免仅凭“是否生成代码”判断成功。</p></div><div class="principle">${icon('users')}<h3>人机职责可区分</h3><p>记录 AI 的执行步骤与人的决策时点，观察哪些环节需要协作和接管。</p></div><div class="principle">${icon('book')}<h3>经验能够再利用</h3><p>将有效方法整理为 Skill，在新任务里检验它是否真的具有迁移价值。</p></div></div></section>`;
  }
  function workflow() {
    const stage = D.stages[state.stage];
    return `${pageHead('AI NATIVE SDLC', '让每一步，都有明确的交接。', '需求 → 设计 → 实现 → 验证 → 交付 → 沉淀，人始终在关键决策环节。', button('reset-flow', icon('workflow') + '重置演示', 'btn secondary') + button('advance-flow', icon('play') + (state.flowComplete ? '重新演示' : state.running ? '继续演示' : '演示工作流'), 'btn primary'))}<div class="context-strip"><span><span class="project-logo tiny">T</span><strong>TAP-028</strong> Knowledge Chat 引用来源可追溯</span>${badge('模拟流程 · 不执行真实任务', 'amber')}</div><section class="workflow-map" aria-label="研发阶段选择">${D.stages.map((s, i) => `<button class="flow-node ${state.stage === i ? 'selected' : ''} ${(i < state.runStage || state.flowComplete) ? 'completed' : ''}" data-action="stage" data-stage="${i}" aria-pressed="${state.stage === i}"><div class="flow-node-top"><span class="flow-number">0${i + 1}</span>${(i < state.runStage || state.flowComplete) ? icon('check-circle') : icon(s.icon)}</div><strong>${s.name}</strong><span>${s.english}</span><small>${(i < state.runStage || state.flowComplete) ? '已交接' : i === state.runStage ? '当前阶段' : '待推进'}</small></button>`).join('')}</section><div class="loop-caption">${icon('workflow')} 知识沉淀回到下一轮需求，让协作形成持续学习的闭环。</div><div class="two-col workflow-columns"><section class="panel stage-detail">${panelHead(`<span class="stage-title-icon">${icon(stage.icon)}</span>${stage.name}`, stage.description, badge(`STAGE 0${state.stage + 1}`))}<div class="handoff-grid"><div><span class="field-label">输入</span><p>${stage.input}</p></div><div>${icon('arrow')}</div><div><span class="field-label">交付物</span><p>${stage.output}</p></div></div><div class="owner-strip"><div><span class="field-label">AI 执行伙伴</span><strong>${avatar(stage.agent, 'green', 'tiny')}${stage.agent}</strong></div><div><span class="field-label">人工责任角色</span><strong>${icon('users')}${stage.role}</strong></div></div><h3 class="section-title">阶段检查表</h3><ul class="checklist">${stage.checks.map((c, i) => `<li><span class="check-box ${state.stage < state.runStage || state.flowComplete || state.stage === state.runStage && i < 2 ? 'checked' : ''}">${state.stage < state.runStage || state.flowComplete || state.stage === state.runStage && i < 2 ? icon('check') : ''}</span>${c}</li>`).join('')}</ul><div class="gate"><span>${icon('shield')}</span><div><strong>人工确认点</strong><p>${stage.gate}</p></div>${state.stage === state.runStage && !state.flowComplete ? button('approve-stage', '确认并交接 ' + icon('arrow'), 'btn primary small') : badge(state.stage < state.runStage || state.flowComplete ? '已确认' : '等待上游', state.stage < state.runStage || state.flowComplete ? 'green' : 'neutral')}</div></section><aside><section class="panel">${panelHead('本阶段的 Skill', '让方法成为可调用的协作能力')}<button class="linked-skill" data-action="skill" data-id="${stage.skill}"><span class="skill-icon orange">${icon('sparkles')}</span><div><strong>${D.skills.find(s => s.id === stage.skill)?.name}</strong><small>查看用途与来源</small></div>${icon('arrowup')}</button></section><section class="panel trace-panel">${panelHead('交接记录', '示例执行证据')}<ol class="trace-list"><li><span class="dot green-dot"></span><div><strong>上游交付物已关联</strong><small>设计说明 · 实施计划 · 任务上下文</small></div></li><li><span class="dot green-dot"></span><div><strong>Agent 提交阶段材料</strong><small>执行摘要 · 变更记录 · 验证结果</small></div></li><li><span class="dot orange-dot"></span><div><strong>等待人工确认</strong><small>记录批准、驳回或补充要求</small></div></li></ol>${button('artifacts', icon('folder') + '查看示例交付物', 'btn secondary full')}</section></aside></div>`;
  }
  function teamField(selected) {
    const options = D.teams.map(team =>
      `<option value="${team.id}" ${team.id === selected ? 'selected' : ''}>${team.name}</option>`);
    return `<label>所属团队<select name="team">${options.join('')}</select></label>`;
  }

  function stats() {
    const selected = D.teams.find(team => team.id === route().params.get('team'));
    const groups = D.teams.map(team => ({
      ...team, items: state.tasks.filter(task => D.taskTeam(task) === team.id),
    }));
    const items = selected ? groups.find(group => group.id === selected.id).items : state.tasks;
    const statuses = Object.entries(D.statusLabels);
    const count = (list, key) => list.filter(task => task.status === key).length;
    const metrics = [
      ['任务总数', items.length, '全部状态', 'columns'],
      ['进行中', count(items, 'active'), '正在执行的任务', 'workflow'],
      ['待评审', count(items, 'review'), '等待人工确认', 'shield'],
      ['已完成', count(items, 'done'), '已标记完成的任务', 'check-circle'],
    ];
    const header = pageHead('WORKSPACE ACTIVITY', selected?.name ?? '空间统计',
      selected ? '查看团队负责的任务、执行伙伴和当前进展。' : '按负责团队查看当前任务分布，定位等待评审的工作。',
      selected ? link('stats', '返回空间统计', 'btn secondary') : '');
    const cards = metrics.map(([name, value, hint, glyph]) =>
      `<div class="stat-card"><span>${name}${icon(glyph)}</span><strong>${value}</strong><p>${hint}</p></div>`).join('');
    const legend = statuses.map(([key, label]) =>
      `<span><i class="dist-color dist-${key}"></i>${label}</span>`).join('');
    const visibleGroups = groups.filter(group => group.id !== 'unassigned' || group.items.length || selected?.id === group.id);
    const largest = Math.max(1, ...visibleGroups.map(group => group.items.length));
    const rows = visibleGroups.map(group => {
      const values = statuses.map(([key]) => count(group.items, key));
      const segments = statuses.map(([key], index) =>
        `<i class="dist-${key}" style="width:${100 * values[index] / largest}%"></i>`).join('');
      return `<tr ${group.id === selected?.id ? 'class="stats-current"' : ''}>
        <th scope="row">${link('stats?team=' + group.id, group.name + ' ' + icon('chevron'), 'text-link')}</th>
        <td><div class="dist-track" aria-hidden="true">${segments}</div></td>
        ${values.map(value => `<td>${value}</td>`).join('')}<td><strong>${group.items.length}</strong></td></tr>`;
    }).join('');
    const comparison = `<section class="panel stats-comparison">${panelHead('团队工作分布', '每项任务只计入一个负责团队。点击团队名称查看明细。')}
      <div class="dist-legend">${legend}</div><div class="table-scroll"><table><thead><tr><th>负责团队</th><th>任务量</th>
      ${statuses.map(([, label]) => `<th>${label}</th>`).join('')}<th>合计</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
    const detail = selected ? items : items.filter(task => task.status === 'review');
    const list = detail.map(task => `<button class="attention-row" data-action="task" data-id="${e(task.id)}">
      ${icon('columns')}<div><strong>${e(task.title)}</strong><small>${e(task.id)} · ${e(task.project)} · ${e(task.owner)}</small></div>
      ${badge(D.statusLabels[task.status], task.status === 'review' ? 'amber' : 'neutral')}${icon('chevron')}</button>`).join('');
    const detailPanel = `<section class="panel">${panelHead(selected ? '团队任务' : '待评审任务', '', badge(detail.length + ' 项'))}
      ${list || '<p class="empty-inline">当前没有符合条件的任务。</p>'}</section>`;
    return `${header}<div class="stats-grid">${cards}</div>${selected ? detailPanel + comparison : comparison + detailPanel}`;
  }

  function tasks() {
    const filtered = state.tasks.filter(t => (state.project === '全部项目' || t.project === state.project) && `${t.id} ${t.title} ${t.owner}`.toLowerCase().includes(state.taskQuery.trim().toLowerCase()));
    return `${pageHead('TASK BOARD', '让人与 AI，在同一块看板上协作。', '任务是协作的基本单元。每个任务都有责任人、上下文与验收标准。', button('new-task', icon('plus') + '创建任务', 'btn primary'))}<div class="toolbar"><div class="toolbar-group"><label class="select-wrap">${icon('folder')}<select id="project-filter" aria-label="按项目筛选">${['全部项目', 'TAP', 'Workpal'].map(p => `<option ${state.project === p ? 'selected' : ''}>${p}</option>`).join('')}</select></label><label class="search-field compact">${icon('search')}<input id="task-search" placeholder="搜索任务或伙伴…" value="${e(state.taskQuery)}" aria-label="搜索任务"/></label></div><span class="muted"><span id="task-count">${filtered.length}</span> 个任务 <span class="separator">/</span> ${badge('本地演示')}</span></div><div id="task-board" class="kanban">${taskColumns(filtered)}</div><div class="hint-line">${icon('message')} 点击任务可查看上下文、修改状态与责任人；原型改动仅保存在当前浏览器。</div>`;
  }
  function taskColumns(items) {
    return Object.entries(D.statusLabels).map(([status, label]) => `<section class="kanban-column"><div class="kanban-head"><span class="status-dot ${status}"></span><h2>${label}</h2><span class="count">${items.filter(t => t.status === status).length}</span>${button('new-task', icon('plus'), 'icon-btn', `data-status="${status}" aria-label="在${label}中创建任务"`)}</div><div class="kanban-cards">${items.filter(t => t.status === status).map(t => `<button class="task-card" data-action="task" data-id="${e(t.id)}"><div class="task-top"><span>${e(t.id)}</span><span class="priority ${t.priority === '高' ? 'high' : ''}">${t.priority === '高' ? '↑' : '−'} ${e(t.priority)}优先级</span></div><h3>${e(t.title)}</h3><div class="tags">${t.tags.map(x => badge(x)).join('')}</div><div class="task-card-footer"><span>${avatar(t.owner, t.owner === '质量伙伴' ? 'green' : 'blue', 'tiny')}${e(t.owner)}</span><span>${icon('list')} ${t.checks.length}</span></div></button>`).join('') || '<div class="column-empty">暂时没有任务<br><small>清晰的边界，是协作的开始。</small></div>'}</div></section>`).join('');
  }
  function agents() {
    return `${pageHead('YOUR AI TEAM', '各有所长，一起把工作做好。', '以角色组织 AI 伙伴，以任务定义边界，以人工确认保持方向。', button('agent-config', icon('plus') + '配置 AI 伙伴', 'btn primary'))}<div class="team-banner"><div class="avatar-stack">${D.agents.map(a => avatar(a.initials, a.color)).join('')}</div><div><strong>4 位 AI 伙伴，与你组成一个研发团队</strong><p>角色、Skill 与运行环境相互独立，可按任务组合。</p></div>${badge('运行状态为演示', 'amber')}</div><div class="agent-grid">${D.agents.map((a, i) => `<article class="panel agent-card"><div class="agent-top">${avatar(a.initials, a.color, 'large')}${badge(a.status, a.status === '待命' ? 'neutral' : a.status === '演示运行中' ? 'green' : 'amber')}</div><h2>${a.name}</h2><span class="agent-english">${a.english}</span><p>${a.description}</p><div class="agent-role">${icon('target')}${a.role}</div><div class="agent-skills">${a.skills.map(id => `<button data-action="skill" data-id="${id}" class="skill-chip">${icon('sparkles')}${D.skills.find(s => s.id === id)?.name}</button>`).join('')}</div><div class="agent-footer"><span>${icon('monitor')} ${a.runtime}</span>${button('agent', '查看职责 ' + icon('arrow'), 'text-link', `data-index="${i}"`)}</div></article>`).join('')}</div><section class="panel runtime-panel">${panelHead('运行环境', '展示未来的连接关系，本原型未连接本地 CLI 或模型服务。')}<div class="runtime-row"><span class="runtime-icon">${icon('monitor')}</span><div><strong>本地开发环境</strong><small>Codex CLI / Claude Code · 按角色选择执行工具</small></div>${badge('未连接')}${button('runtime', '连接说明 ' + icon('arrow'), 'btn secondary small')}</div><div class="runtime-row"><span class="runtime-icon">${icon('shield')}</span><div><strong>执行权限与人工门禁</strong><small>任务范围内执行 · 合并、发布与共享需人工确认</small></div>${badge('设计约定', 'green')}${link('workflow', '查看工作流 ' + icon('arrow'), 'btn secondary small')}</div></section>`;
  }
  function skills() {
    const items = D.filterSkills(D.skills, state.skillQuery, state.category, state.onlySaved, state.bookmarks);
    return `${pageHead('SKILL HUB', '好方法，值得被更多人用到。', '发现、理解与分享实用的 Agent Skill，让个人经验成为团队的共同能力。', button('submit-skill', icon('plus') + '推荐 Skill', 'btn primary'))}<section class="skill-hero"><div><span class="eyebrow">CURATED FOR BUILDERS</span><h2>从灵感到交付，<br>找到你的下一块能力拼图。</h2><p>围绕软件研发精选社区方法，为同事与同学提供一个共同的学习入口。</p><div class="hero-tags"><span>${icon('check-circle')} 保留作者与来源</span><span>${icon('layers')} 按场景发现</span><span>${icon('share')} 一键分享</span></div></div><div class="skill-art" aria-hidden="true"><div class="skill-art-tile art-back">${icon('code')}</div><div class="skill-art-tile art-front">${icon('sparkles')}<span>SKILL</span></div><span class="art-plus">+</span><span class="art-caption">Build once.<br>Learn together.</span></div></section><div class="skill-toolbar"><label class="search-field">${icon('search')}<input id="skill-search" placeholder="搜索 Skill、使用场景或作者…" aria-label="搜索 Skill" value="${e(state.skillQuery)}"/><kbd>/</kbd></label>${button('toggle-saved', icon('bookmark') + `我的收藏 <span class="count">${state.bookmarks.length}</span>`, `btn ${state.onlySaved ? 'selected' : 'secondary'}`, `aria-pressed="${state.onlySaved}"`)}</div><div class="filter-bar"><div class="category-tabs" role="group" aria-label="Skill 分类">${['全部', '需求与设计', '研发与质量', '体验与创作', '知识与协作'].map(c => button('category', c, `category-tab ${state.category === c ? 'active' : ''}`, `data-category="${c}" aria-pressed="${state.category === c}"`)).join('')}</div><span id="skill-count" class="muted">${items.length} 个 Skill · 编辑精选</span></div><div class="skill-grid" id="skill-grid">${skillCards(items)}</div><div class="catalog-note">${icon('book')} 目录为人工精选示例，不代表热度排名或效果认证。使用前请阅读上游说明与许可。</div>`;
  }
  function skillCards(items) {
    return items.length ? items.map(s => `<article class="skill-card"><div class="skill-card-top"><span class="skill-icon ${s.color}">${icon(s.icon)}</span>${s.featured ? badge('编辑精选', 'orange') : badge(s.category)}${button('bookmark', icon('bookmark'), `icon-btn bookmark-btn ${state.bookmarks.includes(s.id) ? 'is-saved' : ''}`, `data-id="${s.id}" aria-label="${state.bookmarks.includes(s.id) ? '取消收藏' : '收藏'} ${s.name}" aria-pressed="${state.bookmarks.includes(s.id)}"`)}</div><button class="skill-title" data-action="skill" data-id="${s.id}"><h2>${s.name}</h2><span>${s.subtitle}</span></button><p>${s.description}</p><div class="tags">${s.tags.map(t => badge(t)).join('')}</div><div class="skill-card-footer"><span><span class="author-avatar">${s.author.slice(0, 1).toUpperCase()}</span>${s.author}</span>${button('skill', '查看详情 ' + icon('arrowup'), 'text-link', `data-id="${s.id}"`)}</div></article>`).join('') : `<div class="empty-state">${icon('search')}<h2>还没有找到合适的 Skill</h2><p>试试其他关键词，或取消当前筛选。</p>${button('reset-skills', '重置筛选', 'btn secondary')}</div>`;
  }
  function experiments() {
    const skillExp = state.selectedExperiment === 'E02';
    const groups = skillExp ? [['基础流程', 48, 12, 4], ['流程 + Skill', 36, 8, 2], ['流程 + 迭代 Skill', 32, 7, 2]] : [['人工 + 单次 AI', 54, 18, 5], ['分阶段人机协作', 42, 12, 3], ['协作 + Skill 复用', 35, 9, 2]];
    return `${pageHead('EXPERIMENTS & EVALUATION', '用证据，理解协作的价值。', '把研发活动转化为可比较的观察，研究效率、质量与人工介入之间的关系。', button('export-protocol', icon('download') + '导出实验方案', 'btn secondary') + button('experiment-plan', icon('plus') + '设计实验', 'btn primary'))}<div class="experiment-disclaimer">${icon('flask')}<div><strong>实验设计预览，尚未采集真实结果</strong><span>下方数值仅用于演示分析界面，不构成实验结果或效果证明。</span></div>${badge('示例数据', 'amber')}</div><div class="experiment-tabs">${button('experiment', 'E01 · 人机协作方式对照', `experiment-tab ${!skillExp ? 'active' : ''}`, 'data-id="E01"')}${button('experiment', 'E02 · Skill 复用效果观察', `experiment-tab ${skillExp ? 'active' : ''}`, 'data-id="E02"')}</div><div class="experiment-summary"><div><span class="eyebrow">${state.selectedExperiment} / PROPOSED STUDY</span><h2>${skillExp ? '可复用的 Skill，能否减少重复试错？' : '分阶段协作，能否改善任务交付过程？'}</h2><p>${skillExp ? '固定任务类型与模型配置，比较有无 Skill，以及 Skill 迭代前后的任务表现。' : '比较不同协作方式下的任务效率、交付质量，以及人需要介入的位置与原因。'}</p></div>${badge('方案待审阅', 'orange')}</div><div class="metric-definitions">${[['clock', '完成时间', '从任务开始到人工验收通过'], ['shield', '交付质量', '独立评审 + 验收用例通过情况'], ['users', '人工介入', '接管次数、耗时与介入原因'], ['workflow', '返工情况', '评审后修改轮次与缺陷类别']].map(([ic, title, desc]) => `<div class="metric-definition">${icon(ic)}<strong>${title}</strong><p>${desc}</p></div>`).join('')}</div><div class="two-col experiment-charts"><section class="panel">${panelHead('任务完成时间', '同类任务的组间比较 · 分钟', badge('模拟示意'))}<div class="bar-chart" role="img" aria-label="模拟数据，三组完成时间分别为 ${groups.map(g => g[1]).join('、')} 分钟"><div class="chart-axis"><span>0</span><span>20</span><span>40</span><span>60 min</span></div>${groups.map(([name, time], i) => `<div class="bar-row"><span>${name}</span><div class="bar-track"><i class="bar-fill bar-${i}" style="width:${Number(time) / 60 * 100}%"><b>${time}</b></i></div></div>`).join('')}</div><div class="chart-footnote">展示形式示意 · 正式实验将保留逐任务观测与离散程度</div></section><section class="panel">${panelHead('人工介入发生在哪里', '研发阶段中的人工介入点 · 示例轨迹', badge('模拟示意'))}<div class="intervention-chart"><div class="intervention-legend"><span><i class="legend-dot orange"></i>关键决策</span><span><i class="legend-dot blue"></i>纠错接管</span></div><div class="intervention-rows">${[['需求', 2, 0], ['设计', 2, 1], ['实现', 1, 3], ['验证', 3, 2], ['交付', 1, 0], ['沉淀', 2, 0]].map(([name, decision, repair]) => `<div class="intervention-row"><span>${name}</span><div>${Array.from({ length: decision }, () => '<i class="intervention-dot decision"></i>').join('')}${Array.from({ length: repair }, () => '<i class="intervention-dot repair"></i>').join('')}</div></div>`).join('')}</div></div><div class="chart-footnote">每个圆点代表一个示例事件，不代表真实运行记录</div></section></div><section class="panel">${panelHead('实验记录', '预览如何将一次任务关联到执行证据与评价', button('experiment-plan', '查看实验协议 ' + icon('arrow'), 'text-link'))}<div class="table-scroll"><table><thead><tr><th>协作条件</th><th>示例任务</th><th>耗时</th><th>人工介入耗时</th><th>介入次数</th><th>数据性质</th></tr></thead><tbody>${groups.map(([name, time, human, count], i) => `<tr><td><strong>${name}</strong></td><td>${['引用来源展示', '上传边界测试', '检索状态反馈'][i]}</td><td>${time} min</td><td>${human} min</td><td>${count} 次</td><td>${badge('模拟', 'amber')}</td></tr>`).join('')}</tbody></table></div></section>`;
  }
  function research() {
    return `${pageHead('RESEARCH BRIEF', '让人机协作，成为可研究的过程。', '我们关心：人与 AI 怎样协作，才能形成可追溯、可验证、可复用的软件研发过程。', button('review', icon('message') + '给出审阅意见', 'btn secondary') + button('start-tour', icon('play') + '开始原型导览', 'btn primary'))}<div class="research-intro"><div><span class="eyebrow">WORKPAL / RESEARCH PROPOSAL</span><h2>面向 AI 原生 SDLC 的<br>人机协同与知识复用研究</h2><p>以 TAP 的持续研发为应用场景，探索如何将 AI 从单次问答工具，组织为有明确职责、工作流和交付证据的研发伙伴。</p><div class="research-keywords">${['人机协同', '软件工程', 'Agent 工作流', 'Skill 复用', '可观测评估'].map(x => badge(x, 'orange')).join('')}</div></div><aside><span>研究载体</span><strong>Workpal</strong><span>应用场景</span><strong>TAP 产品研发</strong><span>当前阶段</span><strong>原型设计 · 待导师审阅</strong></aside></div><div class="section-heading"><div class="eyebrow">01 / RESEARCH QUESTIONS</div><h2>三个问题，贯穿整条研发链路。</h2></div><div class="research-questions">${[['RQ1', '协作怎样组织？', '显式划分职责、阶段和交接物，是否有助于提升任务交付质量与过程可追溯性？', '观察：完成时间、验收结果、返工轮次'], ['RQ2', '人应该何时介入？', '哪些决策适合交由 AI 执行，哪些环节必须由人确认？不同门禁策略如何影响质量与负担？', '观察：介入时点、原因、耗时与结果'], ['RQ3', '经验怎样被复用？', '将有效方法沉淀为 Skill 后，能否在相近或新任务中减少重复试错，并保持质量？', '观察：迁移表现、重复错误、方法适用边界']].map(([id, title, text, metrics]) => `<article class="panel question-card"><span class="question-id">${id}</span><h3>${title}</h3><p>${text}</p><small>${metrics}</small></article>`).join('')}</div><div class="section-heading"><div class="eyebrow">02 / RESEARCH FRAMEWORK</div><h2>把工作流、知识与证据连接起来。</h2></div><section class="panel framework"><div class="framework-layer"><span class="framework-label">参与者</span><div class="framework-human">${icon('users')} 人 · 问题定义 / 判断 / 验收</div><span class="framework-plus">+</span><div>${icon('sparkles')} AI 伙伴 · 分析 / 执行 / 整理</div></div><div class="framework-arrow">↓</div><div class="framework-flow">${D.stages.map(s => `<span>${icon(s.icon)}${s.name}</span>`).join('<b>→</b>')}</div><div class="framework-arrow">↓</div><div class="framework-bottom"><div>${icon('book')}<strong>Skill Hub</strong><span>发现 → 使用 → 验证 → 沉淀</span></div><div>${icon('flask')}<strong>实验与评估</strong><span>任务轨迹 → 事件编码 → 对照分析</span></div></div></section><div class="two-col research-method"><section class="panel">${panelHead('研究方法', '拟采用设计科学研究 + 探索性对照实验')}<ol class="numbered-list"><li><span>01</span><div><strong>构建与迭代研究原型</strong><p>先验证协作模型、页面与交接逻辑，再逐步接入实际 Agent 执行。</p></div></li><li><span>02</span><div><strong>选择可比较的 TAP 任务</strong><p>按功能开发、缺陷修复、测试补齐分层；匹配难度与变更规模，记录模型与环境版本。</p></div></li><li><span>03</span><div><strong>开展小规模对照与访谈</strong><p>初步规划 18 个任务、3 种协作条件，采用平衡分配与独立质量评审。样本量和分组方式待导师确认。</p></div></li><li><span>04</span><div><strong>分析效率、质量和协作代价</strong><p>结合任务记录与访谈解释结果，关注失败案例、迁移边界和人工成本。</p></div></li></ol></section><section class="panel">${panelHead('边界与有效性', '哪些是当前设计需要特别控制的变量')}<div class="research-boundaries"><div><h3>学习效应与任务差异</h3><p>避免让同一人重复相同任务；记录任务难度与既有经验，使用配对或分层方案。</p></div><div><h3>模型与工具变化</h3><p>记录模型版本、提示、Skill 版本和运行配置，保证结果可以解释与复核。</p></div><div><h3>评价者偏差</h3><p>预先定义验收标准，尽可能由不了解实验分组的评审者评价交付物。</p></div><div><h3>外部有效性</h3><p>单项目、小样本只能支持探索性观察，不直接推广到所有团队或宣称因果结论。</p></div></div></section></div><div class="section-heading"><div class="eyebrow">03 / RESEARCH ROADMAP</div><h2>从可审阅的设计，到可复核的证据。</h2></div><div class="roadmap">${[['01', '原型与研究设计', '当前阶段', '完成产品原型，确认研究问题与实验协议。'], ['02', '最小执行闭环', '计划中', '接入一个仓库、一种运行环境与人工评审。'], ['03', '对照与观察', '计划中', '收集任务轨迹、介入事件、交付结果与访谈。'], ['04', '复用与总结', '计划中', '迭代 Skill，验证迁移边界并整理研究结论。']].map(([n, title, status, desc], i) => `<div class="roadmap-item ${i === 0 ? 'current' : ''}"><span>${n}</span><div>${badge(status, i === 0 ? 'orange' : 'neutral')}<h3>${title}</h3><p>${desc}</p></div></div>`).join('')}</div><div class="advisor-prompt"><div>${icon('message')}<div><h2>希望向老师请教</h2><p>研究问题是否足够聚焦？对照条件是否合理？人工介入和 Skill 复用的评估，应该如何进一步收敛？</p></div></div>${button('review', '记录审阅意见 ' + icon('arrow'), 'btn ink')}</div>`;
  }
  function settings() {
    return `${pageHead('PROTOTYPE SETTINGS', '为这次审阅，保留清晰的上下文。', '所有状态都只保存在当前浏览器。本原型不连接账户、模型或外部执行服务。')}<section class="panel settings-panel">${panelHead('原型信息')}<dl class="definition-list"><div><dt>正式名称</dt><dd>Workpal</dd></div><div><dt>版本</dt><dd>v0.1 · 导师审阅原型</dd></div><div><dt>设计语言</dt><dd>TAP 暖白 / 橙色 / 轻边框</dd></div><div><dt>执行方式</dt><dd>本地模拟，无真实 Agent 调用</dd></div><div><dt>保存范围</dt><dd>任务修改、Skill 收藏、审阅意见</dd></div></dl><div class="section-divider"></div>${panelHead('审阅资料', `已记录 ${state.notes.length} 条审阅意见`)}<div class="settings-actions">${button('review', icon('message') + '查看审阅意见', 'btn secondary')}${button('export-review', icon('download') + '导出审阅记录', 'btn secondary')}</div><div class="section-divider"></div>${panelHead('恢复演示场景', '重置任务和收藏；审阅意见将保留。')}<div>${button('reset-data', '恢复默认示例数据', 'btn secondary')}</div></section>`;
  }
  function taskDetail(id) {
    const task = state.tasks.find(t => t.id === id); if (!task) return;
    modal(`<span class="modal-eyebrow">${e(task.id)} / ${e(task.project)}</span>${e(task.title)}`, `<form id="task-form"><input type="hidden" name="id" value="${e(task.id)}"/>${teamField(D.taskTeam(task))}<div class="form-grid"><label>任务状态<select name="status">${Object.entries(D.statusLabels).map(([key, label]) => `<option value="${key}" ${task.status === key ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label>责任伙伴<select name="owner">${[...D.agents.map(a => a.name), '研究者'].map(n => `<option ${task.owner === n ? 'selected' : ''}>${n}</option>`).join('')}</select></label></div><h3 class="section-title">任务上下文</h3><p class="body-copy">${e(task.description)}</p><h3 class="section-title">验收标准</h3><ul class="detail-checklist">${task.checks.map(c => `<li>${icon('check-circle')}${e(c)}</li>`).join('')}</ul><div class="detail-note">${icon('workflow')} 关联阶段：${D.stages[task.stage]?.name || '理解需求'} · 变更保存在浏览器演示数据中。</div><div class="modal-actions">${button('close-modal', '取消', 'btn secondary')}<button type="submit" class="btn primary">保存任务</button></div></form>`, true);
  }
  function newTask(status = 'todo') {
    modal('创建一个清晰的任务', `<form id="new-task-form"><label>任务名称<input name="title" placeholder="例如：为知识问答补齐引用来源展示" required maxlength="100" autofocus/></label><div class="form-grid"><label>所属项目<select name="project"><option>TAP</option><option>Workpal</option></select></label><label>初始状态<select name="status">${Object.entries(D.statusLabels).map(([k, v]) => `<option value="${k}" ${status === k ? 'selected' : ''}>${v}</option>`).join('')}</select></label></div><label>责任伙伴<select name="owner">${D.agents.map(a => `<option>${a.name}</option>`).join('')}<option>研究者</option></select></label>${teamField('unassigned')}<label>任务上下文<textarea name="description" rows="3" placeholder="描述问题、目标与边界…" required maxlength="2000"></textarea></label><label>验收标准<textarea name="checks" rows="3" placeholder="每行一条，说明怎样判断任务完成" required maxlength="1500"></textarea></label><div class="form-hint">仅添加到原型看板，不会启动真实 Agent。</div><div class="modal-actions">${button('close-modal', '取消', 'btn secondary')}<button class="btn primary" type="submit">创建任务 ${icon('arrow')}</button></div></form>`);
  }
  function skillDetail(id) {
    const skill = D.skills.find(s => s.id === id); if (!skill) return;
    modal(`<span class="modal-eyebrow">SKILL / ${e(skill.author)}</span>${skill.name}`, `<div class="skill-detail-intro"><span class="skill-icon ${skill.color} large">${icon(skill.icon)}</span><div><h3>${skill.subtitle}</h3><p>${skill.description}</p></div></div><div class="detail-tabs"><span class="active">使用说明</span><a href="${skill.source}" target="_blank" rel="noopener noreferrer">上游源码 ${icon('arrowup')}</a></div><div class="skill-detail-grid"><div><h3>什么时候使用</h3><p>${skill.use}</p><h3>预期交付物</h3><p>${skill.outcome}</p><h3>如何带入你的工作</h3><ol class="ordered-copy"><li>阅读上游说明，确认当前版本与运行要求。</li><li>结合项目约束，将 Skill 绑定到具体任务或伙伴。</li><li>保留验证结果，再决定是否在其他任务中复用。</li></ol></div><aside class="skill-meta"><span>作者 / 维护者</span><strong>${skill.author}</strong><span>所属阶段</span><strong>${D.stages[skill.stage].name}</strong><span>收录方式</span><strong>编辑精选</strong><span>验证状态</span><strong>待项目实测</strong></aside></div><div class="source-box"><span class="field-label">源仓库</span><code>${skill.repo}</code>${button('copy-source', icon('copy') + '复制来源', 'btn secondary small', `data-id="${skill.id}"`)}</div><p class="form-hint">本页为原型中的用途摘要。具体能力、安装步骤与许可以上游仓库为准。</p><div class="modal-actions">${button('bookmark-detail', icon('bookmark') + (state.bookmarks.includes(skill.id) ? '已收藏' : '收藏 Skill'), 'btn secondary', `data-id="${skill.id}"`)}${button('share-skill', icon('share') + '复制分享链接', 'btn primary', `data-id="${skill.id}"`)}</div>`, true);
  }
  function review() {
    const title = D.nav.find(n => n[0] === route().page)?.[1] || '原型设置';
    modal('审阅笔记', `<p class="body-copy">针对研究问题、实验方法或页面设计留下建议。记录保存在本浏览器，可导出后分享给研究者。</p><form id="review-form"><div class="form-grid"><label>审阅人<input name="author" placeholder="老师 / 同学 / 自己" maxlength="50"/></label><label>意见类别<select name="category"><option>研究问题</option><option>实验设计</option><option>产品与交互</option><option>其他建议</option></select></label></div><label>审阅意见<textarea name="text" rows="4" placeholder="我建议进一步明确…" required maxlength="3000"></textarea></label><div class="review-form-footer"><span class="muted">关联页面：${title}</span><button class="btn primary" type="submit">保存意见</button></div></form><div class="section-divider"></div><div class="subsection-title"><h3>已记录 ${state.notes.length} 条</h3>${button('export-review', icon('download') + '导出', 'text-link')}</div><div class="review-notes">${state.notes.length ? state.notes.slice().reverse().map(n => `<article class="review-note"><div><strong>${e(n.author || '匿名审阅人')}</strong>${badge(n.category)}<small>${e(n.page)}</small></div><p>${e(n.text)}</p><time>${e(n.date)}</time></article>`).join('') : '<p class="empty-inline">还没有审阅记录。每一个具体的问题，都能帮助研究更进一步。</p>'}</div>`, true);
  }
  function searchDialog() {
    modal('搜索 Workpal', `<label class="search-field"><span>${icon('search')}</span><input id="global-search" placeholder="搜索页面、任务或 Skill…" autofocus aria-label="全局搜索"/></label><div id="global-results" class="global-results">${searchResults('')}</div>`);
  }
  function searchResults(query) {
    const q = query.trim().toLowerCase();
    const items = [...D.nav.map(([id, label, ic]) => ({ type: '页面', id, label, ic, action: 'navigate' })), ...state.tasks.map(t => ({ type: t.id, id: t.id, label: t.title, ic: 'columns', action: 'task' })), ...D.skills.map(s => ({ type: 'Skill', id: s.id, label: s.name + ' · ' + s.subtitle, ic: 'sparkles', action: 'skill' }))].filter(item => `${item.label} ${item.type}`.toLowerCase().includes(q)).slice(0, 12);
    return items.length ? items.map(item => `<button data-action="${item.action}" data-id="${e(item.id)}" class="search-result">${icon(item.ic)}<span>${e(item.label)}</span><small>${e(item.type)}</small>${icon('arrow')}</button>`).join('') : '<div class="empty-inline">没有找到匹配结果，试试其他关键词。</div>';
  }
  function download(name, content, type = 'text/markdown;charset=utf-8') {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast('已复制，可以分享给同事或同学。'); }
    catch {
      modal('复制内容', `<p class="body-copy">当前离线环境无法直接访问剪贴板，请选中下方内容复制。</p><textarea class="copy-fallback" readonly rows="4">${e(text)}</textarea>`);
      $('.copy-fallback').select();
    }
  }
  const protocol = () => `# Workpal 实验方案（拟议）\n\n状态：待导师审阅；未采集真实实验数据。\n\n## 研究问题\n- RQ1：分阶段人机协作对任务交付质量、时间和可追溯性的影响。\n- RQ2：人工介入的有效位置、原因和成本。\n- RQ3：Skill 复用对重复错误与迁移表现的影响。\n\n## E01：协作方式对照\n比较人工 + 单次 AI、分阶段人机协作、协作 + Skill 三种条件。\n初步规划 18 个任务，按功能开发、缺陷修复、测试补齐分层并平衡分配。样本量与方案待确认。\n\n## E02：Skill 复用\n固定任务类型、模型和运行配置，比较无 Skill、有 Skill、迭代 Skill。使用新任务检验迁移，不重复同一任务。\n\n## 采集字段\n任务 ID、难度层、实验条件、模型和 Skill 版本、开始/验收时间、人工介入原因与耗时、验收结果、返工轮次、执行轨迹引用。\n\n## 分析与限制\n预先确定验收标准，尽可能盲评；保留失败和未完成任务，报告逐任务结果与离散程度。\n控制学习效应、任务差异、评价者偏差；小样本单项目只支持探索性观察，不预设积极结果或宣称因果结论。\n`;
  const actions = {
    'close-modal': closeModal,
    'mobile-nav': () => { state.mobileNav = !state.mobileNav; render(); },
    'new-task': (el) => newTask(el.dataset.status),
    task: (el) => taskDetail(el.dataset.id),
    skill: (el) => skillDetail(el.dataset.id),
    search: searchDialog,
    navigate: (el) => { closeModal(); go(el.dataset.id); },
    review,
    'start-tour': () => { state.tour = true; if (route().page === 'research') render(); else go('research'); },
    'end-tour': () => { state.tour = false; render(); },
    'project-tasks': (el) => { state.project = el.dataset.project; state.taskQuery = ''; go('tasks'); },
    stage: (el) => { state.stage = Number(el.dataset.stage); render(); },
    'advance-flow': () => {
      if (state.flowComplete) { state.runStage = 0; state.flowComplete = false; }
      state.running = true;
      state.stage = state.runStage;
      render();
      modal('演示到达人工确认点', `<div class="gate-modal-icon">${icon('shield')}</div><h3>${D.stages[state.runStage].name} · 等待你的判断</h3><p class="body-copy">${D.stages[state.runStage].gate}。可以查看当前阶段的示例交付物，再决定继续或返回修改。</p><div class="detail-note">此操作仅演示状态流转，不会执行测试、修改代码或发起发布。</div><div class="modal-actions">${button('close-modal', '继续检查', 'btn secondary')}${button('approve-stage', '确认并交接', 'btn primary')}</div>`);
    },
    'approve-stage': () => {
      closeModal();
      if (state.runStage < 5) { state.runStage += 1; state.stage = state.runStage; toast('已记录演示确认，进入「' + D.stages[state.stage].name + '」。'); }
      else { state.running = false; state.flowComplete = true; toast('演示闭环已完成：经验已进入待审阅的 Skill 候选。'); }
      render();
    },
    'reset-flow': () => { state.stage = 0; state.runStage = 0; state.running = false; state.flowComplete = false; render(); toast('演示已回到需求阶段。'); },
    bookmark: (el) => { toggleBookmark(el.dataset.id); updateSkills(); },
    'bookmark-detail': (el) => { toggleBookmark(el.dataset.id); skillDetail(el.dataset.id); if (route().page === 'skills') updateSkills(); },
    'toggle-saved': () => { state.onlySaved = !state.onlySaved; render(); },
    category: (el) => { state.category = el.dataset.category; render(); },
    'reset-skills': () => { state.skillQuery = ''; state.category = '全部'; state.onlySaved = false; render(); },
    'copy-source': (el) => copy(D.skills.find(s => s.id === el.dataset.id).source),
    'share-skill': (el) => {
      const url = new URL(location.href); url.hash = `skills?id=${el.dataset.id}`;
      if (url.protocol === 'file:') {
        copy(`Workpal Skill Hub · ${D.skills.find(s => s.id === el.dataset.id).name}\n离线原型：请将 Workpal.html 一起发送，打开后访问 #skills?id=${el.dataset.id}\n上游来源：${D.skills.find(s => s.id === el.dataset.id).source}`);
      } else { copy(url.href); }
    },
    experiment: (el) => { state.selectedExperiment = el.dataset.id; render(); },
    'export-protocol': () => { download('Workpal-实验方案.md', protocol()); toast('已导出拟议实验方案。'); },
    'experiment-plan': () => modal('实验协议 · 拟议方案', `<div class="modal-document"><h3>研究条件</h3><p>人工 + 单次 AI / 分阶段人机协作 / 协作 + Skill。先做小规模试点，确认任务难度与记录完整性。</p><h3>任务分配</h3><p>初步规划 18 个任务，按功能开发、缺陷修复、测试补齐分层；采用平衡分配，避免重复相同任务带来的学习效应。</p><h3>统一采集</h3><p>模型与 Skill 版本、任务难度、完成时间、人工介入原因和耗时、验收结果与返工轮次。</p><h3>评价原则</h3><p>预先定义验收标准、保留失败任务、尽可能独立盲评。先描述观察，再讨论解释与局限。</p><div class="detail-note">本原型用于确认研究设计，不提供真实实验启动能力。</div></div><div class="modal-actions">${button('review', '记录方法建议', 'btn secondary')}${button('export-protocol', '导出方案', 'btn primary')}</div>`, true),
    'export-review': () => {
      const notes = state.notes.map((n, i) => `## ${i + 1}. ${n.category} / ${n.page}\n\n审阅人：${n.author || '匿名'} · ${n.date}\n\n${n.text}\n`).join('\n');
      download('Workpal-审阅记录.md', '# Workpal 原型审阅记录\n\n' + (notes || '暂无审阅意见。\n'));
      toast('审阅记录已导出。');
    },
    'reset-data': () => modal('恢复默认示例数据？', `<p class="body-copy">这会恢复初始任务和收藏。已保存的审阅意见会保留。</p><div class="modal-actions">${button('close-modal', '取消', 'btn secondary')}${button('confirm-reset', '恢复示例', 'btn primary')}</div>`),
    'confirm-reset': () => { state.tasks = structuredClone(D.tasks); state.bookmarks = ['brainstorming', 'webapp-testing']; persist(); closeModal(); render(); toast('已恢复示例，审阅意见已保留。'); },
    agent: (el) => { const a = D.agents[Number(el.dataset.index)]; modal(`${a.name} · 职责与边界`, `<div class="agent-detail-head">${avatar(a.initials, a.color, 'large')}<div><h3>${a.role}</h3><p>${a.english}</p></div></div><p class="body-copy">${a.description}</p><h3 class="section-title">执行边界</h3><div class="detail-note">${icon('shield')}${a.boundary}</div><h3 class="section-title">绑定的 Skill</h3><div class="agent-skills">${a.skills.map(id => button('skill', icon('sparkles') + D.skills.find(s => s.id === id).name, 'skill-chip', `data-id="${id}"`)).join('')}</div><h3 class="section-title">运行配置预览</h3><dl class="definition-list"><div><dt>预期运行环境</dt><dd>${a.runtime}</dd></div><div><dt>代码执行</dt><dd>本原型未连接</dd></div><div><dt>任务完成条件</dt><dd>提交证据并由责任人验收</dd></div></dl>`); },
    'agent-config': () => modal('配置 AI 伙伴 · 设计预览', `<form id="agent-form"><label>伙伴名称<input name="name" placeholder="例如：安全评审伙伴" required maxlength="50"/></label><label>职责与边界<textarea name="role" placeholder="说明负责什么，以及哪些决策需要由人确认…" rows="4" required maxlength="1000"></textarea></label><label>运行环境<select name="runtime"><option>Codex CLI</option><option>Claude Code</option><option>其他兼容运行环境</option></select></label><p class="form-hint">本阶段会保存为审阅提案，不创建真实 Agent。</p><div class="modal-actions"><button type="submit" class="btn primary">保存配置提案</button></div></form>`),
    'project-guide': () => modal('新建研究项目 · 设计预览', `<form id="project-form"><label>项目名称<input name="name" placeholder="例如：下一代知识库" required maxlength="80"/></label><label>研究场景<textarea name="description" rows="4" placeholder="项目解决什么问题？希望观察哪类协作过程？" required maxlength="1500"></textarea></label><p class="form-hint">原型阶段先收集项目提案，真实仓库接入在后续执行闭环中实现。</p><div class="modal-actions"><button type="submit" class="btn primary">保存项目提案</button></div></form>`),
    'project-detail': (el) => modal(`${e(el.dataset.project)} · 项目说明`, `<div class="modal-document"><h3>应用场景</h3><p>${el.dataset.project === 'TAP' ? '知识问答、文档处理与测试设计生成。用真实研发需求观察人机协作的具体边界。' : '工作流、Skill 分享与实验评估。通过平台自身的迭代改进研究方法。'}</p><h3>研究记录</h3><p>需求及其验收标准、方案选择、执行轨迹、人工介入、验证证据与复盘结果。</p><h3>原型边界</h3><p>当前展示的是示例任务和设计流程，尚未读取或修改真实项目仓库。</p></div><div class="modal-actions">${button('project-tasks-modal', '查看示例任务 ' + icon('arrow'), 'btn primary', `data-project="${e(el.dataset.project)}"`)}</div>`),
    'project-tasks-modal': (el) => { closeModal(); actions['project-tasks'](el); },
    runtime: () => modal('运行环境连接 · 设计说明', `<div class="modal-document"><h3>计划中的连接步骤</h3><ol class="ordered-copy"><li>选择本地工作目录和允许使用的 Agent CLI。</li><li>检查工具是否可用，确认身份与执行权限。</li><li>将运行环境绑定到指定项目和角色。</li><li>以一个隔离任务验证执行、暂停、人工确认和结果回传。</li></ol><div class="detail-note">本原型不读取本机凭据，不调用模型，也不会执行代码。</div></div>`),
    'submit-skill': () => modal('推荐一个好用的 Skill', `<form id="recommend-form"><label>Skill 名称<input name="name" required maxlength="100" placeholder="它叫什么？"/></label><label>上游地址<input name="url" type="url" required maxlength="500" placeholder="https://github.com/…"/></label><label>推荐理由<textarea name="reason" required rows="4" maxlength="1500" placeholder="适合什么场景？你希望它解决什么问题？"></textarea></label><p class="form-hint">推荐将保存为本地审阅记录，尚未接入公开投稿与审核服务。</p><div class="modal-actions"><button type="submit" class="btn primary">保存推荐</button></div></form>`),
    artifacts: () => modal('TAP-028 · 示例交付物', `<div class="artifact-list">${[['需求说明', '为每条回答引用关联可访问的原始片段；缺少来源时明确提示。', '产品伙伴'], ['实现摘要', '在引用列表中加入文档名称、片段位置和打开来源的入口。', '开发伙伴'], ['验收记录', '计划验证有效引用、缺失来源与键盘导航三条路径。此处为演示文案，没有运行测试。', '质量伙伴']].map(([name, desc, owner]) => `<article>${icon('book')}<div><h3>${name}</h3><p>${desc}</p><small>${owner} · 示例材料</small></div></article>`).join('')}</div>`),
    notifications: () => modal('演示通知', `<div class="notification-list">${state.tasks.filter(t => t.status === 'review').map(t => `<button class="attention-row" data-action="task" data-id="${e(t.id)}">${icon('shield')}<div><strong>${e(t.title)}</strong><small>${e(t.id)} · 等待人工评审</small></div>${icon('arrow')}</button>`).join('') || '<p class="empty-inline">当前没有待评审任务。</p>'}<div class="detail-note">这些通知由原型示例任务生成，不来自实际运行。</div></div>`),
    activity: () => modal('TAP-028 · 示例协作轨迹', `<div class="modal-document"><ol class="numbered-list">${[['需求确认', 'Patrick 明确了引用展示的目标和不做事项。'], ['方案交接', '架构伙伴整理接口约束与测试计划，人工确认范围。'], ['协同实现', '开发伙伴提交实现摘要与待验证路径。'], ['质量验证', '质量伙伴归纳验收材料，等待责任人批准。'], ['知识沉淀', '交付后计划提炼“引用可追溯性检查”方法。']].map(([t, d], i) => `<li><span>0${i + 1}</span><div><strong>${t}</strong><p>${d}</p></div></li>`).join('')}</ol><div class="detail-note">此轨迹为交互说明，未在真实 TAP 项目中执行。</div></div>`),
  };
  function toggleBookmark(id) {
    state.bookmarks = state.bookmarks.includes(id) ? state.bookmarks.filter(x => x !== id) : [...state.bookmarks, id];
    persist(); toast(state.bookmarks.includes(id) ? '已加入收藏。' : '已取消收藏。');
  }
  function updateSkills() {
    const items = D.filterSkills(D.skills, state.skillQuery, state.category, state.onlySaved, state.bookmarks);
    const grid = $('#skill-grid'); if (grid) grid.innerHTML = skillCards(items);
    const count = $('#skill-count'); if (count) count.textContent = `${items.length} 个 Skill · 编辑精选`;
    const savedCount = $('[data-action="toggle-saved"] .count'); if (savedCount) savedCount.textContent = state.bookmarks.length;
  }
  function addNote(author, category, text) {
    state.notes.push({ author, category, text, page: D.nav.find(n => n[0] === route().page)?.[1] || '原型设置', date: new Date().toLocaleString('zh-CN', { hour12: false }) });
    persist();
  }
  document.addEventListener('click', (event) => {
    if (event.target.closest('.skip-link')) { event.preventDefault(); $('#main').focus(); $('#main').scrollIntoView(); return; }
    const control = event.target.closest('[data-action]');
    if (control && actions[control.dataset.action]) actions[control.dataset.action](control);
  });
  document.addEventListener('input', (event) => {
    if (event.target.id === 'skill-search') { state.skillQuery = event.target.value; updateSkills(); }
    if (event.target.id === 'task-search') { state.taskQuery = event.target.value; const items = state.tasks.filter(t => (state.project === '全部项目' || state.project === t.project) && `${t.id} ${t.title} ${t.owner}`.toLowerCase().includes(state.taskQuery.trim().toLowerCase())); $('#task-board').innerHTML = taskColumns(items); $('#task-count').textContent = items.length; }
    if (event.target.id === 'global-search') $('#global-results').innerHTML = searchResults(event.target.value);
  });
  document.addEventListener('change', (event) => { if (event.target.id === 'project-filter') { state.project = event.target.value; render(); } });
  document.addEventListener('submit', (event) => {
    const form = event.target; if (!(form instanceof HTMLFormElement)) return;
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const formId = form.getAttribute('id');
    if (Object.values(data).some(v => typeof v === 'string' && !v.trim()) && ['new-task-form', 'recommend-form', 'agent-form', 'project-form'].includes(formId)) { toast('请填写有效内容，不能只输入空格。'); return; }
    if (formId === 'new-task-form') {
      state.tasks.push({ id: `${data.project === 'TAP' ? 'TAP' : 'WP'}-${String(Date.now()).slice(-6)}`, title: data.title.trim(), status: data.status, priority: '中', owner: data.owner, team: data.team, project: data.project, stage: 0, description: data.description.trim(), checks: data.checks.split('\n').map(x => x.trim()).filter(Boolean), tags: ['新建任务'] });
      state.project = '全部项目'; state.taskQuery = ''; persist(); closeModal(); go('tasks'); render(); toast('任务已添加到原型看板。');
    }
    if (formId === 'task-form') { const task = state.tasks.find(t => t.id === data.id); task.status = data.status; task.owner = data.owner; task.team = data.team; persist(); closeModal(); render(); toast('任务已保存。'); }
    if (formId === 'review-form') { if (!data.text.trim()) { toast('请填写具体意见。'); return; } addNote(data.author.trim(), data.category, data.text.trim()); review(); toast('审阅意见已保存在本浏览器。'); }
    if (formId === 'recommend-form') { if (!/^https?:\/\//i.test(data.url)) { toast('请提供 HTTP 或 HTTPS 来源地址。'); return; } addNote('Skill 推荐', '产品与交互', `${data.name}\n${data.url}\n${data.reason}`); closeModal(); toast('推荐已加入审阅记录，尚未公开发布。'); }
    if (formId === 'agent-form') { addNote('配置提案', '产品与交互', `AI 伙伴：${data.name}\n职责：${data.role}\n运行环境：${data.runtime}`); closeModal(); toast('配置提案已加入审阅记录。'); }
    if (formId === 'project-form') { addNote('项目提案', '研究问题', `项目：${data.name}\n研究场景：${data.description}`); closeModal(); toast('项目提案已加入审阅记录。'); }
  });
  window.addEventListener('hashchange', () => { closeModal(); state.mobileNav = false; render(); window.scrollTo(0, 0); });
  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchDialog(); }
    if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && !$('#dialog').open) { event.preventDefault(); const search = $('#skill-search') || $('#task-search'); if (search) search.focus(); else searchDialog(); }
  });
  $('#dialog').addEventListener('click', (event) => { if (event.target === $('#dialog')) { const r = $('#dialog').getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) closeModal(); } });
  render();
})();
