import os
import json
from collections import Counter

SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'embedded_nanobot_context')


def iter_json_files(directory):
    for fname in os.listdir(directory):
        if fname.endswith('.json'):
            yield os.path.join(directory, fname)

def main():
    fallback_count = 0
    total = 0
    fallback_samples = []
    fallback_types = Counter()
    route_decision_types = Counter()
    for fpath in iter_json_files(SNAPSHOT_DIR):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load {fpath}: {e}")
            continue
        total += 1
        route_fallback = data.get('route_fallback')
        route_decision = data.get('route_decision')
        if route_decision:
            route_decision_types[str(route_decision.get('decision_type', route_decision.get('type', 'unknown')))] += 1
        if route_fallback:
            fallback_count += 1
            fallback_types[str(route_fallback.get('reason', route_fallback.get('type', 'unknown')))] += 1
            if len(fallback_samples) < 10:
                fallback_samples.append({
                    'file': os.path.basename(fpath),
                    'route_fallback': route_fallback,
                    'route_decision': route_decision,
                    'user_input': data.get('user_input', data.get('messages', [{}])[0].get('content', ''))
                })
    print(f"总快照数: {total}")
    print(f"route_fallback 触发数: {fallback_count}，命中率: {fallback_count/total:.2%}" if total else "无快照")
    print("\nroute_fallback 类型分布:")
    for k, v in fallback_types.most_common():
        print(f"  {k}: {v}")
    print("\nroute_decision 类型分布:")
    for k, v in route_decision_types.most_common():
        print(f"  {k}: {v}")
    print("\n典型 route_fallback 样本（最多10条）:")
    for sample in fallback_samples:
        print(f"\n文件: {sample['file']}")
        print(f"route_fallback: {json.dumps(sample['route_fallback'], ensure_ascii=False, indent=2)}")
        print(f"route_decision: {json.dumps(sample['route_decision'], ensure_ascii=False, indent=2)}")
        print(f"user_input: {sample['user_input'][:200]}")

if __name__ == '__main__':
    main()
