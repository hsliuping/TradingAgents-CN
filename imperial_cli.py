#!/usr/bin/env python3
"""
帝国AI命令行工具 - Phase 4G-G5 基础监控和工具
Imperial AI CLI Tool - Phase 4G-G5 Basic Monitoring and Tools

提供命令行界面来操作帝国AI协作系统，包括分析、监控和管理功能。
"""

import asyncio
import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

# 导入核心组件
try:
    from imperial_agents.core.collaboration_system import (
        RealDataCollaborationSystem,
        CollaborationMode,
        ConflictLevel
    )
    from tradingagents.agents.utils.agent_utils import Toolkit
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保已正确安装所有依赖包")
    sys.exit(1)


class ImperialAICLI:
    """帝国AI命令行界面"""
    
    def __init__(self):
        """初始化CLI"""
        self.collaboration_system = None
        self.config = self._load_default_config()
        
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            'llm_provider': 'fake',  # 默认使用模拟LLM，实际使用时需要配置
            'default_mode': 'parallel',
            'timeout': 30,
            'log_level': 'INFO',
            'output_format': 'text'
        }
    
    def _initialize_system(self):
        """初始化协作系统"""
        if self.collaboration_system is None:
            print("🔧 [系统初始化] 正在初始化帝国AI协作系统...")
            
            # 使用模拟LLM（实际使用时需要配置真实LLM）
            from langchain_community.llms.fake import FakeListLLM
            responses = [
                "技术分析: 买入信号, 置信度80%",
                "222法则验证: 符合条件, 建议持有, 置信度75%", 
                "风险评估: 中等风险, 建议谨慎操作, 置信度70%"
            ]
            llm = FakeListLLM(responses=responses)
            toolkit = Toolkit()
            
            self.collaboration_system = RealDataCollaborationSystem(llm, toolkit)
            print("✅ [系统初始化] 帝国AI协作系统初始化完成")
    
    async def analyze_stock(self, symbol: str, mode: str = 'parallel', output_format: str = 'text') -> bool:
        """
        执行股票分析
        
        Args:
            symbol: 股票代码
            mode: 协作模式
            output_format: 输出格式
            
        Returns:
            bool: 是否成功
        """
        self._initialize_system()
        
        try:
            print(f"🔍 [股票分析] 开始分析 {symbol} (模式: {mode})")
            start_time = time.time()
            
            # 转换协作模式
            collaboration_mode = {
                'parallel': CollaborationMode.PARALLEL,
                'sequential': CollaborationMode.SEQUENTIAL,
                'emergency': CollaborationMode.EMERGENCY
            }.get(mode, CollaborationMode.PARALLEL)
            
            # 执行协作分析
            result = await self.collaboration_system.analyze_stock_collaboration(
                symbol=symbol,
                mode=collaboration_mode
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 输出结果
            if output_format == 'json':
                self._output_json_result(result)
            else:
                self._output_text_result(result, execution_time)
            
            return True
            
        except Exception as e:
            print(f"❌ [分析失败] {symbol} 分析失败: {e}")
            return False
    
    def _output_text_result(self, result, execution_time: float):
        """输出文本格式结果"""
        print("\n" + "=" * 60)
        print("📊 帝国AI协作分析报告")
        print("=" * 60)
        
        print(f"🎯 股票代码: {result.symbol}")
        print(f"🤝 协作模式: {result.collaboration_mode.value}")
        print(f"⏱️ 执行时间: {execution_time:.2f}秒 (系统: {result.execution_time:.2f}秒)")
        print(f"📈 共识决策: {result.consensus_decision.value}")
        print(f"🎪 置信度: {result.consensus_confidence:.2%}")
        print(f"🔍 冲突级别: {result.conflict_level.value}")
        
        print("\n👥 各角色分析结果:")
        for i, analysis in enumerate(result.individual_results, 1):
            print(f"  {i}. {analysis.role_name}: {analysis.decision.value} ({analysis.confidence:.2%})")
        
        if result.conflict_details:
            print(f"\n⚠️ 冲突详情:")
            for detail in result.conflict_details:
                print(f"  • {detail}")
        
        if result.risk_alerts:
            print(f"\n🛡️ 风险警报:")
            for alert in result.risk_alerts[:5]:  # 显示前5个最重要的
                print(f"  • {alert}")
            if len(result.risk_alerts) > 5:
                print(f"  ... 还有 {len(result.risk_alerts) - 5} 个警报")
        
        print(f"\n📝 分析摘要:")
        print(result.final_reasoning[:300] + "..." if len(result.final_reasoning) > 300 else result.final_reasoning)
        
        print("\n" + "=" * 60)
    
    def _output_json_result(self, result):
        """输出JSON格式结果"""
        json_result = result.to_dict()
        print(json.dumps(json_result, ensure_ascii=False, indent=2))
    
    def monitor_system(self) -> bool:
        """监控系统状态"""
        self._initialize_system()
        
        try:
            print("📊 [系统监控] 帝国AI协作系统状态报告")
            print("=" * 60)
            
            # 获取协作历史摘要
            summary = self.collaboration_system.get_collaboration_summary()
            
            print(f"📈 总协作次数: {summary['total_collaborations']}")
            print(f"⚡ 平均执行时间: {summary['avg_execution_time']:.2f}秒")
            print(f"🎯 平均置信度: {summary['avg_confidence']:.2%}")
            
            print(f"\n🔍 冲突分布:")
            for conflict_type, count in summary['conflict_distribution'].items():
                print(f"  • {conflict_type}: {count} 次")
            
            print(f"\n📊 决策分布:")
            for decision, count in summary['decision_distribution'].items():
                print(f"  • {decision}: {count} 次")
            
            # 系统健康检查
            print(f"\n🏥 系统健康检查:")
            health_score = self._calculate_health_score(summary)
            print(f"  🏆 综合健康评分: {health_score:.1f}/10")
            
            if health_score >= 8.0:
                print("  🟢 系统状态: 优秀")
            elif health_score >= 6.0:
                print("  🟡 系统状态: 良好")
            elif health_score >= 4.0:
                print("  🟠 系统状态: 一般")
            else:
                print("  🔴 系统状态: 需要关注")
            
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"❌ [监控失败] 系统监控失败: {e}")
            return False
    
    def _calculate_health_score(self, summary: Dict[str, Any]) -> float:
        """计算系统健康评分"""
        score = 10.0
        
        # 执行时间评分
        avg_time = summary['avg_execution_time']
        if avg_time > 10:
            score -= 2.0
        elif avg_time > 5:
            score -= 1.0
        
        # 置信度评分
        avg_confidence = summary['avg_confidence']
        if avg_confidence < 0.6:
            score -= 2.0
        elif avg_confidence < 0.7:
            score -= 1.0
        
        # 冲突率评分
        conflict_dist = summary['conflict_distribution']
        total_conflicts = sum(conflict_dist.values())
        if total_conflicts > 0:
            critical_rate = conflict_dist.get('严重冲突', 0) / total_conflicts
            major_rate = conflict_dist.get('重大冲突', 0) / total_conflicts
            
            if critical_rate > 0.2:
                score -= 3.0
            elif major_rate > 0.3:
                score -= 2.0
        
        return max(0.0, score)
    
    def list_agents(self) -> bool:
        """列出可用智能体"""
        self._initialize_system()
        
        try:
            print("👥 [智能体列表] 帝国AI核心角色")
            print("=" * 60)
            
            agents = self.collaboration_system.agents
            for i, (name, agent) in enumerate(agents.items(), 1):
                print(f"{i}. {name} ({agent.title})")
                print(f"   专业领域: {', '.join(agent.role_config.expertise)}")
                print(f"   决策风格: {agent.role_config.decision_style}")
                print(f"   风险偏好: {agent.role_config.risk_tolerance}")
                
                # 获取分析历史
                history_count = len(agent.analysis_history)
                print(f"   历史分析: {history_count} 次")
                print()
            
            print(f"📊 协作权重配置:")
            for name, weight in self.collaboration_system.decision_weights.items():
                print(f"  • {name}: {weight:.2%}")
            
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"❌ [列表失败] 智能体列表获取失败: {e}")
            return False
    
    def show_config(self) -> bool:
        """显示系统配置"""
        try:
            print("⚙️ [系统配置] 帝国AI当前配置")
            print("=" * 60)
            
            for key, value in self.config.items():
                print(f"{key}: {value}")
            
            if self.collaboration_system:
                print(f"\n🛡️ 风险控制阈值:")
                for key, value in self.collaboration_system.risk_thresholds.items():
                    print(f"  {key}: {value}")
            
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"❌ [配置失败] 配置显示失败: {e}")
            return False
    
    def run_test(self) -> bool:
        """运行系统测试"""
        print("🧪 [系统测试] 运行帝国AI系统测试")
        print("=" * 60)
        
        test_symbols = ["000001.SZ", "000002.SZ", "600036.SS"]
        test_results = []
        
        async def run_tests():
            for symbol in test_symbols:
                print(f"🔬 测试股票: {symbol}")
                start_time = time.time()
                
                success = await self.analyze_stock(symbol, mode='parallel', output_format='text')
                
                end_time = time.time()
                test_time = end_time - start_time
                
                test_results.append({
                    'symbol': symbol,
                    'success': success,
                    'time': test_time
                })
                
                print(f"{'✅' if success else '❌'} {symbol} 测试{'成功' if success else '失败'} (用时: {test_time:.2f}秒)")
                print("-" * 40)
        
        # 运行异步测试
        try:
            asyncio.run(run_tests())
            
            # 测试结果统计
            success_count = sum(1 for r in test_results if r['success'])
            total_count = len(test_results)
            avg_time = sum(r['time'] for r in test_results) / total_count if test_results else 0
            
            print(f"\n📊 测试结果统计:")
            print(f"  成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
            print(f"  平均时间: {avg_time:.2f}秒")
            
            if success_count == total_count:
                print("🎉 所有测试通过！系统运行正常")
                return True
            else:
                print("⚠️ 部分测试失败，请检查系统配置")
                return False
                
        except Exception as e:
            print(f"❌ [测试失败] 系统测试失败: {e}")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="帝国AI命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python imperial_cli.py analyze 000001.SZ                    # 分析股票
  python imperial_cli.py analyze 000001.SZ --mode sequential  # 使用顺序模式
  python imperial_cli.py monitor                              # 系统监控
  python imperial_cli.py agents                               # 列出智能体
  python imperial_cli.py test                                 # 运行测试
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 分析命令
    analyze_parser = subparsers.add_parser('analyze', help='分析股票')
    analyze_parser.add_argument('symbol', help='股票代码')
    analyze_parser.add_argument('--mode', choices=['parallel', 'sequential', 'emergency'], 
                              default='parallel', help='协作模式')
    analyze_parser.add_argument('--format', choices=['text', 'json'], 
                              default='text', help='输出格式')
    
    # 监控命令
    subparsers.add_parser('monitor', help='系统监控')
    
    # 智能体命令
    subparsers.add_parser('agents', help='列出智能体')
    
    # 配置命令
    subparsers.add_parser('config', help='显示配置')
    
    # 测试命令
    subparsers.add_parser('test', help='运行系统测试')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 初始化CLI
    cli = ImperialAICLI()
    
    # 执行命令
    try:
        if args.command == 'analyze':
            success = asyncio.run(cli.analyze_stock(args.symbol, args.mode, args.format))
        elif args.command == 'monitor':
            success = cli.monitor_system()
        elif args.command == 'agents':
            success = cli.list_agents()
        elif args.command == 'config':
            success = cli.show_config()
        elif args.command == 'test':
            success = cli.run_test()
        else:
            print(f"❌ 未知命令: {args.command}")
            success = False
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
