"""
Phase 4H-H1 七阶段对撞引擎实战演示
展示帝国AI三核心角色的对撞决策过程

创建时间: 2025-08-16
版本: v1.0
作者: 帝国AI项目团队
"""

import asyncio
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

from imperial_agents.core.seven_stage_collision_engine import (
    SevenStageCollisionEngine, 
    CollisionStage,
    CollisionResult
)
from imperial_agents.roles.wyckoff_ai import WyckoffAI
from imperial_agents.roles.marenhui_ai import MarenhuiAI
from imperial_agents.roles.crocodile_mentor_ai import CrocodileMentorAI


class CollisionEngineDemo:
    """七阶段对撞引擎实战演示"""
    
    def __init__(self):
        self.demo_scenarios = [
            {
                "name": "场景1: 蓝筹股投资决策",
                "task_data": {
                    "task_name": "贵州茅台(600519)投资分析",
                    "stock_code": "600519.SH",
                    "stock_name": "贵州茅台",
                    "market_cap": "大盘股",
                    "sector": "消费行业",
                    "analysis_period": "中期(3-6个月)",
                    "current_price": "1800元",
                    "pe_ratio": "35",
                    "market_condition": "震荡市",
                    "risk_preference": "稳健型"
                }
            },
            {
                "name": "场景2: 成长股投资决策",
                "task_data": {
                    "task_name": "宁德时代(300750)投资分析",
                    "stock_code": "300750.SZ",
                    "stock_name": "宁德时代",
                    "market_cap": "大盘股",
                    "sector": "新能源",
                    "analysis_period": "短期(1-3个月)",
                    "current_price": "180元",
                    "pe_ratio": "25",
                    "market_condition": "牛市",
                    "risk_preference": "积极型"
                }
            },
            {
                "name": "场景3: 高风险投机决策",
                "task_data": {
                    "task_name": "ST股票投资风险评估",
                    "stock_code": "ST****",
                    "stock_name": "某ST股票",
                    "market_cap": "小盘股",
                    "sector": "问题企业",
                    "analysis_period": "短期(1个月内)",
                    "current_price": "低价",
                    "pe_ratio": "负值",
                    "market_condition": "熊市",
                    "risk_preference": "投机型"
                }
            }
        ]
    
    async def run_comprehensive_demo(self):
        """运行综合演示"""
        print("🎭 帝国AI七阶段对撞引擎实战演示")
        print("=" * 60)
        print("🔥 三大高手巅峰对决: 威科夫AI vs 马仁辉AI vs 鳄鱼导师AI")
        print("⚔️ 七阶段智慧对撞，决策见真章!")
        print("=" * 60)
        
        # 初始化三个核心角色
        print("\n🎯 初始化三大核心角色...")
        wyckoff_ai = WyckoffAI()
        marenhui_ai = MarenhuiAI()
        crocodile_mentor = CrocodileMentorAI()
        
        agents = [wyckoff_ai, marenhui_ai, crocodile_mentor]
        
        print(f"✅ {wyckoff_ai.agent_name} - 威科夫理论技术分析专家")
        print(f"✅ {marenhui_ai.agent_name} - 222法则量化验证专家")
        print(f"✅ {crocodile_mentor.agent_name} - 鳄鱼法则风控专家")
        
        # 初始化对撞引擎
        print(f"\n⚡ 初始化七阶段对撞引擎...")
        
        # 配置对撞引擎参数
        collision_config = {
            "max_stage_duration": 30.0,  # 每阶段最大30秒
            "min_consensus_threshold": 0.7,  # 70%共识阈值
            "max_dissent_rounds": 2,  # 最多2轮异议处理
            "confidence_weight": 0.4,  # 置信度权重40%
            "consensus_weight": 0.6,  # 共识度权重60%
            "enable_deep_analysis": True,  # 启用深度分析
            "save_process_log": True,  # 保存过程日志
        }
        
        engine = SevenStageCollisionEngine(agents, collision_config)
        print("✅ 七阶段对撞引擎初始化完成")
        
        # 逐个场景演示
        for i, scenario in enumerate(self.demo_scenarios, 1):
            print(f"\n" + "="*80)
            print(f"🎬 {scenario['name']}")
            print("="*80)
            
            await self._demo_single_scenario(engine, scenario, i)
            
            if i < len(self.demo_scenarios):
                print(f"\n⏰ 准备下一个场景 (3秒后开始)...")
                await asyncio.sleep(3)
        
        print(f"\n🏆 七阶段对撞引擎演示完毕!")
        print("🎊 帝国AI Phase 4H-H1: 七阶段对撞机制实现 - 圆满成功!")
    
    async def _demo_single_scenario(self, engine: SevenStageCollisionEngine, scenario: dict, scenario_num: int):
        """演示单个场景"""
        task_data = scenario["task_data"]
        
        print(f"📋 任务信息:")
        for key, value in task_data.items():
            print(f"   {key}: {value}")
        
        print(f"\n🚀 开始七阶段对撞决策流程...")
        print("-" * 50)
        
        # 执行对撞流程
        start_time = time.time()
        
        try:
            result = await engine.run_collision_process(task_data)
            execution_time = time.time() - start_time
            
            # 展示结果
            self._display_collision_result(result, execution_time, scenario_num)
            
            # 保存结果
            await self._save_demo_result(scenario, result, execution_time)
            
        except Exception as e:
            print(f"❌ 场景 {scenario_num} 执行失败: {str(e)}")
    
    def _display_collision_result(self, result: CollisionResult, execution_time: float, scenario_num: int):
        """展示对撞结果"""
        print(f"\n🏆 场景 {scenario_num} 对撞决策结果")
        print("=" * 50)
        
        # 最终决策
        print(f"📝 最终决策: {result.final_decision}")
        
        # 核心指标
        print(f"\n📊 决策质量指标:")
        print(f"   置信度评分: {result.confidence_score:.2f}/1.0")
        print(f"   共识水平: {result.consensus_level:.2f}/1.0")
        print(f"   执行时间: {execution_time:.2f}秒")
        
        # 决策等级评估
        quality_level = self._assess_decision_quality(result.confidence_score, result.consensus_level)
        print(f"   决策等级: {quality_level}")
        
        # 各阶段耗时
        print(f"\n⏱️ 七阶段执行时间:")
        for stage, duration in result.stage_durations.items():
            print(f"   {stage.value}: {duration:.2f}秒")
        
        # 异议和冲突
        if result.dissent_points:
            print(f"\n⚠️ 异议点记录: {len(result.dissent_points)}个")
            for i, dissent in enumerate(result.dissent_points[:3], 1):  # 最多显示3个
                print(f"   {i}. {str(dissent)[:50]}...")
        
        # 执行计划
        if result.execution_plan:
            print(f"\n✅ 执行计划:")
            steps = result.execution_plan.get("steps", [])
            for step in steps[:3]:  # 最多显示3步
                print(f"   • {step.get('action', 'N/A')} ({step.get('timeline', 'N/A')})")
        
        print("-" * 50)
    
    def _assess_decision_quality(self, confidence: float, consensus: float) -> str:
        """评估决策质量等级"""
        avg_score = (confidence + consensus) / 2
        
        if avg_score >= 0.9:
            return "🥇 卓越 (A+级)"
        elif avg_score >= 0.8:
            return "🥈 优秀 (A级)"
        elif avg_score >= 0.7:
            return "🥉 良好 (B级)"
        elif avg_score >= 0.6:
            return "📊 合格 (C级)"
        else:
            return "⚠️ 需改进 (D级)"
    
    async def _save_demo_result(self, scenario: dict, result: CollisionResult, execution_time: float):
        """保存演示结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        demo_result = {
            "timestamp": timestamp,
            "scenario": scenario,
            "result": {
                "final_decision": result.final_decision,
                "confidence_score": result.confidence_score,
                "consensus_level": result.consensus_level,
                "execution_time": execution_time,
                "stage_durations": {stage.value: duration for stage, duration in result.stage_durations.items()},
                "dissent_points_count": len(result.dissent_points),
                "execution_plan": result.execution_plan
            }
        }
        
        # 保存到文件
        results_dir = Path("demo_results")
        results_dir.mkdir(exist_ok=True)
        
        filename = f"collision_demo_{scenario['name'].split(':')[0].replace(' ', '_')}_{timestamp}.json"
        filepath = results_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(demo_result, f, ensure_ascii=False, indent=2)
            print(f"💾 结果已保存: {filepath}")
        except Exception as e:
            print(f"⚠️ 保存结果失败: {str(e)}")


async def run_interactive_demo():
    """交互式演示"""
    print("🎮 帝国AI七阶段对撞引擎 - 交互式演示")
    print("=" * 50)
    
    while True:
        print("\n请选择演示模式:")
        print("1. 完整三场景演示")
        print("2. 单场景快速测试")
        print("3. 自定义投资决策")
        print("0. 退出")
        
        try:
            choice = input("\n请输入选择 (0-3): ").strip()
            
            if choice == "0":
                print("👋 感谢使用帝国AI七阶段对撞引擎!")
                break
            elif choice == "1":
                demo = CollisionEngineDemo()
                await demo.run_comprehensive_demo()
            elif choice == "2":
                await run_quick_test()
            elif choice == "3":
                await run_custom_decision()
            else:
                print("❌ 无效选择，请重新输入")
                
        except KeyboardInterrupt:
            print("\n👋 用户取消，退出演示")
            break
        except Exception as e:
            print(f"❌ 演示过程出错: {str(e)}")


async def run_quick_test():
    """快速测试"""
    print("\n⚡ 快速测试模式")
    
    # 使用模拟智能体进行快速测试
    class QuickTestAgent:
        def __init__(self, name, style):
            self.agent_name = name
            self.style = style
        
        async def analyze(self, prompt):
            await asyncio.sleep(0.1)  # 快速响应
            
            if self.style == "technical":
                return {
                    "analysis": "技术面分析显示趋势良好",
                    "confidence": 0.8,
                    "reasoning": "基于技术指标判断",
                    "detailed_opinion": "从技术角度看，建议适度参与",
                    "decision": "买入",
                    "rationale": "技术面支撑明确"
                }
            elif self.style == "quantitative":
                return {
                    "analysis": "量化指标显示风险可控",
                    "confidence": 0.75,
                    "reasoning": "基于数量化模型",
                    "detailed_opinion": "数据显示投资价值存在",
                    "decision": "谨慎买入",
                    "rationale": "量化信号偏正面"
                }
            else:  # risk_control
                return {
                    "analysis": "风险评估结果偏谨慎",
                    "confidence": 0.7,
                    "reasoning": "基于风险控制原则",
                    "detailed_opinion": "建议控制仓位，降低风险",
                    "decision": "小仓位试探",
                    "rationale": "安全第一"
                }
    
    agents = [
        QuickTestAgent("技术分析师", "technical"),
        QuickTestAgent("量化分析师", "quantitative"),
        QuickTestAgent("风控专家", "risk_control")
    ]
    
    engine = SevenStageCollisionEngine(agents)
    
    task_data = {
        "task_name": "快速测试投资决策",
        "target": "测试标的",
        "type": "快速验证",
        "mode": "test"
    }
    
    print("🔄 执行快速测试...")
    start_time = time.time()
    result = await engine.run_collision_process(task_data)
    duration = time.time() - start_time
    
    print(f"✅ 快速测试完成 ({duration:.2f}秒)")
    print(f"📝 决策结果: {result.final_decision}")
    print(f"📊 置信度: {result.confidence_score:.2f}")
    print(f"📊 共识度: {result.consensus_level:.2f}")


async def run_custom_decision():
    """自定义决策演示"""
    print("\n🛠️ 自定义投资决策")
    
    try:
        # 获取用户输入
        stock_name = input("请输入股票名称: ").strip() or "自定义股票"
        investment_amount = input("请输入投资金额: ").strip() or "100万"
        time_horizon = input("请输入投资周期 (短期/中期/长期): ").strip() or "中期"
        risk_preference = input("请输入风险偏好 (保守/稳健/积极): ").strip() or "稳健"
        
        task_data = {
            "task_name": f"{stock_name}投资决策",
            "stock_name": stock_name,
            "investment_amount": investment_amount,
            "time_horizon": time_horizon,
            "risk_preference": risk_preference,
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "custom_decision": True
        }
        
        print(f"\n📋 自定义任务: {task_data['task_name']}")
        print("🔄 正在执行七阶段对撞分析...")
        
        # 使用简化的模拟智能体
        class CustomAgent:
            def __init__(self, name):
                self.agent_name = name
            
            async def analyze(self, prompt):
                await asyncio.sleep(0.2)
                return {
                    "analysis": f"{self.agent_name}针对{stock_name}的专业分析",
                    "confidence": 0.75,
                    "reasoning": f"基于{self.agent_name}的专业判断",
                    "detailed_opinion": f"从{self.agent_name}角度看，该投资方案具有一定可行性",
                    "decision": f"{self.agent_name}的决策建议",
                    "rationale": "综合考虑多方面因素"
                }
        
        agents = [CustomAgent("威科夫AI"), CustomAgent("马仁辉AI"), CustomAgent("鳄鱼导师AI")]
        engine = SevenStageCollisionEngine(agents)
        
        result = await engine.run_collision_process(task_data)
        
        print(f"\n🏆 自定义决策完成!")
        print(f"📝 决策建议: {result.final_decision}")
        print(f"📊 决策置信度: {result.confidence_score:.2f}")
        print(f"📊 专家共识度: {result.consensus_level:.2f}")
        
    except Exception as e:
        print(f"❌ 自定义决策失败: {str(e)}")


async def main():
    """主函数"""
    print("🎭 欢迎使用帝国AI七阶段对撞引擎!")
    print("🚀 Phase 4H-H1: 核心功能扩展 - 对撞机制实现")
    
    await run_interactive_demo()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序异常: {str(e)}")
