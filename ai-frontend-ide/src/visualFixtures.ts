import type { NoteDocument } from './types/chat'

type VisualFixture = {
  id: string
  title: string
  description: string
  noteDocument: NoteDocument
}

const svgDataUri = ({
  title,
  subtitle,
  start,
  end,
}: {
  title: string
  subtitle: string
  start: string
  end: string
}) =>
  `data:image/svg+xml;utf8,${encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 900">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${start}" />
          <stop offset="100%" stop-color="${end}" />
        </linearGradient>
      </defs>
      <rect width="1200" height="900" fill="url(#bg)" rx="48" />
      <circle cx="220" cy="190" r="170" fill="rgba(255,255,255,0.16)" />
      <circle cx="1000" cy="130" r="120" fill="rgba(255,255,255,0.12)" />
      <circle cx="940" cy="760" r="190" fill="rgba(15,23,42,0.12)" />
      <rect x="88" y="612" width="1024" height="176" rx="36" fill="rgba(255,255,255,0.14)" />
      <text x="92" y="694" font-family="Arial, Helvetica, sans-serif" font-size="76" font-weight="800" fill="white">${title}</text>
      <text x="96" y="748" font-family="Arial, Helvetica, sans-serif" font-size="28" fill="rgba(255,255,255,0.86)">${subtitle}</text>
    </svg>
  `)}`

const buildTheme = (primary: string, accent: string, bg = '#fff8f7') => ({
  page_theme: {
    '--bg-color': bg,
    '--bg-gradient': `linear-gradient(180deg, ${bg} 0%, color-mix(in srgb, ${accent} 8%, white 92%) 100%)`,
    '--card-bg': 'rgba(255,255,255,0.95)',
    '--card-bg-soft': 'rgba(255,255,255,0.82)',
    '--card-border': 'rgba(244,114,182,0.14)',
    '--card-shadow': '0 18px 42px rgba(15,23,42,0.08)',
    '--text-color': '#1f2937',
    '--text-muted': '#6b7280',
    '--primary-vibe': primary,
    '--primary-vibe-light': `color-mix(in srgb, ${primary} 20%, white 80%)`,
    '--pro-color': primary,
    '--con-color': '#0f172a',
  },
  global_vars: {},
})

const mateHeroA = '/demo-assets/mate-hero-a.jpg'
const mateHeroB = '/demo-assets/mate-hero-b.jpg'
const digitalAltA = '/demo-assets/travel-hero-a.jpg'
const digitalAltB = '/demo-assets/travel-hero-b.jpg'
const digitalLifestyle = '/demo-assets/daily-hero.jpg'
const digitalDesk = '/demo-assets/daily-coffee.jpg'

export const visualFixtures: VisualFixture[] = [
  {
    id: 'seeding_compare',
    title: '数码对比种草',
    description: '高频对比块、雷达块和互动块一起看，适合锁定比例和信息层级。',
    noteDocument: {
      document_meta: {
        title: '华为 Mate 60：超预期与代价并存的真实结论',
        scenarios: ['seeding'],
      },
      theme: buildTheme('#ff5b7f', '#ffd7de'),
      blocks: [
        {
          id: 'title_1',
          type: 'TitleBlock',
          semantic_role: 'heading',
          props: {
            title: '华为 Mate 60：超预期与代价并存的真实结论',
          },
        },
        {
          id: 'story_1',
          type: 'StoryText',
          semantic_role: 'narrative_text',
          props: {
            paragraphs: [
              '如果你在找的是一台“综合体验很强、但不追求把纸面参数堆到极致”的手机，Mate 60 依然很能打。',
              '它真正拉开差距的地方不是某一个绝对跑分，而是手感、系统稳定性和影像调性组合出来的整体验证感。',
            ],
            sections: [
              {
                label: '开场判断',
                role: 'summary',
                paragraph: '如果你在找的是一台“综合体验很强、但不追求把纸面参数堆到极致”的手机，Mate 60 依然很能打。',
                summary: '先告诉读者为什么还值得继续往下看。',
              },
              {
                label: '为什么成立',
                role: 'selling_point',
                paragraph: '它真正拉开差距的地方不是某一个绝对跑分，而是手感、系统稳定性和影像调性组合出来的整体验证感。',
                summary: '把优势写成使用路线，而不是参数堆砌。',
              },
            ],
          },
        },
        {
          id: 'radar_1',
          type: 'RadarChartBlock',
          semantic_role: 'score_overview',
          props: {
            title: '五维体验雷达',
            dimensions: ['性能', '影像', '续航', '手感', '系统'],
            scores: [85, 90, 83, 88, 92],
            metrics: [
              { label: '性能', value: 85, reason: '重度使用下依然够稳，不会拖后腿。', confidence: 'medium', evidence: '长时间切换与常用负载表现' },
              { label: '影像', value: 90, reason: '风格辨识度很强，属于容易让人记住的优势。', confidence: 'high', evidence: '日景与夜景成像调性' },
              { label: '续航', value: 83, reason: '一天够用，但不是绝对无脑优势。', confidence: 'medium', evidence: '中高强度续航反馈' },
              { label: '手感', value: 88, reason: '上手氛围和握持反馈都很完整。', confidence: 'medium', evidence: '机身尺寸与重量平衡' },
              { label: '系统', value: 92, reason: '流畅度和整体一致性是它真正拉开差距的地方。', confidence: 'high', evidence: '日常操作与反馈节奏' },
            ],
          },
        },
        {
          id: 'versus_1',
          type: 'VersusCard',
          semantic_role: 'comparison',
          props: {
            title: '华为 Mate 60 vs iPhone 17',
            pros: {
              summary: '更在意系统统一性、影像调性和上手氛围',
              points: ['第一眼更容易喜欢', '影像风格辨识度更强', '整机气质更统一'],
              fit_for: '适合更看重上手好感和作品气质的人。',
            },
            cons: {
              summary: '更追求绝对稳定的生态协同和工作流',
              points: ['第三方适配更稳', '视频工作流更省心', '生态协同更成熟'],
              fit_for: '适合更看重长期稳定性和效率的人。',
            },
            pros: {
              summary: '更像“整体验受宠”路线',
              details: '上手观感更完整。影像风格更有记忆点。系统反馈和日常手感更讨喜。',
              points: ['第一眼好感更强', '影像风格更有辨识度', '系统反馈更讨喜'],
              fit_for: '适合更在意整机氛围、影像调性和日常使用愉悦感的人。',
            },
            cons: {
              summary: '更像“效率与生态”路线',
              details: '跨设备协同更成熟。第三方生态更稳。视频和工作流更容易无脑接入。',
              points: ['生态协同更成熟', '第三方适配更稳', '工作流接入更省心'],
              fit_for: '适合更在意效率、生态和长期无脑稳定的人。',
            },
            decision_hint: '这不是单纯优缺点堆砌，而是“你到底更想要哪种使用路线”的分流。',
          },
        },
        {
          id: 'poll_1',
          type: 'PollBlock',
          semantic_role: 'interactive_opinion',
          props: {
            question: '华为 Mate 60 的对比里你更站哪边？',
            option_a: '看整机氛围感，我更站 Mate 60',
            option_b: '看生态和效率，我还是选 iPhone',
            explanation: '这张卡只负责承接偏好表达，不假装自己是平台真票仓。',
            option_cards: [
              {
                label: '看整机氛围感，我更站 Mate 60',
                stance: '主推理由',
                vote_hint: '如果你最在意“拿起来就喜欢”的整机体验，会更容易站这边。',
                why_it_matters: '它更适合承接第一购买理由和情绪驱动力。',
              },
              {
                label: '看生态和效率，我还是选 iPhone',
                stance: '现实代价',
                vote_hint: '如果你更看重无脑稳定和工作流效率，会更容易站这边。',
                why_it_matters: '它更适合承接长期使用里的现实妥协点。',
              },
            ],
          },
        },
      ],
      assets: [],
    },
  },
  {
    id: 'seeding_camera_focus',
    title: '影像路线决策页',
    description: '重点观察封面、证据卡和叙事块是否能把“为什么值得买”讲清楚，而不是只堆参数。',
    noteDocument: {
      document_meta: {
        title: 'Mate 60 影像路线：如果你最在意照片风格，这页该怎么讲',
        scenarios: ['seeding'],
      },
      theme: buildTheme('#2563eb', '#dbeafe', '#f6f7ff'),
      blocks: [
        {
          id: 'cover_1',
          type: 'CoverSwiper',
          semantic_role: 'hero_media',
          props: {
            image_urls: [digitalAltA, digitalAltB],
          },
        },
        {
          id: 'spec_camera_1',
          type: 'ProductSpecCard',
          semantic_role: 'fact_list',
          props: {
            spec_items: [
              { label: '主观第一印象', value: '更容易拍出“直接能发”的成片感。', status: 'verified', decision_impact: '适合把影像偏好作为第一购买理由的人。', sources: ['样张与主观体验'] },
              { label: '夜景风格', value: '夜景更偏克制，不会一味拉高亮。', status: 'default', decision_impact: '适合解释它的风格路线，而不是简单写成“夜景更强”。', sources: ['夜景样张'] },
              { label: '风险边界', value: '如果你最在意第三方视频工作流，需要更保守判断。', status: 'caution', decision_impact: '适合作为风险边界而不是一票否决。', sources: ['创作工作流体验'] },
            ],
          },
        },
        {
          id: 'story_2',
          type: 'StoryText',
          semantic_role: 'narrative_text',
          props: {
            paragraphs: [
              '这页不追求把影像参数铺满，而是更强调“这台手机拍出来到底是什么感觉”。',
              '如果你选手机的第一判断标准是出片风格和稳定性，这类表达会比单纯列参数更能帮助决策。',
            ],
          },
        },
        {
          id: 'weather_1',
          type: 'WeatherPolaroid',
          semantic_role: 'ambience_snapshot',
          props: {
            image_url: digitalAltB,
            caption: '这类图片区块更适合承接“影像调性”而不是装饰性摆图。',
            location: '样张氛围参考',
            weather: 'Tone Study',
            time: 'Camera Focus',
          },
        },
      ],
      assets: [],
    },
  },
  {
    id: 'seeding_budget_pick',
    title: '预算导向决策页',
    description: '检查轻叙事场景下的封面、正文和互动块是否还能服务购买决策，而不是滑回日常分享页。',
    noteDocument: {
      document_meta: {
        title: '预算 5000 左右，为什么这几台更值得优先看',
        scenarios: ['seeding'],
      },
      theme: buildTheme('#f97316', '#fde68a', '#fffaf4'),
      blocks: [
        {
          id: 'cover_2',
          type: 'CoverSwiper',
          semantic_role: 'hero_media',
          props: {
            image_urls: [digitalLifestyle],
          },
        },
        {
          id: 'title_2',
          type: 'TitleBlock',
          semantic_role: 'heading',
          props: {
            title: '预算 5000 左右，这几台为什么更值得先看',
          },
        },
        {
          id: 'story_3',
          type: 'StoryText',
          semantic_role: 'narrative_text',
          props: {
            paragraphs: [
              '预算导向的购买决策，不是把最贵的那台写得最强，而是把“哪些地方最值、哪些地方该忍”讲清楚。',
              '真正能帮助用户下单的，不是参数百科，而是把预算、体验和风险边界一起落下来。',
            ],
          },
        },
        {
          id: 'poll_2',
          type: 'PollBlock',
          semantic_role: 'interactive_opinion',
          props: {
            question: '如果预算 5000 左右，你会更优先看哪种路线？',
            option_a: '先看整机均衡感',
            option_b: '先看影像和亮点',
          },
        },
      ],
      assets: [],
    },
  },
  {
    id: 'knowledge_digest',
    title: '知识摘要与时间线页',
    description: '补齐参数卡、引用块和时间轴，检查事实摘要类积木在同一页中的层次是否自然。',
    noteDocument: {
      document_meta: {
        title: '一台产品从参数判断到购买建议的完整摘要',
        scenarios: ['seeding'],
      },
      theme: buildTheme('#2563eb', '#dbeafe', '#f8fbff'),
      blocks: [
        {
          id: 'title_knowledge',
          type: 'TitleBlock',
          semantic_role: 'heading',
          props: {
            title: '从参数、引用到购买建议的完整判断',
            subtitle: '不是堆配置，而是把核心依据和结论摆清楚。',
          },
        },
        {
          id: 'spec_1',
          type: 'ProductSpecCard',
          semantic_role: 'evidence_summary',
          props: {
            spec_items: [
              { label: '影像风格', value: '高动态范围更自然，夜景不过度抹平。', status: 'verified', decision_impact: '更适合承接“为什么它一上手就让人有好感”。', sources: ['样张与实测'], hint: '适合放进主推荐理由里。' },
              { label: '续航策略', value: '中高强度一天够用，但重度拍摄仍需补电。', status: 'default', decision_impact: '更适合解释“够不够用”，而不是写成绝对优势。', sources: ['日常续航反馈'], hint: '适合做购买预期管理。' },
              { label: '系统稳定性', value: '日常操作流畅，长时间切应用掉帧感低。', status: 'verified', decision_impact: '更适合承接长期使用里的稳定感。', sources: ['长期体验反馈'], hint: '适合放进结论区。' },
              { label: '购买提醒', value: '如果你更看重生态协同，结论需要更谨慎。', status: 'caution', decision_impact: '更适合作为购买边界，而不是一票否决。', sources: ['跨平台体验'], hint: '这里要保守表达。' },
            ],
          },
        },
        {
          id: 'quote_1',
          type: 'QuoteBlock',
          semantic_role: 'quote_highlight',
          props: {
            quote: '真正影响购买决策的，往往不是某一个参数，而是它在一整天使用里有没有拖后腿。',
            author: '编辑室结论摘录',
          },
        },
        {
          id: 'timeline_1',
          type: 'TimelineBlock',
          semantic_role: 'timeline',
          props: {
            events: [
              { time: '09:30', title: '先看参数', description: '快速排除明显短板，锁定需要重点验证的维度。' },
              { time: '13:00', title: '进入实测', description: '拍照、续航、手感和系统稳定性一起验证。' },
              { time: '18:40', title: '形成结论', description: '保留事实依据，再决定到底是推荐、观望还是劝退。' },
            ],
          },
        },
      ],
      assets: [],
    },
  },
  {
    id: 'all_blocks_gallery',
    title: '全积木总览页',
    description: '一页里把当前所有正式积木都摆出来，专门用于整体视觉和比例检查。',
    noteDocument: {
      document_meta: {
        title: 'XHS-Forge 数码决策积木总览',
        scenarios: ['seeding'],
      },
      theme: buildTheme('#ec4899', '#fde7f3', '#fff8fc'),
      blocks: [
        {
          id: 'gallery_cover',
          type: 'CoverSwiper',
          semantic_role: 'hero_media',
          props: {
            image_urls: [mateHeroA, mateHeroB],
          },
        },
        {
          id: 'gallery_title',
          type: 'TitleBlock',
          semantic_role: 'heading',
          props: {
            title: '这一页把正式积木全部摆出来',
            subtitle: '重点看比例、层次、主题和块之间有没有彼此抢戏。',
          },
        },
        {
          id: 'gallery_story',
          type: 'StoryText',
          semantic_role: 'narrative_text',
          props: {
            paragraphs: [
              '这张总览页不是为了真实发布，而是为了让我们一次看清所有积木在同一主题里的观感是否协调。',
              '如果某个块比例失控、主题跑偏或信息密度突然断层，在这里会非常明显。',
            ],
            sections: [
              {
                label: '为什么要看总览',
                role: 'summary',
                paragraph: '这张总览页不是为了真实发布，而是为了让我们一次看清所有积木在同一主题里的观感是否协调。',
                summary: '先解释这页存在的意义。',
              },
              {
                label: '怎么看问题',
                role: 'caution',
                paragraph: '如果某个块比例失控、主题跑偏或信息密度突然断层，在这里会非常明显。',
                summary: '把观测重点说清楚。',
              },
            ],
          },
        },
        {
          id: 'gallery_spec',
          type: 'ProductSpecCard',
          semantic_role: 'evidence_summary',
          props: {
            spec_items: [
              { label: '事实摘要', value: '参数卡适合承接结构化事实，不应该做成大段说明书。', status: 'verified', decision_impact: '让读者一眼知道这块是“看判断依据”的。', sources: ['设计规范'] },
              { label: '结论边界', value: '冲突信息要保守表达，不写死绝对判断。', status: 'caution', decision_impact: '决定系统是不是可信。', sources: ['RAG 守则'] },
              { label: '读感要求', value: '信息要短，不要把页面拖成一整面墙。', status: 'default', decision_impact: '决定参数卡有没有“看完就知道怎么买”的感觉。', sources: ['视觉回归规则'] },
            ],
          },
        },
        {
          id: 'gallery_radar',
          type: 'RadarChartBlock',
          semantic_role: 'score_overview',
          props: {
            title: '五维表现总览',
            dimensions: ['主题贴合', '信息层级', '比例舒适度', '互动感', '证据感'],
            scores: [90, 88, 86, 80, 84],
            metrics: [
              { label: '主题贴合', value: 90, reason: '内容和组件职责高度贴题。', confidence: 'high', evidence: '固定样例对齐' },
              { label: '信息层级', value: 88, reason: '从标题到结论的路径比较清楚。', confidence: 'medium', evidence: '阅读顺序检查' },
              { label: '比例舒适度', value: 86, reason: '主体比例已经顺了很多，但仍要防止窄壳误伤。', confidence: 'medium', evidence: '视觉回归截图' },
              { label: '互动感', value: 80, reason: '互动块已经有分流表达，但还需要持续约束。', confidence: 'medium', evidence: 'PollBlock review' },
              { label: '证据感', value: 84, reason: '结构化证据已经存在，但还要避免纯装饰图。', confidence: 'high', evidence: 'RAG grounding 面板' },
            ],
          },
        },
        {
          id: 'gallery_versus',
          type: 'VersusCard',
          semantic_role: 'comparison',
          props: {
            title: '作品感 vs 工程感',
            pros: {
              summary: '更看重作品气质、首屏氛围和整体张力',
              points: ['第一印象更强', '封面叙事更完整', '整体观感更成熟'],
              fit_for: '适合把作品感放在第一优先级的路线。',
            },
            cons: {
              summary: '更看重可维护性、协议一致性和评估体系',
              points: ['迭代更稳', '协议更统一', '更容易长期维护'],
              fit_for: '适合把长期工程质量放前面的路线。',
            },
            pros: {
              summary: '更像作品集展示路线',
              details: '封面、版式、层级和动效会直接决定“像不像成熟产品”。',
              points: ['首屏氛围更强', '更容易给面试官留下第一印象', '更像完成态作品'],
              fit_for: '适合优先追求作品感和展示打动力。',
            },
            cons: {
              summary: '更像长期维护路线',
              details: '协议、测试、评估和回归能力决定后续能不能持续做大。',
              points: ['协议更稳', '回归更可靠', '更适合长期迭代'],
              fit_for: '适合优先追求可维护性和系统质量。',
            },
            risk_note: '真正成熟的项目，应该同时有作品感和工程感，而不是让其中一边彻底压过另一边。',
          },
        },
        {
          id: 'gallery_poll',
          type: 'PollBlock',
          semantic_role: 'interactive_opinion',
          props: {
            question: '如果只能先保一个方向，你更站哪边？',
            option_a: '先把视觉和作品感打满',
            option_b: '先把工程和评估体系打满',
            explanation: '互动块应该承接表达，而不是假装真实平台投票。',
            option_cards: [
              {
                label: '先把视觉和作品感打满',
                stance: '展示优先',
                vote_hint: '适合先把第一眼冲击力做出来。',
                why_it_matters: '它决定面试官会不会立刻愿意继续看下去。',
              },
              {
                label: '先把工程和评估体系打满',
                stance: '系统优先',
                vote_hint: '适合先把长期稳定性打牢。',
                why_it_matters: '它决定项目能不能持续演化而不是停留在 demo。',
              },
            ],
          },
        },
        {
          id: 'gallery_location',
          type: 'LocationBlock',
          semantic_role: 'location_info',
          props: {
            poi_name: '演示工作台',
            location: '右侧工作台负责观察系统，左侧聊天负责输入和版本演化，两边一起看才完整。',
          },
        },
        {
          id: 'gallery_weather',
          type: 'WeatherPolaroid',
          semantic_role: 'ambience_snapshot',
          props: {
            image_url: digitalDesk,
            desc: '这一块现在应该只负责给页面加一点呼吸感，而不是突然跑成完全无关的生活方式图片。',
            weather: 'Soft Light',
            temperature: '22°C',
            time: '17:40',
          },
        },
        {
          id: 'gallery_quote',
          type: 'QuoteBlock',
          semantic_role: 'quote_highlight',
          props: {
            quote: '真正成熟的前端观感，来自比例、留白和语义一致性，而不是堆更多花哨特效。',
            author: '视觉回归守则',
          },
        },
        {
          id: 'gallery_timeline',
          type: 'TimelineBlock',
          semantic_role: 'timeline',
          props: {
            events: [
              { time: 'Step 1', title: '固定样例', description: '先锁住输入和主题，不让截图回归失去意义。' },
              { time: 'Step 2', title: '多视口截图', description: '同时检查窄屏和桌面，避免块在边界宽度变形。' },
              { time: 'Step 3', title: 'review 巡检', description: '整页图和单块图一起看，快速定位是哪块出问题。' },
            ],
          },
        },
      ],
      assets: [],
    },
  },
]

export const getVisualFixture = (fixtureId: string | null | undefined) =>
  visualFixtures.find((fixture) => fixture.id === fixtureId) || visualFixtures[0]
