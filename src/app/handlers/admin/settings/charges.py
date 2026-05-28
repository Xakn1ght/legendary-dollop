from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core import settings
from app.core.settings import CHARGE_PRESET_PACKAGES, save_charge_packages
from app.shared.admin_access import ADMIN_IDS
from app.shared.plan_ordering import get_ordered_charge_plans, save_charge_plans_order
from app.utils.bot_i18n import t

from ._common import lang_for_tg_user
from ._previews import build_charge_plan_preview
from .menu import admin_settings_menu

router = Router()


class AddChargePlan(StatesGroup):
    waiting_name = State()
    waiting_price = State()
    waiting_gb = State()
    waiting_days = State()


class EditChargePlanField(StatesGroup):
    waiting_value = State()


@router.callback_query(F.data == "packages_manage")
async def charge_plans_manage(cb: CallbackQuery):
    kb = InlineKeyboardBuilder()
    lang = lang_for_tg_user(cb.from_user)
    text_lines = [t(lang, "admin_settings_charge_packages_title")]

    kb.button(
        text=t(lang, "admin_settings_btn_button_layout").format(cols=settings.CHARGE_PLANS_BUTTON_COLUMNS),
        callback_data="toggle_charge_plans_layout",
    )
    kb.button(text=t(lang, "admin_settings_btn_positions"), callback_data="charge_plans_positions")

    for idx, plan_name in enumerate(get_ordered_charge_plans(), 1):
        plan = CHARGE_PRESET_PACKAGES[plan_name]
        price = plan.get("price", "N/A")
        gb = plan.get("gb", "-")
        days = plan.get("days", "-")
        text_lines.append(f"{idx}. {plan_name} | 💰 {price} | 📦 {gb}GB | 📅 {days}d")
        kb.button(
            text=t(lang, "admin_settings_btn_edit_item").format(name=plan_name),
            callback_data=f"chargeplanedit_{plan_name}",
        )
        kb.button(
            text=t(lang, "admin_settings_btn_delete_item").format(name=plan_name),
            callback_data=f"chargeplandel_{plan_name}",
        )

    kb.button(text=t(lang, "admin_settings_btn_add_new_package"), callback_data="chargeplan_add")
    kb.button(text=t(lang, "admin_settings_btn_back"), callback_data="close_settings")
    kb.adjust(2)

    await cb.message.edit_text("\n".join(text_lines), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "toggle_charge_plans_layout")
async def toggle_charge_plans_layout(cb: CallbackQuery):
    new_val = 1 if settings.CHARGE_PLANS_BUTTON_COLUMNS == 2 else 2
    settings.save_charge_plans_layout(new_val)
    settings.CHARGE_PLANS_BUTTON_COLUMNS = new_val
    await charge_plans_manage(cb)
    lang = lang_for_tg_user(cb.from_user)
    await cb.answer(t(lang, "admin_settings_layout_set").format(cols=new_val), show_alert=True)


