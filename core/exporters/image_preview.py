"""저장 원본을 수정하지 않고 오프라인 HTML용 JPEG 미리보기를 만든다."""
from io import BytesIO
import warnings
from PIL import Image, ImageOps


def compress(data, max_edge=1600, target_bytes=220_000):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                image = ImageOps.exif_transpose(original)
                image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                # 첫 프레임과 실제 픽셀만 보관. EXIF 등 원본 메타데이터는 내장하지 않는다.
                background = Image.new("RGB", image.size, "#0B0B0D")
                if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    background.paste(image.convert("RGB"))
                for quality in (80, 65, 50):
                    out = BytesIO()
                    background.save(out, "JPEG", quality=quality, optimize=True)
                    if out.tell() <= target_bytes: return out.getvalue()
                while max(background.size) > 400:
                    background.thumbnail(tuple(max(1, int(v * .8)) for v in background.size), Image.Resampling.LANCZOS)
                    out = BytesIO()
                    background.save(out, "JPEG", quality=50, optimize=True)
                    if out.tell() <= target_bytes: break
                return out.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None
