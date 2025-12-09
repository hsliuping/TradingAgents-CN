export interface MCPServerConfig {
  command: string;
  args: string[];
  env?: Record<string, string>;
  [key: string]: any;
}

export interface MCPConnector {
  id: string;
  name: string;
  config: MCPServerConfig;
  enabled: boolean;
  status: 'healthy' | 'degraded' | 'unreachable' | 'unknown' | 'stopped';
}

export interface MCPUpdatePayload {
  mcpServers: Record<string, MCPServerConfig>;
}

export interface MCPHealthResult {
  status: MCPConnector['status'];
  latency_ms?: number;
  checked_at?: string;
  message?: string;
}

export interface MCPTool {
  id: string;
  name: string;
  description: string;
  serverName: string;
  serverId: string;
  status: 'healthy' | 'unhealthy';
  schema?: any;
}
