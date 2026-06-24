## Description: <br>
iFinD投研-金融资讯搜索 helps an agent semantically search market-wide financial news, public sentiment, market updates, industry activity, and company news through the iFinD/Repilot service. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[wenzisay](https://clawhub.ai/user/wenzisay) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
External users and financial research agents use this skill to retrieve relevant financial-news snippets from natural-language questions, optionally constrained by a date range. The agent can then summarize titles, sources, dates, links, and important details without fabricating market information. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: Search queries and the configured service token are sent over the network to the iFinD/Repilot service. <br>
Mitigation: Install only when the user trusts the iFinD/Repilot service and is comfortable sending those queries and credentials to that provider. <br>
Risk: The token is stored in ~/.config/ifind-repilot/config.json. <br>
Mitigation: Treat the config file as secret-bearing local state and avoid sharing logs, archives, or machine images that include it. <br>
Risk: The helper script has an under-disclosed --set-url option that can redirect the configured token to another endpoint. <br>
Mitigation: Keep the default provider URL and use --set-url only for endpoints the user controls and trusts. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/wenzisay/ifind-repilot-news-search) <br>
- [Publisher profile](https://clawhub.ai/user/wenzisay) <br>
- [iFinD/Repilot platform](https://repilot.51ifind.com/) <br>


## Skill Output: <br>
**Output Type(s):** [Text, JSON, Shell commands, Configuration, Guidance] <br>
**Output Format:** [JSON search results from the helper script, commonly reorganized by the agent into concise Markdown or text summaries.] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Requires python3 and a locally configured iFinD/Repilot auth token; supports optional start and end timestamps in YYYY-MM-DDTHH:MM:SS format.] <br>

## Skill Version(s): <br>
1.0.1 (source: server release evidence) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
