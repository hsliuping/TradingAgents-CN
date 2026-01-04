"""
批量重命名高级课程文件为英文名
"""
import os
import shutil
from pathlib import Path

# 文件映射：旧文件名 -> 新文件名
FILE_MAPPING = {
    '01-基础篇-第1课.md': 'lesson-01-basics-retail-to-system-trader.md',
    '01-基础篇-第2课.md': 'lesson-02-basics-evolvable-investment-cycle.md',
    '02-选股篇-第3课.md': 'lesson-03-stock-selection-single-analysis.md',
    '02-选股篇-第4课.md': 'lesson-04-stock-selection-batch-analysis.md',
    '02-选股篇-第5课.md': 'lesson-05-stock-selection-short-long-term.md',
    '03-择时篇-第6课.md': 'lesson-06-timing-bull-bear-debate.md',
    '03-择时篇-第7课.md': 'lesson-07-timing-risk-debate.md',
    '03-择时篇-第8课.md': 'lesson-08-timing-multi-agent-debate.md',
    '04-执行篇-第9课.md': 'lesson-09-execution-position-management.md',
    '04-执行篇-第10课.md': 'lesson-10-execution-strategy.md',
    '05-持仓管理篇-第11课.md': 'lesson-11-position-ai-analysis.md',
    '05-持仓管理篇-第12课.md': 'lesson-12-position-decision.md',
    '06-风险管理篇-第13课.md': 'lesson-13-risk-debate-application.md',
    '06-风险管理篇-第14课.md': 'lesson-14-risk-profit-loss-strategy.md',
    '07-复盘改进篇-第15课.md': 'lesson-15-review-ai-trade-review.md',
    '07-复盘改进篇-第16课.md': 'lesson-16-review-continuous-improvement.md',
    '08-短线实战篇-第17课.md': 'lesson-17-short-term-plan-design.md',
    '08-短线实战篇-第18课.md': 'lesson-18-short-term-case-study-1.md',
    '08-短线实战篇-第19课.md': 'lesson-19-short-term-case-study-2.md',
    '09-中长线实战篇-第20课.md': 'lesson-20-long-term-system-design.md',
    '09-中长线实战篇-第21课.md': 'lesson-21-long-term-case-study-1.md',
    '09-中长线实战篇-第22课.md': 'lesson-22-long-term-case-study-2.md',
    '10-交易计划建立-第23课.md': 'lesson-23-trading-plan-template.md',
    '10-交易计划建立-第24课.md': 'lesson-24-continuous-optimization.md',
}

def rename_files():
    """重命名文件"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    course_dir = project_root / 'docs' / 'courses' / 'advanced' / 'expanded'
    
    if not course_dir.exists():
        print(f'错误：目录不存在: {course_dir}')
        return
    
    renamed_count = 0
    skipped_count = 0
    
    for old_name, new_name in FILE_MAPPING.items():
        old_path = course_dir / old_name
        new_path = course_dir / new_name
        
        if not old_path.exists():
            print(f'跳过：文件不存在 - {old_name}')
            skipped_count += 1
            continue
        
        if new_path.exists():
            print(f'跳过：目标文件已存在 - {new_name}')
            skipped_count += 1
            continue
        
        try:
            shutil.move(str(old_path), str(new_path))
            print(f'重命名：{old_name} -> {new_name}')
            renamed_count += 1
        except Exception as e:
            print(f'错误：重命名失败 - {old_name}: {e}')
    
    print(f'\n完成！')
    print(f'成功重命名: {renamed_count} 个文件')
    print(f'跳过: {skipped_count} 个文件')

if __name__ == '__main__':
    rename_files()


