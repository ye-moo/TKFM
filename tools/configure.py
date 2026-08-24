from pathlib import Path
import shutil

# 项目根目录
root_dir = Path(__file__).parent.parent.resolve()

# 修改：不再指向assets，直接指向仓库根目录
maa_common_assets_dir = root_dir / "MaaCommonAssets"
target_ocr_dir = root_dir / "resource" / "model" / "ocr"


def configure_ocr_model():
    assets_ocr_dir = maa_common_assets_dir / "OCR"
    if not assets_ocr_dir.exists():
        print(f"File Not Found: {assets_ocr_dir}")
        exit(1)

    if not target_ocr_dir.exists():
        # 拷贝默认ppocr_v6 small模型到 resource/model/ocr
        shutil.copytree(
            maa_common_assets_dir / "OCR" / "ppocr_v6" / "small",
            target_ocr_dir,
            dirs_exist_ok=True,
        )
    else:
        print("Found existing OCR directory, skipping default OCR model import.")


if __name__ == "__main__":
    configure_ocr_model()
    print("OCR model configured.")
