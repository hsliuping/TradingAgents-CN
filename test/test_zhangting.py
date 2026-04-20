import pandas as pd
import datetime
import time

try:
    import pywencai
except ImportError:
    print("❌ 错误: 请安装 pywencai (pip install pywencai)")
    exit(1)

def get_detailed_limit_up_data(date):
    """
    获取包含特定字段（封单量、封单额、类型）的涨停数据
    关键点：在 query 中显式指定需要返回的字段
    """
    date_str = date.strftime('%Y%m%d')
    
    # 【关键修改】构造查询语句
    # 语法：条件，字段1，字段2，字段3...
    # 我们显式要求返回：股票代码，股票简称，涨停原因类别，涨停封单量，涨停封单额，涨停类型，首次涨停时间
    query = f"非ST,{date_str}涨停，股票代码，股票简称，涨停原因类别，涨停封单量，涨停封单额，涨停类型，首次涨停时间"
    
    print(f"🔍 正在请求详细数据...")
    print(f"📝 查询语句: {query}")
    
    try:
        df = pywencai.get(
            query=query,
            sort_key='涨停封单额', # 尝试按封单额排序，验证字段是否存在
            sort_order='desc',
            loop=True
        )
        
        if df is None or df.empty:
            print("❌ 未获取到数据。")
            return None
            
        print(f"✅ 获取成功，共 {len(df)} 条记录。")
        return df

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def validate_columns(df, target_fields):
    """
    验证目标字段是否存在，并检查数据质量
    """
    print("\n" + "="*50)
    print("🔎 字段存在性验证")
    print("="*50)
    
    # 标准化列名（去除空格，转小写以便模糊匹配，但这里先精确匹配）
    # pywencai 返回的列名可能带有后缀，如 '涨停封单量[20260227]'
    
    found_cols = {}
    
    for target in target_fields:
        # 1. 尝试精确匹配
        if target in df.columns:
            found_cols[target] = target
            continue
        
        # 2. 尝试模糊匹配 (处理带日期的列名)
        matched = False
        for col in df.columns:
            if target in str(col):
                found_cols[target] = col
                matched = True
                break
        
        if matched:
            print(f"✅ [{target}] -> 找到列名: '{found_cols[target]}'")
        else:
            print(f"❌ [{target}] -> 未找到相关列!")
            
    if len(found_cols) != len(target_fields):
        print("\n⚠️ 警告: 部分关键字段缺失。")
        print("📋 实际返回的所有列名:")
        for i, col in enumerate(df.columns):
            print(f"   {i+1}. {col}")
        return False, found_cols
    
    return True, found_cols

def analyze_data_quality(df, found_cols):
    """
    分析找到字段的数据质量（空值率、数据类型、示例值）
    """
    print("\n" + "="*50)
    print("📊 数据质量与样本分析")
    print("="*50)
    
    sample_size = min(5, len(df))
    
    for original_target, actual_col in found_cols.items():
        series = df[actual_col]
        
        print(f"\n--- 字段: {original_target} (实际列名: {actual_col}) ---")
        print(f"数据类型: {series.dtype}")
        print(f"空值数量: {series.isna().sum()} / {len(series)}")
        
        # 尝试转换为数值型（针对封单量/额）
        if '量' in original_target or '额' in original_target:
            # 清洗可能存在的单位字符 (如 "万", "亿") - 简单处理
            # 注意：pywencai 有时直接返回数字，有时带单位，视情况而定
            try:
                # 如果全是数字，直接统计
                numeric_series = pd.to_numeric(series, errors='coerce')
                non_null_count = numeric_series.notna().sum()
                if non_null_count > 0:
                    max_val = numeric_series.max()
                    avg_val = numeric_series.mean()
                    print(f"最大值: {max_val}")
                    print(f"平均值: {avg_val:.2f}")
                else:
                    print("⚠️ 无法转换为数值，可能包含非数字字符。")
            except Exception as e:
                print(f"转换数值失败: {e}")
        
        # 打印前几个非空样本
        non_null_samples = series.dropna().head(3)
        if not non_null_samples.empty:
            print("样本值预览:")
            for val in non_null_samples:
                print(f"   - {val}")
        else:
            print("   (无有效样本值)")

def main():
    print("🚀 涨停详细字段（封单量/额/类型）专项测试")
    print("="*60)
    
    # 测试日期
    test_date = datetime.date(2026, 2, 27)
    print(f"📅 测试日期: {test_date}")
    
    # 1. 获取数据
    df = get_detailed_limit_up_data(test_date)
    
    if df is None or df.empty:
        print("\n❌ 测试终止：无法获取基础数据。")
        return

    # 2. 定义需要验证的目标字段
    # 注意：这里的关键词是我们在查询中请求的，也是我们要验证的
    target_fields = [
        '涨停原因类别',
        '涨停封单量',
        '涨停封单额',
        '涨停类型',
        '首次涨停时间'
    ]
    
    # 3. 验证列是否存在
    success, found_cols = validate_columns(df, target_fields)
    
    if not success:
        print("\n💡 建议:")
        print("   1. 同花顺问财可能不支持直接查询某些字段（特别是历史日期的封单量）。")
        print("   2. 尝试去掉日期后缀，或使用更通用的字段名。")
        print("   3. 某些字段可能需要付费权限或仅在盘中可用。")
        # 即使部分失败，也继续分析成功的字段
        if not found_cols:
            return

    # 4. 分析数据质量
    analyze_data_quality(df, found_cols)
    
    # 5. 综合展示 (如果有足够的字段)
    if '涨停封单额' in found_cols and '涨停原因类别' in found_cols:
        col_amount = found_cols['涨停封单额']
        col_reason = found_cols['涨停原因类别']
        
        print("\n" + "="*50)
        print("💰 封单金额 TOP 5 股票及其原因")
        print("="*50)
        
        # 确保能排序
        try:
            df_sorted = df.copy()
            df_sorted['_temp_amount'] = pd.to_numeric(df_sorted[col_amount], errors='coerce')
            top5 = df_sorted.nlargest(5, '_temp_amount')
            
            display_df = top5[['股票代码', '股票简称', col_reason, col_amount, '涨停类型' if '涨停类型' in found_cols else found_cols.get('涨停类型', '')]]
            # 重命名列以便显示
            display_df = display_df.rename(columns={
                col_reason: '涨停原因',
                col_amount: '封单额',
                found_cols.get('涨停类型', ''): '类型'
            })
            print(display_df.to_string(index=False))
            
        except Exception as e:
            print(f"排序展示失败: {e}")

    print("\n✅ 测试完成。")

if __name__ == "__main__":
    main()