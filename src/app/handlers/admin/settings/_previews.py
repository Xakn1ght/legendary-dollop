def build_user_plan_preview(order):
    """Builds an HTML preview of the plan buttons for the user."""
    from app.core.settings import PLANS, PLANS_BUTTON_COLUMNS

    keys = order
    preview_html = "\n\n<b>User Preview:</b>\n"

    button_grid = []
    for i in range(0, len(keys), PLANS_BUTTON_COLUMNS):
        row = [keys[j] for j in range(i, min(i + PLANS_BUTTON_COLUMNS, len(keys)))]
        button_grid.append(row)

    if not button_grid:
        return ""

    for row in button_grid:
        display_row = row[::-1]
        row_str = "   |   ".join(f"<b>{plan_name}</b>" for plan_name in display_row)
        preview_html += f"{row_str}\n"

    return preview_html


def build_charge_plan_preview(order):
    """Builds an HTML preview of the charge plan buttons for the user."""
    from app.core.settings import CHARGE_PLANS_BUTTON_COLUMNS, CHARGE_PRESET_PACKAGES

    keys = order
    preview_html = "\n\n<b>User Preview:</b>\n"

    button_grid = []
    for i in range(0, len(keys), CHARGE_PLANS_BUTTON_COLUMNS):
        row = [keys[j] for j in range(i, min(i + CHARGE_PLANS_BUTTON_COLUMNS, len(keys)))]
        button_grid.append(row)

    if not button_grid:
        return ""

    for row in button_grid:
        display_row = row[::-1]
        row_str = "   |   ".join(f"<b>{plan_name}</b>" for plan_name in display_row)
        preview_html += f"{row_str}\n"

    return preview_html
