import json
from itertools import combinations

# 加载所有 tag
with open("resource/data/recruit_tags.json", "r", encoding="utf-8") as f:
    tags_data = json.load(f)

all_tags = tags_data["all_tags"]
print(f"总 tag 数: {len(all_tags)}")
print(f"所有 tag: {all_tags}")

# 计算理论上的 5-tag 组合数
total_combinations = len(list(combinations(all_tags, 5)))
print(f"\n理论上 5-tag 组合数: C({len(all_tags)}, 5) = {total_combinations}")

# 检查 lookup 表
with open("resource/data/recruit_lookup.json", "r", encoding="utf-8") as f:
    lookup = json.load(f)

packs = lookup.get("packs", {})
print(f"\nlookup 表中的组合数: {len(packs)}")

# 统计分支
branches = {}
for key, value in packs.items():
    branch = value.get("branch", "unknown")
    branches[branch] = branches.get(branch, 0) + 1

print(f"\n分支统计:")
for branch, count in sorted(branches.items()):
    print(f"  {branch}: {count} 个")

# 检查 lookup 表的 key 格式问题
# lookup 表的 key 是用逗号分隔的字符串，需要排序
print("\n检查 lookup 表 key 格式...")
invalid_keys = []
for key in packs.keys():
    tags_in_key = key.split(",")
    if sorted(tags_in_key) != tags_in_key:
        invalid_keys.append(key)

if invalid_keys:
    print(f"发现 {len(invalid_keys)} 个 key 未排序:")
    for k in invalid_keys[:5]:  # 只显示前5个
        print(f"  {k}")
else:
    print("所有 key 格式正确（已排序）")

# 检查代码中的查找逻辑
print("\n" + "=" * 60)
print("代码中的查找逻辑测试:")
test_tags = ["回复", "防御", "群体攻击", "风属性", "守护者"]
print(f"输入 tags: {test_tags}")
key_to_find = ",".join(sorted(test_tags))
print(f"查找的 key: {key_to_find}")
found = key_to_find in packs
print(f"是否在 lookup 中: {found}")
if found:
    print(f"结果: {packs[key_to_find]}")
