from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PANEL_PATH = (
    ROOT
    / "frontend/src/components/alphaguard/ModelConfigurationPanel.vue"
)


def _panel() -> str:
    return PANEL_PATH.read_text(encoding="utf-8")


def test_model_configuration_has_one_visible_workflow():
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")
    panel = _panel()

    assert operations.count("<ModelConfigurationPanel") == 1
    assert "activeModelTab" not in operations
    assert "showAdvancedModelSettings" not in operations
    assert "<el-tabs" not in panel
    for label in (
        "模型服务",
        "API 密钥",
        "决策模型",
        "连接检测",
        "普通决策模型",
        "风险终审模型",
    ):
        assert label in panel


def test_settings_page_has_no_legacy_model_or_credential_workflow():
    settings = (
        ROOT / "frontend/src/views/Settings/ConfigManagement.vue"
    ).read_text(encoding="utf-8")

    assert '<AlphaGuardOperations models-only embedded />' in settings
    for removed_contract in (
        "legacy-model-catalog",
        "legacy-providers",
        "legacy-llm",
        "legacy-api-keys",
        "ProviderDialog",
        "LLMConfigDialog",
        "migrateFromEnv",
    ):
        assert removed_contract not in settings


def test_technical_records_are_collapsed_and_read_only():
    panel = _panel()
    technical_start = panel.index(
        '<el-collapse v-model="advancedSections"'
    )
    technical_end = panel.index("</el-collapse>", technical_start)
    technical = panel[technical_start:technical_end]

    assert "const advancedSections = ref<string[]>([])" in panel
    assert "<el-form" not in technical
    assert "@click=" not in technical
    assert "模型服务版本" in technical
    assert "模型角色绑定" in technical
    assert "API 密钥记录" in technical
    assert "近期调用记录" in technical


def test_profile_status_is_scoped_to_exact_endpoint_version():
    panel = _panel()
    profile_projection = panel[
        panel.index("const endpointProfiles = computed"):
        panel.index("const endpointCredentialRecords = computed")
    ]

    assert "item.endpoint_profile_id === selectedEndpoint.value?.endpoint_profile_id" in profile_projection
    assert "item.endpoint_profile_version === selectedEndpoint.value?.profile_version" in profile_projection
    assert "new Map((modelStatus.value?.profiles" not in panel


def test_destructive_actions_have_confirmation_and_result_feedback():
    panel = _panel()

    assert 'aria-label="停用当前服务"' in panel
    assert 'aria-label="撤销当前密钥"' in panel
    assert "await ElMessageBox.confirm" in panel
    assert "模型服务已停用，历史配置仍保留。" in panel
    assert "API 密钥已撤销。" in panel
    assert "停用模型服务失败" in panel
    assert "撤销 API 密钥失败" in panel


def test_failed_credential_replacement_keeps_old_credential_visible():
    panel = _panel()

    assert "const replacingCredential = Boolean(currentCredential.value)" in panel
    assert "replacingCredential && !response.data.replaced" in panel
    assert "新 API 密钥验证未通过，原密钥已保留且仍可使用。" in panel


def test_unreadable_credential_remains_replaceable_and_revocable():
    panel = _panel()
    current_projection = panel[
        panel.index("const currentCredential = computed"):
        panel.index("const endpointProfiles = computed")
    ]

    assert "item.configured" not in current_projection
    assert "const credentialReady = computed" in current_projection
    assert "安全存储当前不可读；可以更换或撤销" in current_projection
    assert 'v-if="currentCredential"' in panel
    assert "currentCredential.value\n      ? await alphaguardModelsApi.replaceCredential" in panel


def test_authenticated_degraded_credential_can_continue_model_bootstrap():
    panel = _panel()
    credential_projection = panel[
        panel.index("const credentialReady = computed"):
        panel.index("const endpointProfiles = computed")
    ]

    assert "currentCredential.value?.configured" in credential_projection
    assert "currentCredential.value.status !== 'DEGRADED'" not in credential_projection
    assert "const credentialNeedsModelSetup = computed" in credential_projection
    assert "'MODEL_NOT_FOUND'" in credential_projection
    assert "已保存，待配置" in credential_projection
    assert "认证和服务访问已通过，请继续添加决策模型" in credential_projection
    assert ':disabled="!canManage || !credentialReady"' in panel
    assert "if (!credentialReady.value) return '请先添加或修复 API 密钥。'" in panel
    assert "服务商拒绝读取模型列表" in panel


def test_partial_loads_and_confirmation_errors_are_visible():
    panel = _panel()

    load_section = panel[panel.index("async function load()"):
                         panel.index("function resetProviderForm()")]
    assert "Promise.allSettled" in load_section
    assert "部分状态未能读取" in load_section
    assert "endpointModels.value = []" in load_section
    assert "showActionError('切换模型服务失败', error)" in load_section
    assert "function isDialogCancellation" in panel
    assert "showActionError('打开停用确认失败', error)" in panel
    assert "showActionError('打开撤销确认失败', error)" in panel
    assert "showActionError('打开检测确认失败', error)" in panel