@router.callback_query(F.data == "charge_plans_positions")
async def charge_plans_positions_menu(cb: CallbackQuery, state: FSMContext):
    order = get_ordered_charge_plans()
    kb = InlineKeyboardBuilder()
    for idx, plan_name in enumerate(order, 1):
        kb.button(text=f"{plan_name} .{idx}", callback_data=f"charge_pos_select_{idx}")
    kb.adjust(settings.CHARGE_PLANS_BUTTON_COLUMNS)
    lang = lang_for_tg_user(cb.from_user)
    kb.row(InlineKeyboardButton(text=t(lang, "admin_settings_btn_back"), callback_data="packages_manage"))
    await state.update_data(pos_selected=None, pos_order=order)
    preview = build_charge_plan_preview(order)
    await cb.message.edit_text(
        t(lang, "admin_settings_select_plan_swap").format(preview=preview),
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("charge_pos_select_"))
async def charge_pos_select(cb: CallbackQuery, state: FSMContext):
    lang = lang_for_tg_user(cb.from_user)
    idx = int(cb.data[len("charge_pos_select_") :]) - 1
    data = await state.get_data()
    order = list(data.get("pos_order", get_ordered_charge_plans()))
    selected = data.get("pos_selected")
    if selected is None:
        await state.update_data(pos_selected=idx, pos_order=order)
        kb = InlineKeyboardBuilder()
        for i, plan_name in enumerate(order, 1):
            if i - 1 == idx:
                kb.button(text=f"[{plan_name} .{i}]", callback_data=f"charge_pos_select_{i}")
            else:
                kb.button(text=f"{plan_name} .{i}", callback_data=f"charge_pos_select_{i}")
        kb.adjust(settings.CHARGE_PLANS_BUTTON_COLUMNS)
        lang = lang_for_tg_user(cb.from_user)
        kb.row(InlineKeyboardButton(text=t(lang, "admin_settings_btn_back"), callback_data="packages_manage"))
        preview = build_charge_plan_preview(order)
        await cb.message.edit_text(
            t(lang, "admin_settings_select_plan_swap_with").format(preview=preview),
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
        await cb.answer()
    else:
        order[selected], order[idx] = order[idx], order[selected]
        save_charge_plans_order(order)
        await state.clear()
        kb = InlineKeyboardBuilder()
        for i, plan_name in enumerate(order, 1):
            kb.button(text=f"{plan_name} .{i}", callback_data=f"charge_pos_select_{i}")
        kb.adjust(settings.CHARGE_PLANS_BUTTON_COLUMNS)
        kb.row(InlineKeyboardButton(text=t(lang, "admin_settings_btn_back"), callback_data="packages_manage"))
        preview = build_charge_plan_preview(order)
        await cb.message.edit_text(
            t(lang, "admin_settings_swapped_new_order").format(preview=preview),
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )
        await cb.answer()


@router.callback_query(F.data.startswith("chargeplanedit_"))
async def charge_plan_edit_inline(cb: CallbackQuery):
    plan_name = cb.data[len("chargeplanedit_") :]
    plan = CHARGE_PRESET_PACKAGES.get(plan_name)
    if not plan:
        lang = lang_for_tg_user(cb.from_user)
        await cb.answer(t(lang, "admin_settings_package_not_found"), show_alert=True)
        return
    lang = lang_for_tg_user(cb.from_user)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "admin_settings_btn_edit_name"), callback_data=f"chargeplanfield_name_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_edit_price"), callback_data=f"chargeplanfield_price_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_edit_gb"), callback_data=f"chargeplanfield_gb_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_edit_days"), callback_data=f"chargeplanfield_days_{plan_name}")
    kb.button(text=t(lang, "admin_settings_btn_save"), callback_data="packages_manage")
    kb.button(text=t(lang, "admin_settings_btn_cancel"), callback_data="packages_manage")
    kb.adjust(2)
    details = t(lang, "admin_settings_edit_package_details").format(
        price=plan.get("price", "N/A"),
        gb=plan.get("gb", "-"),
        days=plan.get("days", "-"),
    )
    await cb.message.edit_text(f"{t(lang, 'admin_settings_edit_package_title')} {plan_name}\n{details}", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("chargeplanfield_"))
async def charge_plan_field_edit(cb: CallbackQuery, state: FSMContext):
    _, field, plan_name = cb.data.split("_", 2)
    lang = lang_for_tg_user(cb.from_user)
    await state.update_data(editing_plan=plan_name, editing_field=field)
    await cb.message.edit_text(t(lang, "admin_settings_enter_new_value").format(field=field, name=plan_name))
    await state.set_state(EditChargePlanField.waiting_value)
    await cb.answer()


