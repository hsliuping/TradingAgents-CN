# 新闻过滤方案设计文档

## 🎯 目标

为TradingAgents系统设计并实现一个高效的新闻过滤机制，解决东方财富新闻API返回低质量、不相关新闻的问题，提高新闻分析师的分析质量。

## 🔍 可行方案分析

### 方案1: 基于规则的过滤器 (推荐 - 立即可行)

**优势:**
- ✅ 无需额外依赖，基于现有Python库
- ✅ 实现简单，维护成本低
- ✅ 执行速度快，几乎无延迟
- ✅ 可解释性强，规则透明
- ✅ 资源消耗极低

**实现方案:**
```python
class NewsRelevanceFilter:
    def __init__(self, stock_code: str, company_name: str):
        self.stock_code = stock_code
        self.company_name = company_name
        self.exclude_keywords = [
            'etf', '指数基金', '基金', '指数', 'index', 'fund',
            '权重股', '成分股', '板块', '概念股'
        ]
        self.include_keywords = [
            '业绩', '财报', '公告', '重组', '并购', '分红',
            '高管', '董事', '股东', '增持', '减持', '回购'
        ]
    
    def calculate_relevance_score(self, title: str, content: str) -> float:
        """计算新闻相关性评分 (0-100)"""
        score = 0
        title_lower = title.lower()
        content_lower = content.lower()
        
        # 直接提及公司 (+40分)
        if self.company_name in title:
            score += 40
        elif self.company_name in content:
            score += 20
            
        # 直接提及股票代码 (+30分)
        if self.stock_code in title:
            score += 30
        elif self.stock_code in content:
            score += 15
            
        # 包含公司相关关键词 (+20分)
        for keyword in self.include_keywords:
            if keyword in title_lower:
                score += 10
            elif keyword in content_lower:
                score += 5
                
        # 排除不相关内容 (-30分)
        for keyword in self.exclude_keywords:
            if keyword in title_lower:
                score -= 30
            elif keyword in content_lower:
                score -= 15
                
        return max(0, min(100, score))
    
    def filter_news(self, news_df: pd.DataFrame, min_score: float = 30) -> pd.DataFrame:
        """过滤新闻，返回相关性评分高于阈值的新闻"""
        filtered_news = []
        
        for _, row in news_df.iterrows():
            title = row.get('新闻标题', '')
            content = row.get('新闻内容', '')
            
            score = self.calculate_relevance_score(title, content)
            
            if score >= min_score:
                row_dict = row.to_dict()
                row_dict['relevance_score'] = score
                filtered_news.append(row_dict)
        
        # 按相关性评分排序
        filtered_df = pd.DataFrame(filtered_news)
        if not filtered_df.empty:
            filtered_df = filtered_df.sort_values('relevance_score', ascending=False)
            
        return filtered_df
```

### 方案2: 轻量级本地模型 (中期方案)

**使用sentence-transformers进行语义相似度计算:**

```python
# 需要添加到requirements.txt
# sentence-transformers>=2.2.0

from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticNewsFilter:
    def __init__(self, stock_code: str, company_name: str):
        self.stock_code = stock_code
        self.company_name = company_name
        # 使用中文优化的轻量级模型
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # 定义目标语义
        self.target_semantics = [
            f"{company_name}公司新闻",
            f"{company_name}业绩财报",
            f"{company_name}重大公告",
            f"{stock_code}股票新闻"
        ]
        self.target_embeddings = self.model.encode(self.target_semantics)
    
    def calculate_semantic_similarity(self, text: str) -> float:
        """计算文本与目标语义的相似度"""
        text_embedding = self.model.encode([text])
        similarities = np.dot(text_embedding, self.target_embeddings.T)
        return float(np.max(similarities))
    
    def filter_news_semantic(self, news_df: pd.DataFrame, threshold: float = 0.3) -> pd.DataFrame:
        """基于语义相似度过滤新闻"""
        filtered_news = []
        
        for _, row in news_df.iterrows():
            title = row.get('新闻标题', '')
            content = row.get('新闻内容', '')
            
            # 计算标题和内容的语义相似度
            title_sim = self.calculate_semantic_similarity(title)
            content_sim = self.calculate_semantic_similarity(content[:200])  # 限制内容长度
            
            max_similarity = max(title_sim, content_sim)
            
            if max_similarity >= threshold:
                row_dict = row.to_dict()
                row_dict['semantic_score'] = max_similarity
                filtered_news.append(row_dict)
        
        filtered_df = pd.DataFrame(filtered_news)
        if not filtered_df.empty:
            filtered_df = filtered_df.sort_values('semantic_score', ascending=False)
            
        return filtered_df
```

### 方案3: 本地小模型分类 (长期方案)

**使用transformers库的中文分类模型:**

