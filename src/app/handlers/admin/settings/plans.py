import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core import settings
from app.core.settings import PLANS
from app.core.settings.bootstrap import CORE_DIR
from app.shared.admin_access import ADMIN_IDS
from app.shared.plan_ordering import get_ordered_plans, save_plans_order
from app.utils.bot_i18n import t

from ._common import lang_for_tg_user
from ._previews import build_user_plan_preview

router = Router()

PLANS_FILE_PATH = CORE_DIR / "plans.json"


def _save_plans():
    """Persist current PLANS dict to a JSON file so changes survive restarts."""
    try:
        PLANS_FILE_PATH.write_text(
            json.dumps(PLANS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print("Failed to save plans.json:", e)


class PlanFieldEdit(StatesGroup):
    waiting_value = State()
    waiting_days = State()


class AddPlan(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_gb = State()
    waiting_days = State()


@router.callback_query(F.data == "plans_manage")
async def plans_manage(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return

    lang = lang_for_tg_user(cb.from_user)
    kb = InlineKeyboardBuilder()
    text_lines = [t(lang, "admin_settings_plans_title")]
    kb.button(
        text=t(lang, "admin_settings_btn_button_layout").format(cols=settings.PLANS_BUTTON_COLUMNS),
        callback_data="toggle_plans_layout",
    )
    kb.button(text=t(lang, "admin_settings_btn_positions"), callback_data="plans_positions")
    for idx, plan_name in enumerate(get_ordered_plans(), 1):
        plan = PLANS[plan_name]
        days = plan.get("days", "-")
        text_lines.append(f"{idx}. {plan_name} | 💰 {plan['price']} | 📦 {plan['gb']}GB | 📅 {days}d")
        kb.button(
            text=t(lang, "admin_settings_btn_edit_item").format(name=plan_name),
            callback_data=f"planedit_{plan_name}",
        )
        kb.button(
            text=t(lang, "admin_settings_btn_delete_item").format(name=plan_name),
            callback_data=f"plandel_{plan_name}",
        )
    kb.button(text=t(lang, "admin_settings_btn_add_new_plan"), callback_data="plan_add")
    kb.button(text=t(lang, "admin_settings_btn_back"), callback_data="close_settings")
    kb.adjust(settings.PLANS_BUTTON_COLUMNS)

    await cb.message.edit_text("\n".join(text_lines), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "toggle_plans_layout")
async def toggle_plans_layout(cb: CallbackQuery):
    new_val = 1 if settings.PLANS_BUTTON_COLUMNS == 2 else 2
    settings.save_plans_layout(new_val)
    settings.PLANS_BUTTON_COLUMNS = new_val
    await plans_manage(cb)
    lang = lang_for_tg_user(cb.from_user)
    await cb.answer(t(lang, "admin_settings_layout_set").format(cols=settings.PLANS_BUTTON_COLUMNS), show_alert=True)


@router.callback_query(F.data == "plans_positions")
async def plans_positions_menu(cb: CallbackQuery, state: FSMContext):
    order = get_ordered_plans()
    kb = InlineKeyboardBuilder()
    for idx, plan_name in enumerate(order, 1):
        kb.button(text=f"{plan_name} .{idx}", callback_data=f"pos_select_{idx}")
    kb.adjust(settings.PLANS_BUTTON_COLUMNS)
    lang = lang_for_tg_user(cb.from_user)
    kb.row(InlineKeyboardButton(text=t(lang, "admin_settings_btn_back"), callback_data="plans_manage"))
    await state.update_data(pos_selected=None, pos_order=order)
    preview = build_user_plan_preview(order)
    await cb.message.edit_text(
        t(lang, "admin_settings_select_plan_swap").format(preview=preview),
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("pos_select_"))
async def pos_select(cb: CallbackQuery, state: FSMContext):
    lang = lang_for_tg_user(cb.from_user)
    idx = int(cb.data[len("pos_select_") :]) - 1
    data = await state.get_data()
    order = list(data.get("pos_order", get_ordered_plans()))
    selected = data.get("pos_selected")
    if selected is None:
        await state.update_data(pos_selected=idx, pos_order=order)
        kb = InlineKeyboardBuilder()
        for i, plan_name in enumerate(order, 1):
            if i - 1 == idx:
                kb.button(text=f"[{plan_name} .{i}]", callback_data=f"pos_select_{i}")
            else:
                kb.button(text=f"{plan_name} .{i}", callback_data=f"pos_select_{i}")
        kb.adjust(settings.PLANS_BUTTON_COLUMNS)
        kb.row(InlineKeyboardButton(text=t(lang, "admin_settings_btn_back"), callback_data="plans_manage"))
        preview = build_user_plan_preview(order)
        await cb.message.edit_text(
            t(lang, "admin_settings_select_plan_swap_with").format(preview=preview),
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
        await cb.answer()
    else:
        order[selected], order[idx] = order[idx], order[selected]
        save_plans_order(order)
        await state.clear()
        kb = InlineKeyboardBuilder()
        for i, plan_name in enumerate(order, 1):
            kb.button(text=f"{plan_name} .{i}", callback_data=f"pos_select_{i}")
        kb.adjust(settings.PLANS_BUTTON_COLUMNS)
        kb.row(InlineKeyboardButton(text=t(lang, "admin_settings_btn_back"), callback_data="plans_manage"))
        preview = build_user_plan_preview(order)
        await cb.message.edit_text(
            t(lang, "admin_settings_swapped_new_order").format(preview=preview),
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
        await cb.answer()


@router.callback_query(F.data.startswith("planedit_"))
async def plan_edit_inline(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_name = cb.data[len("planedit_") :]
    plan = PLANS.get(plan_name)
    if not plan:
        lang = lang_for_tg_user(cb.from_user)
        await cb.answer(t(lang, "admin_settings_plan_not_found"), show_alert=True)
        return
    lang = lang_for_tg_user(cb.from_user)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "admin_settings_btn_edit_name"), callback_data=f"planfield_name_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_edit_price"), callback_data=f"planfield_price_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_edit_gb"), callback_data=f"planfield_gb_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_edit_days"), callback_data=f"planfield_days_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_save"), callback_data="plans_manage")
    kb.button(text=t(lang, "admin_settings_btn_cancel"), callback_data="plans_manage")
    kb.adjust(2)
    details = t(lang, "admin_settings_edit_plan_details").format(
        name=plan_name,
        price=plan["price"],
        gb=plan["gb"],
        days=plan.get("days", "-"),
    )
    await cb.message.edit_text(f"{t(lang, 'admin_settings_edit_plan_title')} {plan_name}\n{details}", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("planfield_"))
async def plan_field_edit(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    _, field, plan_name = cb.data.split("_", 2)
    lang = lang_for_tg_user(cb.from_user)
    await state.update_data(editing_plan=plan_name, editing_field=field)
    await cb.message.edit_text(t(lang, "admin_settings_enter_new_value").format(field=field, name=plan_name))
    await state.set_state(PlanFieldEdit.waiting_value)
    await cb.answer()


async def send_plans_menu_message(user, msg):
    kb = InlineKeyboardBuilder()
    lang = lang_for_tg_user(user)
    text_lines = [t(lang, "admin_settings_plans_title")]
    kb.button(
        text=t(lang, "admin_settings_btn_button_layout").format(cols=settings.PLANS_BUTTON_COLUMNS),
        callback_data="toggle_plans_layout",
    )
    kb.button(text=t(lang, "admin_settings_btn_positions"), callback_data="plans_positions")
    for idx, plan_name in enumerate(get_ordered_plans(), 1):
        plan = PLANS[plan_name]
        days = plan.get("days", "-")
        text_lines.append(f"{idx}. {plan_name} | 💰 {plan['price']} | 📦 {plan['gb']}GB | 📅 {days}d")
        kb.button(text=t(lang, "admin_settings_btn_edit_item").format(name=plan_name), callback_data=f"planedit_{plan_name}")
        kb.button(text=t(lang, "admin_settings_btn_delete_item").format(name=plan_name), callback_data=f"plandel_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_add_new_plan"), callback_data="plan_add")
    kb.button(text=t(lang, "admin_settings_btn_back"), callback_data="close_settings")
    kb.adjust(settings.PLANS_BUTTON_COLUMNS)
    await msg.answer("\n".join(text_lines), reply_markup=kb.as_markup())


@router.message(PlanFieldEdit.waiting_value)
async def plan_field_update(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    plan_name = data["editing_plan"] if "editing_plan" in data else data.get("plan_name")
    field = data["editing_field"] if "editing_field" in data else data.get("field")
    value = message.text.strip()
    if plan_name not in PLANS:
        await message.answer(t(lang, "admin_settings_plan_not_found"))
        return
    if field == "name":
        PLANS[value] = PLANS.pop(plan_name)
        plan_name = value
    elif field == "price":
        try:
            PLANS[plan_name]["price"] = int(value.replace(",", ""))
        except Exception:
            await message.answer(t(lang, "admin_settings_invalid_price"))
            return
    elif field == "gb":
        try:
            PLANS[plan_name]["gb"] = int(value.replace(",", ""))
        except Exception:
            await message.answer(t(lang, "admin_settings_invalid_gb"))
            return
    elif field == "days":
        try:
            PLANS[plan_name]["days"] = int(value.replace(",", ""))
        except Exception:
            await message.answer(t(lang, "admin_settings_invalid_days"))
            return
    _save_plans()
    await message.answer(t(lang, "admin_settings_updated_ok"))
    await state.clear()
    await send_plans_menu_message(message.from_user, message)


@router.callback_query(F.data == "plan_add")
async def plan_add_inline(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(new_plan={})
    lang = lang_for_tg_user(cb.from_user)
    await cb.message.edit_text(t(lang, "admin_settings_enter_name_new_plan"))
    await state.set_state(AddPlan.waiting_name)
    await cb.answer()


@router.message(AddPlan.waiting_name)
async def plan_add_name(message: Message, state: FSMContext):
    await state.update_data(new_plan={"name": message.text.strip()})
    lang = lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_settings_enter_price_new_plan"))
    await state.set_state(AddPlan.waiting_price)


@router.message(AddPlan.waiting_price)
async def plan_add_price(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    new_plan = data.get("new_plan", {})
    try:
        price = int(message.text.strip().replace(",", ""))
    except Exception:
        await message.answer(t(lang, "admin_settings_invalid_price_number"))
        return
    new_plan["price"] = price
    await state.update_data(new_plan=new_plan)
    await message.answer(t(lang, "admin_settings_enter_gb_new_plan"))
    await state.set_state(AddPlan.waiting_gb)


@router.message(AddPlan.waiting_gb)
async def plan_add_gb(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    new_plan = data.get("new_plan", {})
    try:
        gb = int(message.text.strip().replace(",", ""))
    except Exception:
        await message.answer(t(lang, "admin_settings_invalid_gb_number"))
        return
    new_plan["gb"] = gb
    await state.update_data(new_plan=new_plan)
    await message.answer(t(lang, "admin_settings_enter_days_new_plan"))
    await state.set_state(AddPlan.waiting_days)


@router.message(AddPlan.waiting_days)
async def plan_add_days(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    new_plan = data.get("new_plan", {})
    try:
        days = int(message.text.strip().replace(",", ""))
    except Exception:
        await message.answer(t(lang, "admin_settings_invalid_days_number"))
        return
    name = new_plan["name"]
    PLANS[name] = {"price": new_plan["price"], "gb": new_plan["gb"], "days": days}
    _save_plans()
    await message.answer(t(lang, "admin_settings_plan_added").format(name=name))
    await state.clear()
    await send_plans_menu_message(message.from_user, message)


@router.callback_query(F.data.startswith("plandel_"))
async def plan_delete_inline(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    plan_name = cb.data[len("plandel_") :]
    if plan_name in PLANS:
        del PLANS[plan_name]
        _save_plans()
        lang = lang_for_tg_user(cb.from_user)
        await cb.answer(t(lang, "admin_settings_plan_deleted").format(name=plan_name), show_alert=True)
    else:
        lang = lang_for_tg_user(cb.from_user)
        await cb.answer(t(lang, "admin_settings_plan_not_found"), show_alert=True)
    await plans_manage(cb)
