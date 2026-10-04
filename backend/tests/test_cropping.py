from PIL import Image
from backend.app.explain import process_crop_and_marker

def test_process_crop_and_marker():
    img = Image.new("RGB", (1000, 1000), color=(200, 200, 200))
    x, y = 0.5, 0.5
    cropped, marked, crop_b64, marked_b64 = process_crop_and_marker(img, x, y)
    
    assert cropped.size == (512, 512)
    assert marked.size == (1000, 1000)
    assert len(crop_b64) > 100
    assert len(marked_b64) > 100
