# v2.1 架构图

## 📊 配置层次架构

### 1. 配置优先级流程图

```mermaid
graph TB
    Start[开始查询配置]
    
    subgraph "工具绑定查询"
        Q1{workflow_id + node_id?}
        Q2{workflow_id?}
        Q3[全局配置]
        
        R1[节点级别工具]
        R2[工作流级别工具]
        R3[全局工具]
    end
    
    Start --> Q1
    Q1 -->|是| R1
    Q1 -->|否| Q2
    Q2 -->|是| R2
    Q2 -->|否| Q3
    Q3 --> R3
    
    style R1 fill:#4caf50
    style R2 fill:#ff9800
    style R3 fill:#2196f3
```

---

### 2. 提示词查询优先级

```mermaid
graph TB
    Start[开始查询提示词]
    
    Q1{user_id + workflow_id + node_id?}
    Q2{user_id + workflow_id?}
    Q3{user_id?}
    Q4{workflow_id + node_id?}
    Q5{workflow_id?}
    Q6[Agent 全局配置]
    Q7[代码默认值]
    
    R1[用户节点级别]
    R2[用户工作流级别]
    R3[用户全局级别]
    R4[工作流节点级别]
    R5[工作流级别]
    R6[全局级别]
    R7[默认提示词]
    
    Start --> Q1
    Q1 -->|是| R1
    Q1 -->|否| Q2
    Q2 -->|是| R2
    Q2 -->|否| Q3
    Q3 -->|是| R3
    Q3 -->|否| Q4
    Q4 -->|是| R4
    Q4 -->|否| Q5
    Q5 -->|是| R5
    Q5 -->|否| Q6
    Q6 --> R6
    R6 -->|未找到| Q7
    Q7 --> R7
    
    style R1 fill:#4caf50
    style R2 fill:#8bc34a
    style R3 fill:#cddc39
    style R4 fill:#ff9800
    style R5 fill:#ff5722
    style R6 fill:#2196f3
    style R7 fill:#9e9e9e
```

---

## 🗄️ 数据库关系图

### 1. 工作流上下文配置关系

```mermaid
erDiagram
    workflow_definitions ||--o{ workflow_agent_bindings : "包含"
    workflow_definitions ||--o{ tool_agent_bindings : "使用"
    
    agent_configs ||--o{ workflow_agent_bindings : "被引用"
    agent_configs ||--o{ tool_agent_bindings : "被引用"
    agent_configs ||--o{ prompt_templates : "使用"
    
    tool_configs ||--o{ tool_agent_bindings : "被绑定"
    
    prompt_templates ||--o{ workflow_agent_bindings : "被引用"
    prompt_templates ||--o{ user_template_configs : "被选择"
    
    users ||--o{ user_template_configs : "配置"
    
    workflow_definitions {
        string workflow_id PK
        string name
        string description
    }
    
    workflow_agent_bindings {
        ObjectId _id PK
        string workflow_id FK
        string agent_id FK
        string node_id
        object config_override
        ObjectId prompt_template_id FK
    }
    
    tool_agent_bindings {
        ObjectId _id PK
        string workflow_id FK
        string node_id
        string agent_id FK
        string tool_id FK
        int priority
    }
    
    agent_configs {
        string agent_id PK
        string name
        object config
    }
    
    tool_configs {
        string tool_id PK
        string name
        object config
    }
    
    prompt_templates {
        ObjectId _id PK
        string agent_id FK
        string template_name
        object content
    }
    
    user_template_configs {
        ObjectId _id PK
        ObjectId user_id FK
        string workflow_id FK
        string node_id
        string agent_id FK
        ObjectId template_id FK
    }
    
    users {
        ObjectId _id PK
        string username
    }
```

---

### 2. 配置查询流程

```mermaid
sequenceDiagram
    participant WF as 工作流引擎
    participant GB as GraphBuilder
    participant BM as BindingManager
    participant DB as MongoDB
    
    WF->>GB: 创建工作流图
    GB->>GB: 遍历节点定义
    
    loop 每个 Agent 节点
        GB->>BM: get_tools_for_agent(agent_id, workflow_id, node_id)
        BM->>DB: 查询 tool_agent_bindings
        Note over BM,DB: 优先级：节点 > 工作流 > 全局
        DB-->>BM: 返回工具列表
        BM-->>GB: 返回工具 IDs
        
        GB->>BM: get_workflow_agent_config(workflow_id, agent_id, node_id)
        BM->>DB: 查询 workflow_agent_bindings
        DB-->>BM: 返回配置覆盖
        BM-->>GB: 返回 config_override 和 prompt_template_id
        
        GB->>GB: 合并配置（节点 > 工作流 > 全局）
        GB->>GB: 创建 Agent 实例
    end
    
    GB-->>WF: 返回工作流图
```

