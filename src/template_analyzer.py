"""Analyze a .pptx template to extract its dimensions and safe area."""
from pptx import Presentation


def analyze_template(template_path: str) -> dict:
    """
    Read a .pptx template and return its profile.

    Returns a dict with:
    - slide_width / slide_height (inches)
    - slide_count
    - template_type ("plain_canvas" — we never require editable placeholders)
    - has_editable_placeholders (bool)
    - safe_area: {left, top, right, bottom} in inches — the usable text zone
    """
    prs = Presentation(template_path)

    width_in = prs.slide_width.inches
    height_in = prs.slide_height.inches

    # Detect editable placeholders on the first slide
    has_placeholders = False
    if prs.slides:
        for shape in prs.slides[0].shapes:
            if shape.has_text_frame and shape.shape_type == 14:  # MSO_SHAPE_TYPE.PLACEHOLDER
                has_placeholders = True
                break

    # Safe area — fixed for the TurnB branded template
    # Left margin clears the diamond graphic, right clears the logo
    safe_area = {
        "left": 0.70,
        "top": 1.10,
        "right": 12.60,
        "bottom": 6.80,
    }

    return {
        "slide_width": round(width_in, 3),
        "slide_height": round(height_in, 3),
        "slide_count": len(prs.slides),
        "template_type": "plain_canvas",
        "has_editable_placeholders": has_placeholders,
        "safe_area": safe_area,
    }
