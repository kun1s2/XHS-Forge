import componentManifestJson from '../../config/componentManifest.json'
import type { NoteDocumentBlock } from '../../types/chat'

type GuidanceInput = {
  block: NoteDocumentBlock | null
  payload: Record<string, unknown>
  selectedParagraphIndex: number | null
  pendingFactConflictCount: number
}

export type EditingAction = {
  label: string
  prompt: string
}

export type EditingGuidance = {
  componentLabel: string
  selectionLabel: string
  selectionModeLabel: string
  semanticRoleLabel: string
  semanticRoleHint: string
  editableTargets: string[]
  capabilityBadges: string[]
  directActions: EditingAction[]
  quickActions: EditingAction[]
  promptRecipes: EditingAction[]
  composerPlaceholder: string
}

type ComponentSpecificGuidance = {
  direct: EditingAction[]
  quick: EditingAction[]
  recipes: EditingAction[]
  placeholder: string
}

type ManifestEntry = {
  type: string
  label?: string
  semantic_role?: string
  editable_targets?: string[]
  quick_actions?: string[]
}

const manifestEntries = (((componentManifestJson as { components?: ManifestEntry[] }).components) || []).reduce<Record<string, ManifestEntry>>(
  (acc, item) => {
    acc[item.type] = item
    return acc
  },
  {},
)

const semanticRoleLabels: Record<string, string> = {
  heading: '标题表达',
  narrative_text: '叙事正文',
  evidence_summary: '事实摘要',
  score_overview: '维度判断',
  comparison: '对比判断',
  interactive_opinion: '互动表达',
  hero_media: '主视觉表达',
  location_info: '地点信息',
  ambience_snapshot: '氛围快照',
  quote_highlight: '引用强调',
  timeline: '时间流程',
}

const semanticRoleHints: Record<string, string> = {
  heading: '适合调整标题力度、信息密度和读者第一眼注意点。',
  narrative_text: '适合重写段落、压缩表达、调整语气或重排叙述顺序。',
  evidence_summary: '适合保留事实前提下重排重点、补确认提醒、压缩参数噪音。',
  score_overview: '适合调整维度命名、评分结论和证据解读的保守程度。',
  comparison: '适合修改左右两侧观点、平衡结论力度和对比视角。',
  interactive_opinion: '适合改提问方式、选项站位和互动语气。',
  hero_media: '适合改封面氛围、图片叙事和首屏吸引力。',
  location_info: '适合补地点说明、路线信息和实用建议。',
  ambience_snapshot: '适合改氛围描述、时间天气和生活感表达。',
  quote_highlight: '适合改金句内容、出处和强调方式。',
  timeline: '适合改事件顺序、节奏和每一步的重点。',
}

const editableTargetLabels: Record<string, string> = {
  title: '标题',
  subtitle: '副标题',
  paragraphs: '整段正文',
  'paragraphs[0]': '第 1 段',
  'paragraphs[1]': '第 2 段',
  'paragraphs[2]': '第 3 段',
  core_features: '核心事实',
  dimensions: '评分维度',
  scores: '评分结果',
  pros: '左侧观点',
  cons: '右侧观点',
  decision_hint: '结论建议',
  risk_note: '边界提醒',
  question: '提问方式',
  option_a: '选项 A',
  option_b: '选项 B',
  image_urls: '封面图片',
  poi_name: '地点名称',
  location: '地点描述',
  desc: '氛围描述',
  weather: '天气说明',
  temperature: '温度信息',
  time: '时间说明',
  quote: '引用内容',
  author: '引用来源',
  events: '时间节点',
}

const defaultPlaceholder = '例如：只改当前结论位，保留事实不动。'

