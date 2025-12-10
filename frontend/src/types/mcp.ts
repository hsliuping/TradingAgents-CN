/**
 * MCP 服务器类型
 */
export type MCPServerType = 'stdio' | 'http' | 'streamable-http';

/**
 * 健康检查配置
 */
export interface HealthCheckConfig {
  enabled: boolean;
  interval: number;  // 检查间隔（秒）
  timeout: number;   // 超时时间（秒）
}

/**
 * MCP 服务器配置
 */
export interface MCPServerConfig {
  type: MCPServerType;
  // stdio 模式字段
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  // HTTP 模式字段
  url?: string;
  headers?: Record<string, string>;
  // 通用字段
  description?: string;
  healthCheck?: HealthCheckConfig;
  [key: string]: any;
}

/**
 * 服务器健康信息
 */
export interface ServerHealthInfo {
  status: string;
  lastCheck?: string;
  error?: string;
  latencyMs?: number;
}

/**
 * MCP 连接器
 */
export interface MCPConnector {
  id: string;
  name: string;
  type: MCPServerType;
  config: MCPServerConfig;
  enabled: boolean;
  status: 'healthy' | 'degraded' | 'unreachable' | 'unknown' | 'stopped' | 'disabled' | 'unavailable';
  healthInfo?: ServerHealthInfo;
}

/**
 * MCP 更新负载
 */
export interface MCPUpdatePayload {
  mcpServers: Record<string, MCPServerConfig>;
}

/**
 * MCP 健康检查结果
 */
export interface MCPHealthResult {
  status: MCPConnector['status'];
  latency_ms?: number;
  checked_at?: string;
  message?: string;
}

/**
 * MCP 工具
 */
export interface MCPTool {
  id: string;
  name: string;
  description: string;
  serverName: string;
  serverId: string;
  status: 'healthy' | 'degraded' | 'unreachable' | 'unknown' | 'stopped';
  available: boolean;
  schema?: any;
  error?: string;
}

/**
 * 服务器统计信息
 */
export interface ServerStats {
  total: number;
  available: number;
  status: string;
}

/**
 * 工具列表响应
 */
export interface MCPToolsResponse {
  success: boolean;
  data: MCPTool[];
  serverStats?: Record<string, ServerStats>;
  message?: string;
}

/**
 * 连接器列表响应
 */
export interface MCPConnectorsResponse {
  success: boolean;
  data: MCPConnector[];
}

/**
 * 切换响应
 */
export interface MCPToggleResponse {
  success: boolean;
  data: {
    enabled: boolean;
    status: string;
  };
}