```python
# 需要添加到requirements.txt
# transformers>=4.30.0
# torch>=2.0.0

from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

class LocalModelNewsClassifier:
    def __init__(self):
        # 使用中文文本分类模型
        self.classifier = pipeline(
            "text-classification",
            model="uer/roberta-base-finetuned-chinanews-chinese",
            tokenizer="uer/roberta-base-finetuned-chinanews-chinese"
        )
    
    def classify_news_relevance(self, title: str, content: str, company_name: str) -> dict:
        """分类新闻相关性"""
        # 构建分类文本
        text = f"公司：{company_name}。新闻：{title}。{content[:100]}"
        
        # 进行分类
        result = self.classifier(text)
        
        return {
            'is_relevant': result[0]['label'] == 'RELEVANT',
            'confidence': result[0]['score'],
            'classification': result[0]['label']
        }
```

### 方案4: 混合过滤策略 (最优方案)

**结合规则过滤和语义分析:**

```python
class HybridNewsFilter:
    def __init__(self, stock_code: str, company_name: str):
        self.rule_filter = NewsRelevanceFilter(stock_code, company_name)
        self.semantic_filter = SemanticNewsFilter(stock_code, company_name)
    
    def comprehensive_filter(self, news_df: pd.DataFrame) -> pd.DataFrame:
        """综合过滤策略"""
        # 第一步：规则过滤（快速筛选）
        rule_filtered = self.rule_filter.filter_news(news_df, min_score=20)
        
        if rule_filtered.empty:
            return rule_filtered
        
        # 第二步：语义过滤（精确筛选）
        semantic_filtered = self.semantic_filter.filter_news_semantic(
            rule_filtered, threshold=0.25
        )
        
        # 第三步：综合评分
        if not semantic_filtered.empty:
            semantic_filtered['final_score'] = (
                semantic_filtered['relevance_score'] * 0.6 + 
                semantic_filtered['semantic_score'] * 100 * 0.4
            )
            semantic_filtered = semantic_filtered.sort_values('final_score', ascending=False)
        
        return semantic_filtered
```

## 🚀 实施计划

### 阶段1: 立即实施 (1-2天)
1. **实现基于规则的过滤器**
2. **集成到现有新闻获取流程**
3. **添加过滤日志和统计**

### 阶段2: 中期优化 (1周)
1. **添加sentence-transformers依赖**
2. **实现语义相似度过滤**
3. **混合过滤策略测试**

### 阶段3: 长期改进 (2-3周)
1. **本地分类模型集成**
2. **过滤效果评估体系**
3. **自适应阈值调整**

## 📊 性能对比

| 方案 | 实施难度 | 资源消耗 | 过滤精度 | 执行速度 | 推荐度 |
|------|----------|----------|----------|----------|--------|
| 规则过滤 | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 语义相似度 | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 本地分类模型 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| 混合策略 | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## 🔧 集成方案

### 修改现有代码

**1. 修改 `realtime_news_utils.py`:**
```python
# 在get_realtime_stock_news函数中添加过滤逻辑
def get_realtime_stock_news(ticker: str, curr_date: str, hours_back: int = 6):
    # ... 现有代码 ...
    
    # 获取新闻后添加过滤
    if news_df is not None and not news_df.empty:
        # 获取公司名称
        company_name = get_company_name(ticker)  # 需要实现
        
        # 创建过滤器
        filter = NewsRelevanceFilter(ticker, company_name)
        
        # 过滤新闻
        filtered_df = filter.filter_news(news_df, min_score=30)
        
        logger.info(f"[新闻过滤] 原始新闻: {len(news_df)}条, 过滤后: {len(filtered_df)}条")
        
        if not filtered_df.empty:
            news_df = filtered_df
        else:
            logger.warning(f"[新闻过滤] 所有新闻被过滤，保留原始数据")
    
    # ... 继续现有逻辑 ...
```

**2. 添加公司名称映射:**
```python
# 创建股票代码到公司名称的映射
STOCK_COMPANY_MAPPING = {
    '600036': '招商银行',
    '000858': '五粮液',
    '000001': '平安银行',
    # ... 更多映射
}

def get_company_name(ticker: str) -> str:
    """获取股票对应的公司名称"""
    return STOCK_COMPANY_MAPPING.get(ticker, f"股票{ticker}")
```

## 📈 预期效果

### 过滤前 (招商银行600036)
```
新闻标题:
1. 上证180ETF指数基金（530280）自带杠铃策略
2. A500ETF基金(512050多股涨停
3. 银行ETF指数(512730多只成分股上涨
```

### 过滤后 (预期)
```
新闻标题:
1. 招商银行发布2024年第三季度业绩报告
2. 招商银行董事会决议公告
3. 招商银行获得监管批准设立理财子公司
```

## 🎯 总结

**推荐方案**: 先实施**基于规则的过滤器**，后续逐步添加**语义相似度过滤**，最终形成**混合过滤策略**。

**核心优势**:
- 🚀 立即可用，无需额外依赖
- 💰 资源消耗低，执行速度快
- 🎯 针对性强，解决当前问题
- 🔧 易于维护和调试
- 📈 显著提升新闻分析质量

这个方案可以有效解决当前东方财富新闻质量问题，让新闻分析师生成真正的"新闻分析报告"而非"综合投资分析报告"。