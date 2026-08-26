from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from maa.pipeline import JRecognitionType, JOCR
from difflib import get_close_matches
import json
import os

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resource", "data", "recruit_tags.json"
)
with open(_DATA_PATH, "r", encoding="utf-8") as f:
    _DATA = json.load(f)
KNOWN_TAGS = set(_DATA["all_tags"])


def _fuzzy_match(text: str) -> str | None:
    """OCR 文本归一化到已知 33 个 Tag。"""
    text = text.strip()
    if not text:
        return None
    if text in KNOWN_TAGS:
        return text
    for t in KNOWN_TAGS:
        if text in t or t in text:
            return t
    matches = get_close_matches(text, list(KNOWN_TAGS), n=1, cutoff=0.6)
    return matches[0] if matches else None


@AgentServer.custom_recognition("tkfm_recruit_tag_reco")
class TkfmRecruitTagRecognition(CustomRecognition):
    """选 tag 页面专用识别器。

    职责：使用 MaaFramework 内部 OCR 引擎识别 5 个候选 tag，
    返回 text + click_xy。
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        # 使用 MaaFramework 内部 OCR 识别
        ocr_param = JOCR(
            expected=[],
            roi=(0, 0, 0, 0),  # 全屏
            threshold=0.1,
            order_by="Horizontal"
        )

        detail = context.run_recognition_direct(
            JRecognitionType.OCR,
            ocr_param,
            argv.image
        )

        # 解析 OCR 结果
        tag_list = []
        if detail and detail.all_results:
            seen = set()
            for result in detail.all_results:
                text = result.text if hasattr(result, 'text') else ""
                box = result.box if hasattr(result, 'box') else None

                matched = _fuzzy_match(text)
                if not matched or matched in seen:
                    continue

                # 计算 box 中心点
                click_xy = None
                if box:
                    if len(box) == 4:
                        x, y, w, h = box
                        click_xy = [x + w // 2, y + h // 2]

                if not click_xy:
                    continue

                seen.add(matched)
                tag_list.append({"text": matched, "click_xy": click_xy})

        print(f"TkfmRecruit: 识别到 {len(tag_list)} 个标签 -> {[t['text'] for t in tag_list]}")

        # 返回 AnalyzeResult，detail 是 dict 类型
        return CustomRecognition.AnalyzeResult(
            box=tuple(argv.roi),
            detail={"tags": tag_list}
        )