@router.message(EditChargePlanField.waiting_value)
async def charge_plan_field_update(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    plan_name = data["editing_plan"]
    field = data["editing_field"]
    value = message.text.strip()

    if plan_name not in CHARGE_PRESET_PACKAGES:
        await message.answer(t(lang, "admin_settings_package_not_found"))
        return

    if field == "name":
        CHARGE_PRESET_PACKAGES[value] = CHARGE_PRESET_PACKAGES.pop(plan_name)
    elif field == "price":
        try:
            CHARGE_PRESET_PACKAGES[plan_name]["price"] = int(value.replace(",", ""))
        except ValueError:
            await message.answer(t(lang, "admin_settings_invalid_price"))
            return
    elif field == "gb":
        try:
            val = int(value.replace(",", ""))
            if val > 0:
                CHARGE_PRESET_PACKAGES[plan_name]["gb"] = val
            else:
                CHARGE_PRESET_PACKAGES[plan_name].pop("gb", None)
        except ValueError:
            await message.answer(t(lang, "admin_settings_invalid_gb"))
            return
    elif field == "days":
        try:
            val = int(value.replace(",", ""))
            if val > 0:
                CHARGE_PRESET_PACKAGES[plan_name]["days"] = val
            else:
                CHARGE_PRESET_PACKAGES[plan_name].pop("days", None)
        except ValueError:
            await message.answer(t(lang, "admin_settings_invalid_days"))
            return

    save_charge_packages(CHARGE_PRESET_PACKAGES)
    await message.answer(t(lang, "admin_settings_updated_ok"))
    await state.clear()
    await admin_settings_menu(message)


@router.callback_query(F.data == "chargeplan_add")
async def charge_plan_add_inline(cb: CallbackQuery, state: FSMContext):
    await state.update_data(new_plan={})
    lang = lang_for_tg_user(cb.from_user)
    await cb.message.edit_text(t(lang, "admin_settings_enter_name_new_package"))
    await state.set_state(AddChargePlan.waiting_name)
    await cb.answer()


@router.message(AddChargePlan.waiting_name)
async def charge_plan_add_name(message: Message, state: FSMContext):
    await state.update_data(new_plan={"name": message.text.strip()})
    lang = lang_for_tg_user(message.from_user)
    await message.answer(t(lang, "admin_settings_enter_price_new_package"))
    await state.set_state(AddChargePlan.waiting_price)


@router.message(AddChargePlan.waiting_price)
async def charge_plan_add_price(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    new_plan = data.get("new_plan", {})
    try:
        price = int(message.text.strip().replace(",", ""))
        new_plan["price"] = price
        await state.update_data(new_plan=new_plan)
        await message.answer(t(lang, "admin_settings_enter_gb_new_package"))
        await state.set_state(AddChargePlan.waiting_gb)
    except ValueError:
        await message.answer(t(lang, "admin_settings_invalid_price_number"))


@router.message(AddChargePlan.waiting_gb)
async def charge_plan_add_gb(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    new_plan = data.get("new_plan", {})
    try:
        gb = int(message.text.strip().replace(",", ""))
        if gb > 0:
            new_plan["gb"] = gb
        await state.update_data(new_plan=new_plan)
        await message.answer(t(lang, "admin_settings_enter_days_new_package"))
        await state.set_state(AddChargePlan.waiting_days)
    except ValueError:
        await message.answer(t(lang, "admin_settings_invalid_gb_number"))


@router.message(AddChargePlan.waiting_days)
async def charge_plan_add_days(message: Message, state: FSMContext):
    lang = lang_for_tg_user(message.from_user)
    data = await state.get_data()
    new_plan = data.get("new_plan", {})
    try:
        days = int(message.text.strip().replace(",", ""))
        if days > 0:
            new_plan["days"] = days

        name = new_plan.pop("name")
        CHARGE_PRESET_PACKAGES[name] = new_plan
        save_charge_packages(CHARGE_PRESET_PACKAGES)

        await message.answer(t(lang, "admin_settings_package_added").format(name=name))
        await state.clear()
        await admin_settings_menu(message)
    except ValueError:
        await message.answer(t(lang, "admin_settings_invalid_days_number"))


@router.callback_query(F.data.startswith("chargeplandel_"))
async def charge_plan_delete_inline(cb: CallbackQuery):
    plan_name = cb.data[len("chargeplandel_") :]
    if plan_name in CHARGE_PRESET_PACKAGES:
        del CHARGE_PRESET_PACKAGES[plan_name]
        save_charge_packages(CHARGE_PRESET_PACKAGES)
        lang = lang_for_tg_user(cb.from_user)
        await cb.answer(t(lang, "admin_settings_package_deleted").format(name=plan_name), show_alert=True)
    else:
        lang = lang_for_tg_user(cb.from_user)
        await cb.answer(t(lang, "admin_settings_package_not_found"), show_alert=True)
    await charge_plans_manage(cb)