---

## 🔄 配置继承关系

### 1. 工具绑定继承

```mermaid
graph LR
    subgraph "全局配置"
        G[agent_id: market_analyst_v2<br/>tools: [tool1, tool2]]
    end
    
    subgraph "工作流配置"
        W1[workflow_id: stock_analysis<br/>agent_id: market_analyst_v2<br/>tools: [tool3, tool4]]
        W2[workflow_id: trade_review<br/>agent_id: market_analyst_v2<br/>tools: [tool5]]
    end
    
    subgraph "节点配置"
        N1[workflow_id: stock_analysis<br/>node_id: market_node<br/>agent_id: market_analyst_v2<br/>tools: [tool6]]
    end
    
    G -.降级.-> W1
    G -.降级.-> W2
    W1 -.降级.-> N1
    
    style G fill:#2196f3
    style W1 fill:#ff9800
    style W2 fill:#ff9800
    style N1 fill:#4caf50
```

---

### 2. 提示词继承

```mermaid
graph LR
    subgraph "全局提示词"
        GP[agent_id: market_analyst_v2<br/>template: default<br/>is_system: true]
    end
    
    subgraph "工作流提示词"
        WP1[workflow_id: stock_analysis<br/>agent_id: market_analyst_v2<br/>template: aggressive]
        WP2[workflow_id: trade_review<br/>agent_id: market_analyst_v2<br/>template: conservative]
    end
    
    subgraph "用户提示词"
        UP1[user_id: user_123<br/>workflow_id: stock_analysis<br/>agent_id: market_analyst_v2<br/>template: my_custom]
    end
    
    GP -.降级.-> WP1
    GP -.降级.-> WP2
    WP1 -.降级.-> UP1
    
    style GP fill:#2196f3
    style WP1 fill:#ff9800
    style WP2 fill:#ff9800
    style UP1 fill:#4caf50
```

---

## 🎯 使用场景示例

### 场景 1：同一 Agent 在不同工作流中的配置

```mermaid
graph TB
    subgraph "Agent: market_analyst_v2"
        A[全局配置<br/>tools: [get_stock_data]<br/>prompt: default]
    end
    
    subgraph "工作流 A: 股票分析"
        WA[工作流配置<br/>tools: [get_stock_data, get_technical_indicators]<br/>prompt: aggressive<br/>temperature: 0.9]
        
        NA1[节点 1: 技术分析<br/>tools: [get_technical_indicators]<br/>prompt: technical_focus]
        
        NA2[节点 2: 基本面分析<br/>tools: [get_fundamentals]<br/>prompt: fundamental_focus]
    end
    
    subgraph "工作流 B: 交易复盘"
        WB[工作流配置<br/>tools: [get_trade_records]<br/>prompt: conservative<br/>temperature: 0.3]
    end
    
    A -.降级.-> WA
    A -.降级.-> WB
    WA -.降级.-> NA1
    WA -.降级.-> NA2
    
    style A fill:#2196f3
    style WA fill:#ff9800
    style WB fill:#ff9800
    style NA1 fill:#4caf50
    style NA2 fill:#4caf50
```

---

### 场景 2：用户自定义配置覆盖

```mermaid
graph TB
    subgraph "系统配置"
        SC[工作流: stock_analysis<br/>agent: market_analyst_v2<br/>prompt: aggressive]
    end
    
    subgraph "用户配置"
        UC1[用户 A<br/>workflow: stock_analysis<br/>agent: market_analyst_v2<br/>prompt: my_aggressive_v2]
        
        UC2[用户 B<br/>workflow: stock_analysis<br/>agent: market_analyst_v2<br/>prompt: my_conservative]
    end
    
    SC -.被覆盖.-> UC1
    SC -.被覆盖.-> UC2
    
    style SC fill:#ff9800
    style UC1 fill:#4caf50
    style UC2 fill:#4caf50
```

---

**创建日期**: 2026-01-09  
**最后更新**: 2026-01-09  
**维护者**: TradingAgents-CN Pro Team

