# app/agents/nodes/component_dict.py

COMPONENT_DICTIONARY = """
【允许使用的组件清单】
你只能使用以下类型的组件 (type)。严禁捏造不存在的组件类型。

1. "HeroBanner" (大图横幅)
   - 用途：页面顶部，吸引眼球。
   - 字段：`title` (主标题), `subtitle` (副标题), `image_url` (背景或主图)

2. "TextSection" (纯文本段落)
   - 用途：讲故事，长文本。
   - 字段：`heading` (小标题), `paragraphs` (字符串数组，每项是一段话)

3. "ImageCard" (图文卡片)
   - 用途：展示单个实体（如：哈基米特写）。
   - 字段：`image_url` (图片), `caption` (图片描述), `desc` (详细说明)

4. "FeatureGrid" (网格特性)
   - 用途：列出多个特点（如：哈基旺的3个性格）。
   - 字段：`items` (数组，包含 `icon`, `title`, `text`)
"""