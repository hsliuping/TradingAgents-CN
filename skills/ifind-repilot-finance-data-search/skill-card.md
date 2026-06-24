## Description: <br>
使用自然语言查询金融数据，支持A股股票、基金、期货等上市品种，覆盖基本资料、财务数据、日频行情信息、持仓信息及各类分析指标等数据，也支持宏观经济数据。 <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[wenzisay](https://clawhub.ai/user/wenzisay) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
External users and agents use this skill to query iFinD/Repilot financial and macroeconomic data with natural-language prompts. It is intended for retrieving and summarizing returned data, not for inventing financial figures when the service fails or returns no result. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: The skill stores a finance API token locally and sends that token with natural-language queries. <br>
Mitigation: Use a revocable, limited token where available, keep the local config file private, and delete ~/.config/ifind-repilot/config.json when the skill is no longer needed. <br>
Risk: The API base URL can be changed, which could send tokens and queries to an untrusted host. <br>
Mitigation: Use the default iFinD/Repilot host unless a trusted operator explicitly provides another endpoint. <br>
Risk: Returned financial data can be empty, unavailable, permission-limited, or rate-limited. <br>
Mitigation: Report the returned error or empty result directly, avoid fabricating data, and retry only with a revised query when the skill guidance allows it. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/wenzisay/ifind-repilot-finance-data-search) <br>
- [iFinD/Repilot platform](https://repilot.51ifind.com/) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, shell commands, configuration, guidance] <br>
**Output Format:** [Text and Markdown tables returned from authenticated finance queries, with setup guidance and shell commands when configuration is needed.] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Requires python3 and a configured iFinD/Repilot auth token; results depend on service availability, account permissions, and usage limits.] <br>

## Skill Version(s): <br>
1.0.1 (source: server release evidence) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