const dedupeActions = (actions: EditingAction[]) => {
  const seen = new Set<string>()
  return actions.filter((action) => {
    const key = `${action.label}::${action.prompt}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const mapManifestActionToPrompt = (componentLabel: string, action: string) => ({
  label: action,
  prompt: `把这个${componentLabel}改成「${action}」的方向，保留其余未提到的信息结构。`,
})

const buildStoryTextActions = (selectedParagraphIndex: number | null) => {
  if (typeof selectedParagraphIndex === 'number') {
    const paragraph = selectedParagraphIndex + 1
    return {
      direct: [
        { label: `只改第 ${paragraph} 段`, prompt: `只改这个正文块的第${paragraph}段，其他段落完全不动。` },
        { label: `第 ${paragraph} 段更尖锐`, prompt: `只改这个正文块的第${paragraph}段，把语气改得更尖锐一点。` },
      ],
      quick: [
        { label: '这一段更简短', prompt: `把这个正文块的第${paragraph}段简短一点，保留核心意思。` },
        { label: '这一段更尖锐', prompt: `把这个正文块的第${paragraph}段改得更尖锐一点，但不要失真。` },
        { label: '这一段保留事实改表达', prompt: `保留这个正文块第${paragraph}段的事实信息，只重写表达方式。` },
      ],
      recipes: [
        { label: '只改这一段', prompt: `只改这个正文块的第${paragraph}段，其他段落完全不动。` },
        { label: '把这一段结论提前', prompt: `把这个正文块第${paragraph}段的结论提前到开头，但保留信息。` },
        { label: '这一段更像个人判断', prompt: `把这个正文块第${paragraph}段改得更像真实个人判断，而不是说明书。` },
      ],
      placeholder: `例如：只改第${paragraph}段，保留事实，把语气改得更克制。`,
    }
  }

  return {
    direct: [
      { label: '只改开头', prompt: '只改这个正文块的开头一段，让进入主题更快。' },
      { label: '只改结尾收口', prompt: '只改这个正文块最后一段，让结尾更干净有判断。' },
    ],
    quick: [
      { label: '正文更简短', prompt: '把这个正文块简短一点，保留核心信息。' },
      { label: '正文更尖锐', prompt: '把这个正文块改得更尖锐一点，但不要失真。' },
      { label: '保留事实改表达', prompt: '保留这个正文块的事实信息，只重写表达方式。' },
    ],
    recipes: [
      { label: '只改开头', prompt: '只改这个正文块的开头一段，让进入主题更快。' },
      { label: '重排段落顺序', prompt: '重排这个正文块的段落顺序，让结论更前置。' },
      { label: '降低营销感', prompt: '把这个正文块改得更像真实经验分享，降低营销感。' },
    ],
    placeholder: '例如：只改开头两段，让进入主题更快，后面内容不动。',
  }
}

const buildComponentSpecificGuidance = (
  componentType: string,
  componentLabel: string,
  selectedParagraphIndex: number | null,
  pendingFactConflictCount: number,
) : ComponentSpecificGuidance => {
  switch (componentType) {
    case 'StoryText':
      return buildStoryTextActions(selectedParagraphIndex)
    case 'TitleBlock':
      return {
        direct: [
          { label: '只改标题', prompt: '只改这个标题块的主标题，副标题保持不动。' },
          { label: '只改副标题', prompt: '只改这个标题块的副标题，不动主标题。' },
        ],
        quick: [
          { label: '标题更有张力', prompt: '把这个标题块改得更有张力一点，但不要标题党。' },
          { label: '标题更克制', prompt: '把这个标题块改得更克制一点，保留吸引力。' },
          { label: '副标题更有信息量', prompt: '给这个标题块补一个更有信息量的副标题。' },
        ],
        recipes: [
          { label: '只改标题不改副标题', prompt: '只改这个标题块的主标题，副标题保持不动。' },
          { label: '更像真实经验总结', prompt: '把这个标题块改得更像真实经验总结，不要太像广告。' },
          { label: '结论更前置', prompt: '把这个标题块的核心结论前置，让读者第一眼就能看懂立场。' },
        ],
        placeholder: '例如：只改标题，让结论更鲜明，但不要变成标题党。',
      }
    case 'CoverSwiper':
      return {
        direct: [
          { label: '只改首图文案', prompt: '只改这个封面轮播的首图文案和说明，不动其他图片与顺序。' },
          { label: '只改轮播说明', prompt: '只改这个封面轮播下方的说明文案，不动图片。' },
          { label: '封面图更贴主题', prompt: '只改这个封面轮播的首屏表达，让它更贴当前主题。' },
        ],
        quick: [
          { label: '封面更克制', prompt: '把这个封面区块改得更克制一点，减少花哨感。' },
          { label: '封面更有冲击力', prompt: '把这个封面区块改得更有视觉冲击力。' },
          { label: '首屏更贴主题', prompt: '让这个封面区块更贴当前主题，不要跑到泛风景感。' },
        ],
        recipes: [
          { label: '只改封面文案', prompt: '只改这个封面区块的文案说明，不动图片排序。' },
          { label: '更像开场导语', prompt: '让这个封面区块更像整页开场导语，强化主题感。' },
          { label: '更像生活方式封面', prompt: '把这个封面区块改得更像生活方式内容，而不是硬广告。' },
        ],
        placeholder: '例如：只改封面文案，让首屏更贴主题，不改图片顺序。',
      }
    case 'PollBlock':
      return {
        direct: [
          { label: '只改问题', prompt: '只改这个投票块的问题句式，两个选项保持不动。' },
          { label: '只改选项 A', prompt: '只改这个投票块的选项 A，其他内容保持不动。' },
          { label: '只改选项 B', prompt: '只改这个投票块的选项 B，其他内容保持不动。' },
        ],
        quick: [
          { label: '问题更毒舌', prompt: '把这个投票块的提问方式改得更毒舌一点，但保留诚实感。' },
          { label: '问题更温和', prompt: '把这个投票块的提问方式改得更温和一点。' },
          { label: '选项更清楚', prompt: '把这个投票块的两个选项写得更清楚、更像真站队。' },
        ],
        recipes: [
          { label: '只改提问方式', prompt: '只改这个投票块的问题句式，选项保持不动。' },
          { label: '把选项 A 改得更有吸引力', prompt: '只改这个投票块的选项 A，让它更有吸引力。' },
          { label: '改成更像互动引导', prompt: '把这个投票块改得更像互动引导，而不是冷冰冰的问卷。' },
        ],
        placeholder: '例如：只改提问方式，让它更像真站队，不改两个选项。',
      }
    case 'VersusCard':
      return {
        direct: [
          { label: '只改左列', prompt: '只改这个对比卡左侧的观点和细节，右侧完全不动。' },
          { label: '只改右列', prompt: '只改这个对比卡右侧的观点和细节，左侧完全不动。' },
          { label: '只改结论位', prompt: '只改这个对比卡的结论位和判断句，不动左右两列事实。' },
        ],
        quick: [
          { label: '结论更鲜明', prompt: '把这个对比卡的核心结论改得更鲜明一点。' },
          { label: '左右更均衡', prompt: '让这个对比卡左右两侧的信息密度更均衡。' },
          { label: '更像真实路线对比', prompt: '把这个对比卡改得更像真实路线对比，而不是红黑对抗。' },
        ],
        recipes: [
          { label: '只改左侧观点', prompt: '只改这个对比卡左侧的观点和细节，右侧完全不动。' },
          { label: '只改右侧观点', prompt: '只改这个对比卡右侧的观点和细节，左侧完全不动。' },
          { label: '保留事实，重写结论位', prompt: '保留这个对比卡左右两侧事实，只重写结论位，让立场更清楚。' },
        ],
        placeholder: '例如：只改左侧观点，让结论更清楚，右侧保持不动。',
      }
    case 'RadarChartBlock':
      return {
        direct: [
          { label: '只改结论摘要', prompt: '只改这个雷达图的结论摘要，维度和分数不动。' },
          { label: '只改维度名', prompt: '只改这个雷达图的维度名称，让它更容易理解。' },
        ],
        quick: [
          { label: '维度更克制', prompt: '把这个雷达图的维度描述改得更克制，不要夸大。' },
          { label: '强化总结结论', prompt: '强化这个雷达图的总结结论，让读者更容易看懂整体判断。' },
          { label: '补一个短板提醒', prompt: '给这个雷达图补一个清楚的短板提醒。' },
        ],
        recipes: [
          { label: '只改结论摘要', prompt: '只改这个雷达图的结论摘要，维度和分数不动。' },
          { label: '让维度名更易懂', prompt: '把这个雷达图的维度名称改得更容易理解。' },
          { label: '更像证据摘要', prompt: '把这个雷达图改得更像证据摘要，而不是单纯评分展示。' },
        ],
        placeholder: '例如：只改雷达图结论摘要，不动分数，让证据感更强。',
      }
    case 'ProductSpecCard':
      return {
        direct: [
          { label: '只改参数标题', prompt: '只改这个参数卡每条参数的表达方式，不动事实值。' },
          { label: '只改边界提醒', prompt: '只改这个参数卡的边界提醒和保守表达，不动参数事实。' },
        ],
        quick: [
          { label: '参数更克制', prompt: '把这个参数卡改成更克制的保守表达，不要把存在冲突的参数写成绝对结论。' },
          { label: '提醒确认官方值', prompt: '给这个参数卡补一句提醒，说明存在待确认参数，建议以官方页或人工确认为准。' },
          ...(pendingFactConflictCount === 0
            ? [{ label: '应用已确认事实', prompt: '把这个参数卡改得更明确一点，优先使用已经确认的事实值。' }]
            : []),
        ],
        recipes: [
          { label: '只保留最关键 3 条', prompt: '把这个参数卡压缩成最关键的 3 条事实，其他先收掉。' },
          { label: '改得更像结论卡', prompt: '把这个参数卡改得更像结论卡，而不是堆满参数列表。' },
          { label: '保留事实，降低绝对口气', prompt: '保留这个参数卡的事实内容，但把绝对口气降下来。' },
        ],
        placeholder: '例如：保留事实，把参数卡压成最关键 3 条，并加一个确认提醒。',
      }
    case 'LocationBlock':
      return {
        direct: [
          { label: '只改地点名', prompt: '只改这个地点卡的地点名称和标题，不动说明。' },
          { label: '只改路线说明', prompt: '只改这个地点卡的路线与到达说明，不动地点名称。' },
        ],
        quick: [
          { label: '地点更具体', prompt: '把这个地点卡写得更具体一点，让人知道到底在哪。' },
          { label: '路线更清楚', prompt: '把这个地点卡改得更像可执行路线说明。' },
          { label: '氛围更生活化', prompt: '把这个地点卡改得更有生活方式感。' },
        ],
        recipes: [
          { label: '只改地点描述', prompt: '只改这个地点卡的描述方式，不动地点名称。' },
          { label: '更像攻略提示', prompt: '让这个地点卡更像攻略提示，补一点实用信息。' },
          { label: '更像生活体验', prompt: '让这个地点卡更像真实生活体验，而不是地图说明。' },
        ],
        placeholder: '例如：只改地点描述，让路线更清楚，但地点名称不要变。',
      }
    case 'WeatherPolaroid':
      return {
        direct: [
          { label: '只改氛围描述', prompt: '只改这个氛围图卡的描述文案，不动天气时间信息。' },
          { label: '只改天气时间', prompt: '只改这个氛围图卡的天气和时间信息，描述不动。' },
        ],
        quick: [
          { label: '氛围更贴主题', prompt: '让这个氛围图卡的文案更贴当前主题，不要跑题。' },
          { label: '更像生活片段', prompt: '让这个氛围图卡更像真实生活片段。' },
          { label: '降低装饰感', prompt: '把这个氛围图卡改得更自然，降低装饰感。' },
        ],
        recipes: [
          { label: '只改氛围描述', prompt: '只改这个氛围图卡的描述文案，不动天气时间信息。' },
          { label: '让文案更贴页面主题', prompt: '让这个氛围图卡的文案更贴整页主题。' },
          { label: '更像收尾一笔', prompt: '把这个氛围图卡改得更像页面最后的收尾一笔。' },
        ],
        placeholder: '例如：只改氛围描述，让它更贴页面主题，不要再像泛风景。',
      }
    default:
      return {
        direct: [
          { label: '只改当前块', prompt: `只改这个${componentLabel}，其他区块完全不动。` },
        ],
        quick: [],
        recipes: [
          { label: '只改当前块', prompt: `只改这个${componentLabel}，其他区块完全不动。` },
          { label: '保留事实改表达', prompt: `保留这个${componentLabel}的事实信息，只调整表达方式。` },
        ],
        placeholder: defaultPlaceholder,
      }
  }
}

export const buildEditingGuidance = ({
  block,
  payload,
  selectedParagraphIndex,
  pendingFactConflictCount,
}: GuidanceInput): EditingGuidance => {
  const componentType = String(block?.component_type || block?.type || '')
  const manifest = manifestEntries[componentType]
  const componentLabel = String(block?.label || manifest?.label || componentType || '区块')
  const semanticRole = String(block?.semantic_role || manifest?.semantic_role || 'content')
  const semanticRoleLabel = semanticRoleLabels[semanticRole] || '内容编辑'
  const semanticRoleHint = semanticRoleHints[semanticRole] || '适合围绕当前区块做更细的定向修改。'
  const editableTargetsRaw = Array.isArray(block?.editable_targets) && block?.editable_targets?.length
    ? block?.editable_targets
    : (manifest?.editable_targets || [])

  const editableTargets = editableTargetsRaw.map((target) => editableTargetLabels[target] || target)
  const selectionLabel = componentType === 'StoryText' && typeof selectedParagraphIndex === 'number'
    ? `${componentLabel} · 第${selectedParagraphIndex + 1}段`
    : componentLabel

  const selectionModeLabel = typeof selectedParagraphIndex === 'number'
    ? '当前是段落级精修'
    : '当前是积木级精修'

  const capabilityBadges = [
    semanticRoleLabel,
    ...(editableTargets.length > 0 ? [`可改 ${editableTargets.length} 个槽位`] : []),
    ...(block?.fact_binding_support ? ['可保留事实改表达'] : []),
    ...(block?.asset_support && block.asset_support !== 'none' ? ['支持素材联动'] : []),
  ]

  const specific = buildComponentSpecificGuidance(
    componentType,
    componentLabel,
    selectedParagraphIndex,
    pendingFactConflictCount,
  )
  const manifestQuickActions = (manifest?.quick_actions || []).map((action) =>
    mapManifestActionToPrompt(componentLabel, action),
  )

  const quickActions = dedupeActions([...specific.quick, ...manifestQuickActions]).slice(0, 6)
  const promptRecipes = dedupeActions(specific.recipes).slice(0, 4)

  return {
    componentLabel,
    selectionLabel,
    selectionModeLabel,
    semanticRoleLabel,
    semanticRoleHint,
    editableTargets,
    capabilityBadges,
    directActions: dedupeActions(specific.direct).slice(0, 4),
    quickActions,
    promptRecipes,
    composerPlaceholder: specific.placeholder || defaultPlaceholder,
  }
}
