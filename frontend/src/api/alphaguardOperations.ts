import { ApiClient } from './request'

export type HealthStatus = 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY' | 'NOT_CONFIGURED' | 'UNKNOWN'
export type DataStatus = 'READY' | 'PARTIAL' | 'NOT_READY' | 'NOT_CONFIGURED' | 'STALE' | 'ERROR'

export interface ServiceHealth {
  service_name: string
  status: HealthStatus
  required: boolean
  reachable: boolean | null
  latency_ms: number | null
  error_code: string | null
  sanitized_message: string | null
  last_checked_at: string
}

export interface DataReadiness {
  component: string
  status: DataStatus
  market: string | null
  coverage_start: string | null
  coverage_end: string | null
  record_count: number | null
  required_for: string[]
  blocking_reasons: string[]
  warnings: string[]
}

export interface JobHealth {
  job_name: string
  worker_name: string
  status: string
  last_run_id: string | null
  last_started_at: string | null
  last_finished_at: string | null
  next_scheduled_at: string | null
  retry_count: number
  backlog_count: number | null
  error_code: string | null
  sanitized_message: string | null
}

export interface OperationalAlert {
  alert_id: string
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
  category: string
  code: string
  title: string
  sanitized_message: string
  source_module: string
  source_object_id: string | null
  trace_id: string | null
  first_seen_at: string
  last_seen_at: string
  occurrence_count: number
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
}

export interface SystemReadiness {
  report_id: string
  overall_status: 'READY_FOR_PAPER' | 'DEGRADED_PAPER' | 'NOT_READY' | 'UNSAFE'
  system_mode: string
  live_trading_enabled: boolean
  live_execution_allowed: false
  service_health: ServiceHealth[]
  data_readiness: DataReadiness[]
  job_health: JobHealth[]
  blocking_items: string[]
  warnings: string[]
  paper_execution_ready: boolean
  evaluation_ready: boolean
  experiment_ready: boolean
  challenger_ready: boolean
  active_challenger: boolean
  recommendation_ready: boolean
  auto_candidate_accept: false
  live_ready: false
  code_commit: string
  build_version: string
  config_hash: string
  report_hash: string
  generated_at: string
}

interface Items<T> { items: T[] }

export interface OperationsOverview {
  readiness: SystemReadiness
  sample_counts: Record<string, number>
  challenger_status: ChallengerOperationsStatus
  recommendation_status: RecommendationOperationsStatus
  mvp_acceptance: MvpAcceptanceReport
  backup_status: { latest_backup_id: string | null; status: 'READY' | 'NOT_READY' }
  consistency_status: 'PASS' | 'WARNING' | 'FAIL' | 'NOT_RUN'
  open_alerts: OperationalAlert[]
  safety_notice: string
}

export type MvpAcceptanceStatus = '可用' | '降级可用' | '未就绪' | '已阻断' | '不适用'
export interface MvpAcceptanceItem {
  item_id: string
  item_name: string
  status: MvpAcceptanceStatus
  last_success_at: string | null
  last_failure_at: string | null
  latest_object_id: string | null
  blocking_reason: string | null
  verification_evidence: string[]
  version: string
  owner_module: string
  advanced: Record<string, unknown>
}
export interface MvpAcceptanceReport {
  report_id: string
  generated_at: string
  overall_status: 'MVP_PAPER_READY' | 'DEGRADED' | 'NOT_READY' | 'BLOCKED'
  items: MvpAcceptanceItem[]
  summary: Record<MvpAcceptanceStatus, number>
  state_flags: Record<string, boolean>
  latest_daily_run_id: string | null
  latest_backup_id: string | null
  consistency_status: 'PASS' | 'WARNING' | 'FAIL' | 'NOT_RUN'
  report_hash: string
}

export interface RecommendationOperationsStatus {
  recommendation_ready: boolean
  recommendation_runtime_ready: boolean
  recommendation_data_ready: boolean
  auto_candidate_accept: false
  security_count: number
  eligible_count: number
  today_recommendation_count: number
  pending_review_count: number
  accepted_count: number
  rejected_count: number
  ignored_count: number
  last_run_status: string
  last_success_at: string | null
  last_duration_ms: number
  failed_symbol_count: number
  policy_version: string
  coverage_status: 'NOT_READY' | 'PARTIAL' | 'READY' | 'DEGRADED'
  coverage_percentage: string
  history_ready_count: number
  trade_status_ready_count: number
  data_quality_pass_count: number
  coverage_failed_symbol_count: number
  blocking_reason_counts: Record<string, number>
  last_sync_at: string | null
  top_score: string | null
  score_distribution: Record<string, number>
}

export interface ChallengerOperationsStatus {
  account_status: 'ACTIVE' | 'NOT_CONFIGURED'
  active_challenger_count: number
  last_run_at: string | null
  last_success_at: string | null
  last_failure_at: string | null
  pending_task_count: number
  model_call_count: number
  budget_status: 'READY' | 'BLOCKED'
  budget_remaining_calls: number
  order_count: number
  fill_count: number
  evaluation_subject_count: number
  mature_evaluation_count: number
}

export const alphaguardOperationsApi = {
  overview() {
    return ApiClient.get<OperationsOverview>('/api/alphaguard/operations/overview')
  },
  readiness() {
    return ApiClient.get<SystemReadiness>('/api/alphaguard/operations/readiness')
  },
  services() {
    return ApiClient.get<Items<ServiceHealth>>('/api/alphaguard/operations/services')
  },
  dataReadiness() {
    return ApiClient.get<Items<DataReadiness>>('/api/alphaguard/operations/data-readiness')
  },
  jobs() {
    return ApiClient.get<Items<JobHealth> & { allowed_manual_jobs: string[] }>(
      '/api/alphaguard/operations/jobs'
    )
  },
  alerts(params?: { status?: string; severity?: string }) {
    return ApiClient.get<Items<OperationalAlert>>('/api/alphaguard/operations/alerts', params)
  },
  versions() {
    return ApiClient.get<Record<string, unknown>>('/api/alphaguard/operations/versions')
  },
  integrity() {
    return ApiClient.get<Record<string, unknown>>('/api/alphaguard/operations/integrity')
  },
  mvpAcceptance() {
    return ApiClient.get<MvpAcceptanceReport>('/api/alphaguard/operations/mvp-acceptance')
  },
  runJob(jobName: string, payload: { as_of_trade_date?: string; idempotency_key?: string } = {}) {
    return ApiClient.post(
      `/api/alphaguard/operations/jobs/${encodeURIComponent(jobName)}/run`,
      payload
    )
  },
  acknowledgeAlert(alertId: string) {
    return ApiClient.post<OperationalAlert>(
      `/api/alphaguard/operations/alerts/${encodeURIComponent(alertId)}/acknowledge`
    )
  },
  resolveAlert(alertId: string, resolutionNote: string) {
    return ApiClient.post<OperationalAlert>(
      `/api/alphaguard/operations/alerts/${encodeURIComponent(alertId)}/resolve`,
      { resolution_note: resolutionNote }
    )
  }
}
