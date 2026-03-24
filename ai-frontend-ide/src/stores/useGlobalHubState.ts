import { ref } from 'vue'
import type {
  BenchmarkOverview,
  BlockGalleryOverview,
  EvaluationOverview,
  ShowcaseProfile,
} from '../types/chat'

export const createGlobalHubState = () => {
  const sessions = ref<any[]>([])
  const benchmarkOverview = ref<BenchmarkOverview>({})
  const evaluationOverview = ref<EvaluationOverview>({})
  const blockGalleryOverview = ref<BlockGalleryOverview>({})
  const showcaseProfiles = ref<ShowcaseProfile[]>([])
  const creatorPersona = ref<string>('硬核数码博主')

  return {
    sessions,
    benchmarkOverview,
    evaluationOverview,
    blockGalleryOverview,
    showcaseProfiles,
    creatorPersona,
  }
}
