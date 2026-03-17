// ai-frontend-ide/src/utils/LayoutSolver.ts

export type Breakpoint = 'sm' | 'md' | 'lg';

/**
 * 响应式布局求解器：确保 AI 生成的布局在不同设备上绝对安全
 */
export const resolveResponsiveLayout = (
  colSpan: number = 1,
  breakpoint: Breakpoint
): string => {
  // 手机端强制降级为 1 列 (坍缩逻辑)
  if (breakpoint === 'sm') {
    return 'col-span-1';
  }

  // 平板端限制最大 2 列
  if (breakpoint === 'md') {
    const safeCol = Math.min(colSpan, 2);
    return `col-span-${safeCol}`;
  }

  // 桌面端/预览端按原计划渲染，但最大不超过 4 列
  const safeCol = Math.min(colSpan, 4);
  return `col-span-${safeCol}`;
};

/**
 * 获取当前的断点（模拟简单的 MediaQuery）
 */
export const getCurrentBreakpoint = (width: number): Breakpoint => {
  if (width < 640) return 'sm';
  if (width < 1024) return 'md';
  return 'lg';
};