def test_stale_capability_and_saved_model_state_are_unambiguous():
    panel = _panel()
    api = (ROOT / "frontend/src/api/alphaguardModels.ts").read_text(
        encoding="utf-8"
    )

    assert "capability_stale?: boolean" in api
    assert "API 密钥已重新验证，旧检测结果仍保留在审计中" in panel
    assert "当前需要：重新检测模型" in panel
    assert "capabilityActionLabel" in panel
    assert "{{ capabilityActionLabel }}" in panel
    assert 'v-if="canManage && !assignmentsMatchSelections"' in panel
    assert 'class="saved-state" role="status"' in panel
    assert "当前模型设置已保存。" not in panel


def test_capability_errors_explain_quota_and_invalid_json_schema_results():
    panel = _panel()
    status_service = (
        ROOT / "app/services/alphaguard/model_runtime_status_service.py"
    ).read_text(encoding="utf-8")

    assert "BUDGET_BLOCKED: '服务商额度不足'" in panel
    assert "PROVIDER_QUOTA_EXHAUSTED: '服务商额度不足'" in panel
    assert "服务商额度不足，请充值或选择额度要求更低的模型。" in panel
    assert "请改用结构化输出能力更稳定的模型。" in status_service
    assert "validation_error_count" in status_service


def test_capability_retry_reports_role_results_instead_of_false_success():
    panel = _panel()
    api = (ROOT / "frontend/src/api/alphaguardModels.ts").read_text(
        encoding="utf-8"
    )
    run_check = panel[
        panel.index("async function runCapabilityChecks()"):
        panel.index("function isDialogCancellation")
    ]

    assert "interface ModelCapabilityCheckResult" in api
    assert "ApiClient.post<ModelCapabilityCheckResult>" in api
    assert "response.data.status" in run_check
    assert "result.status !== 'READY'" in run_check
    assert "检测已执行，但未全部通过" in run_check
    assert "两个模型均可用" in run_check
    assert "ElMessage.success('连接检测已完成。')" not in run_check
    assert "配置不变时，重复检测通常会得到相同结果" in panel
    assert "本次结果很可能相同" in run_check


def test_failed_first_endpoint_validation_reuses_same_lineage_for_retry():
    panel = _panel()

    branch_start = panel.index(
        "if (validation.data.url_validation_status !== 'PASS')"
    )
    failure_branch = panel[
        branch_start:panel.index("return", branch_start)
    ]
    assert "selectedEndpointIdentity.value = endpointIdentity(validation.data)" in failure_branch
    assert "providerEditing.value = true" in failure_branch


def test_api_key_never_uses_browser_persistence_or_reveal_control():
    panel = _panel()

    assert 'type="password"' in panel
    assert 'autocomplete="new-password"' in panel
    assert "credentialApiKey.value = ''" in panel
    assert "show-password" not in panel
    assert "localStorage.setItem" not in panel
    assert "sessionStorage.setItem" not in panel
    assert "document.cookie" not in panel


def test_element_plus_controls_use_current_value_contract():
    panel = _panel()

    assert '<el-radio value="SELF_HOSTED">' in panel
    assert '<el-radio value="PROVIDER_PUBLISHED">' in panel
    assert "<el-radio-button" not in panel
    assert "label=\"NORMAL_TRADER\"" not in panel
    assert "label=\"TOP_RISK_REVIEWER\"" not in panel


def test_model_name_uses_explicit_read_only_provider_dropdown():
    panel = _panel()
    api = (ROOT / "frontend/src/api/alphaguardModels.ts").read_text(
        encoding="utf-8"
    )

    model_field = panel[
        panel.index('<el-form-item label="服务商模型名称">'):
        panel.index('<el-form-item label="用途">')
    ]
    open_dialog = panel[
        panel.index("function openModelDialog()"):
        panel.index("async function refreshModelOptions()")
    ]
    refresh = panel[
        panel.index("async function refreshModelOptions()"):
        panel.index("async function saveModel()")
    ]

    assert "<el-select" in model_field
    assert "filterable" in model_field
    assert "allow-create" in model_field
    assert 'placeholder="选择或输入模型名称"' in model_field
    assert 'aria-label="读取服务商模型"' in model_field
    assert "endpointModelOptions" not in open_dialog
    assert "alphaguardModelsApi.endpointModelOptions" in refresh
    assert "endpoint_profile_version: endpoint.profile_version" in refresh
    assert "credential_id: credential.credential_id" in refresh
    assert '"/models/options"' not in api
    assert "/models/options`" in api
    assert "discoverEndpointModels" not in refresh


def test_existing_remote_model_creates_next_immutable_version_or_reuses():
    panel = _panel()
    save_model = panel[
        panel.index("async function saveModel()"):
        panel.index("async function saveDecisionModels()")
    ]

    assert "sameNameModels.find(modelMatchesForm)" in save_model
    assert "endpoint_model_id: latest.endpoint_model_id" in save_model
    assert "model_version: nextModelVersion(sameNameModels)" in save_model
    assert "const existingPrice = matchingPrice(model)" in save_model
    assert "if (!existingPrice)" in save_model
