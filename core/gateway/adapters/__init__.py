"""
Gateway 适配器包

每个 IM 平台实现一个适配器子类，负责：
1. 验证 Webhook 签名
2. 解析平台消息为 GatewayMessage
3. 将 GatewayResponse 发送到平台
"""

