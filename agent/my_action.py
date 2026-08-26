from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from itertools import combinations
import json
import os
import time

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TAGS_PATH = os.path.join(_BASE, "resource", "data", "recruit_tags.json")
_CHARS_PATH = os.path.join(_BASE, "resource", "data", "characters.json")
_LOOKUP_PATH = os.path.join(_BASE, "resource", "data", "recruit_lookup.json")

with open(_TAGS_PATH, "r", encoding="utf-8") as f:
    _TAGS_DATA = json.load(f)

ALL_TAGS = set(_TAGS_DATA["all_tags"])


def _load_character_db():
    if not os.path.exists(_CHARS_PATH):
        return [], {}, {}
    with open(_CHARS_PATH, "r", encoding="utf-8") as f:
        chars = json.load(f)
    tag_to_chars: dict[str, set[str]] = {}
    for c in chars:
        for t in c.get("tags", []):
            tag_to_chars.setdefault(t, set()).add(c["name"])
    by_name = {c["name"]: c for c in chars}
    return chars, tag_to_chars, by_name


def _load_lookup():
    if not os.path.exists(_LOOKUP_PATH):
        return {}
    with open(_LOOKUP_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("packs", {})


_CHARS, _TAG_TO_CHARS, _CHARS_BY_NAME = _load_character_db()
_LOOKUP = _load_lookup()

BRANCH_LEADER = "leader"


def _candidates_of(combo: tuple[str, ...]) -> list[dict]:
    """模拟网站 isContain 逻辑：3星领袖角色只能通过含"领袖"的组合匹配"""
    if not _TAG_TO_CHARS or not _CHARS_BY_NAME:
        return []
    sets = []
    for t in combo:
        s = _TAG_TO_CHARS.get(t)
        if not s:
            return []
        sets.append(s)
    names = set.intersection(*sets)
    combo_has_leader = "领袖" in combo
    result = []
    for n in names:
        if n not in _CHARS_BY_NAME:
            continue
        char = _CHARS_BY_NAME[n]
        # 网站 isContain: 组合不含"领袖"时，领袖角色不匹配
        if not combo_has_leader and "领袖" in char.get("tags", []):
            continue
        result.append(char)
    return result


def _lookup_pack(tags: list[str]) -> dict | None:
    """用识别到的 5 个 tag 查找预设组合包的预计算结果。"""
    if not _LOOKUP or len(tags) != 5:
        return None
    key = ",".join(sorted(tags))
    entry = _LOOKUP.get(key)
    if not entry:
        return None
    return {
        "chosen": entry.get("chosen", []),
        "branch": entry.get("branch", "normal"),
        "candidates": entry.get("candidates", []),
    }


def _pick_fallback(tags: list[str]) -> tuple[list[str], str]:
    """查表失败时的实时计算后备方案。"""
    valid = [t for t in tags if t in ALL_TAGS]
    if not valid:
        return [], "normal"

    if "领袖" in valid:
        return ["领袖"], BRANCH_LEADER

    for combo in combinations(valid, 2):
        cands = _candidates_of(combo)
        if cands and all(c.get("stars", 0) == 2 for c in cands):
            return list(combo), "two_star"

    for combo in combinations(valid, 3):
        cands = _candidates_of(combo)
        if cands and all(c.get("stars", 0) == 2 for c in cands):
            return list(combo), "two_star"

    for combo in combinations(valid, 2):
        cands = _candidates_of(combo)
        if cands:
            return list(combo), "normal"

    return valid[:2], "normal"


def _click(context: Context, xy: list[int], settle_ms: int = 300) -> None:
    context.tasker.controller.post_click(xy[0], xy[1]).wait()
    if settle_ms:
        time.sleep(settle_ms / 1000.0)


@AgentServer.custom_action("tkfm_recruit_select_tags")
class TkfmRecruitSelectTags(CustomAction):
    """选 tag 页面专用动作。

    逻辑：
    1. 从识别器结果获取 5 个 tag
    2. 查表（recruit_lookup.json）获取 tkfm.club 网站的预计算最优结果
    3. 查表失败时实时计算作为后备
    4. 领袖分支 -> 中断任务
    5. 其他 -> 勾选 tag + 总是 9 小时
    """

    DURATION_DOWN_ARROW_ROI = [122, 332, 134, 39]

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 从同节点识别器的 reco_detail 获取 detail
        tag_entries = []

        if argv.reco_detail:
            result = None
            if argv.reco_detail.filtered_results:
                result = argv.reco_detail.filtered_results[0]
            elif argv.reco_detail.best_result:
                result = argv.reco_detail.best_result

            if result and hasattr(result, 'detail'):
                detail = result.detail
                # detail 可能是 dict 或 JSON 字符串
                if isinstance(detail, str):
                    try:
                        detail = json.loads(detail)
                    except Exception:
                        detail = {}
                if isinstance(detail, dict) and "tags" in detail:
                    tag_entries = detail["tags"]

        if not tag_entries:
            print("TkfmRecruit: 未识别到标签，跳过")
            return False

        by_text = {e["text"]: e for e in tag_entries if "click_xy" in e}
        all_tags = list(by_text.keys())

        # 优先查表（tkfm.club 预计算结果）
        chosen = []
        branch = "normal"
        candidates = None

        lookup_result = _lookup_pack(all_tags)
        if lookup_result:
            chosen = lookup_result["chosen"]
            branch = lookup_result["branch"]
            candidates = lookup_result["candidates"]
            print(f"TkfmRecruit: [查表命中] {all_tags} -> {chosen} (branch={branch})")
        else:
            chosen, branch = _pick_fallback(all_tags)
            print(f"TkfmRecruit: [实时计算] {all_tags} -> {chosen} (branch={branch})")

        if not chosen:
            print("TkfmRecruit: 无可用组合")
            return False

        # 领袖分支：列出所有含"领袖"的组合及该组合下的3星角色
        if branch == BRANCH_LEADER:
            valid = [t for t in all_tags if t in ALL_TAGS]
            combos_with_leader = []
            # 枚举所有 2-3 tag 组合（必须含"领袖"，排除单"领袖"）
            for r in range(2, min(4, len(valid) + 1)):
                for combo in combinations(valid, r):
                    if "领袖" not in combo:
                        continue
                    cands = _candidates_of(combo)
                    three_stars = [c for c in cands if c.get("stars", 0) == 3]
                    if three_stars:
                        combos_with_leader.append((combo, three_stars))

            print("=" * 60)
            print("[领袖/3☆ 预报]")
            if combos_with_leader:
                # 按3星角色数从少到多排序
                combos_with_leader.sort(key=lambda x: len(x[1]))
                print(f"[共 {len(combos_with_leader)} 种组合可出3星角色]")
                for combo, stars in combos_with_leader:
                    total = len(stars)
                    prob = 100.0 / total
                    combo_str = " + ".join(combo)
                    print(f"\n  组合: {combo_str} ({total}个3星)")
                    for c in stars:
                        name = c.get("name", "?")
                        print(f"    ★★★ {name}  概率 {prob:.2f}%")
            else:
                print("[警告] 未找到3星角色候选")
            print("\n[领袖分支] 任务中断，请手动决定是否招募")
            print("=" * 60)
            return False

        # 勾选选中的 tag
        for tag in chosen:
            entry = by_text.get(tag)
            if not entry:
                print(f"TkfmRecruit: 未找到 tag '{tag}' 的坐标")
                continue
            print(f"TkfmRecruit: 勾选 {tag} @ {entry['click_xy']}")
            _click(context, entry["click_xy"], settle_ms=400)

        # 总是点击下箭头切换到 9 小时
        roi = self.DURATION_DOWN_ARROW_ROI
        print(f"TkfmRecruit: 点击下箭头切换到 9 小时 @ roi={roi}")
        cx = roi[0] + roi[2] // 2
        cy = roi[1] + roi[3] // 2
        _click(context, [cx, cy], settle_ms=500)

        # 点击确认按钮 [420, 1033, 140, 27]
        confirm_roi = [420, 1033, 140, 27]
        print(f"TkfmRecruit: 点击确认 @ roi={confirm_roi}")
        cx = confirm_roi[0] + confirm_roi[2] // 2
        cy = confirm_roi[1] + confirm_roi[3] // 2
        _click(context, [cx, cy], settle_ms=500)

        return True
