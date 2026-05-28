from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.settings import (
    CHARGE_RATE_PER_DAY,
    DAY_PLANS,
    JOB_SCHEDULES,
    SUPPORT_AVG_HANDLE_MINUTES,
    SUPPORT_TICKET_AUTOCLOSE_DAYS,
    SUPPORT_TICKET_REMINDER_HOURS,
    save_job_schedules,
    save_support_settings,
)
from app.shared.admin_access import ADMIN_IDS

from .menu import admin_settings_menu

router = Router()

# Persian-friendly job names for display
JOB_DISPLAY_NAMES = {
    "update_user_analytics_job": "به‌روزرسانی آمار کاربران",
    "check_low_data_job": "بررسی حجم کم سرویس‌ها",
    "renewal_job": "بررسی تمدید سرویس‌ها",
}


def _day_plans_kb_and_text():
    kb = InlineKeyboardBuilder()
    lines = ["📅 پلن‌های زمانی (خرید روز):"]
    for name, cfg in DAY_PLANS.items():
        price = cfg.get("price", cfg.get("days", 0) * CHARGE_RATE_PER_DAY)
        days = cfg.get("days", 0)
        lines.append(f"- {name} | {days} روز | {price:,} تومان")
        kb.button(text=f"✏️ ویرایش {name}", callback_data=f"dayplan_edit_{name}")
        kb.button(text=f"🗑️ حذف {name}", callback_data=f"dayplan_del_{name}")
    kb.button(text="➕ افزودن پلن", callback_data="dayplan_add")
    kb.button(text="⬅️ بازگشت", callback_data="close_settings")
    kb.adjust(1)
    return "\n".join(lines), kb


@router.callback_query(F.data == "jobs_manage")
async def jobs_manage(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardBuilder()
    for job, conf in JOB_SCHEDULES.items():
        display = JOB_DISPLAY_NAMES.get(job, job)
        kb.button(text=f"{display}", callback_data=f"jobedit_{job}")
    kb.button(text="⬅️ بازگشت", callback_data="close_settings")
    kb.adjust(1)
    await cb.message.edit_text("⏰ لیست وظایف زمان‌بندی شده:", reply_markup=kb.as_markup())
    await cb.answer()


class SupportEditState(StatesGroup):
    waiting_reminder = State()
    waiting_autoclose = State()
    waiting_avg_handle = State()


@router.callback_query(F.data == "support_settings")
async def support_settings_menu(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    text = (
        "🆘 تنظیمات پشتیبانی\n\n"
        f"⏰ یادآوری پاسخ کاربر: هر {SUPPORT_TICKET_REMINDER_HOURS} ساعت\n"
        f"📅 بستن خودکار: پس از {SUPPORT_TICKET_AUTOCLOSE_DAYS} روز بدون پاسخ\n\n"
        f"📈 زمان متوسط رسیدگی: {SUPPORT_AVG_HANDLE_MINUTES} دقیقه\n\n"
        "یک گزینه را انتخاب کنید:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ تغییر ساعت یادآوری", callback_data="edit_support_reminder")
    kb.button(text="✏️ تغییر روز بستن خودکار", callback_data="edit_support_autoclose")
    kb.button(text="✏️ تغییر زمان متوسط رسیدگی", callback_data="edit_support_avg_handle")
    kb.button(text="🔙 بازگشت", callback_data="close_settings")
    kb.adjust(1)
    await cb.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "edit_support_reminder")
async def edit_support_reminder_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SupportEditState.waiting_reminder)
    await cb.message.edit_text("ساعت‌های بین یادآوری را وارد کنید (عدد صحیح 1-24):")


@router.message(SupportEditState.waiting_reminder)
async def edit_support_reminder_save(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if not (1 <= value <= 24):
            raise ValueError
        save_support_settings(reminder_hours=value)
        await message.answer(f"✅ یادآوری هر {value} ساعت تنظیم شد.")
        await state.clear()
        await admin_settings_menu(message)
    except ValueError:
        await message.answer("مقدار نامعتبر است. یک عدد صحیح بین 1 تا 24 وارد کنید:")


@router.callback_query(F.data == "edit_support_autoclose")
async def edit_support_autoclose_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SupportEditState.waiting_autoclose)
    await cb.message.edit_text("تعداد روز برای بستن خودکار را وارد کنید (عدد صحیح 1-30):")


@router.message(SupportEditState.waiting_autoclose)
async def edit_support_autoclose_save(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if not (1 <= value <= 30):
            raise ValueError
        save_support_settings(autoclose_days=value)
        await message.answer(f"✅ بستن خودکار پس از {value} روز تنظیم شد.")
        await state.clear()
        await admin_settings_menu(message)
    except ValueError:
        await message.answer("مقدار نامعتبر است. یک عدد صحیح بین 1 تا 30 وارد کنید:")


@router.callback_query(F.data == "edit_support_avg_handle")
async def edit_support_avg_handle_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SupportEditState.waiting_avg_handle)
    await cb.message.edit_text("زمان متوسط رسیدگی (دقیقه) را وارد کنید (عدد صحیح 1-120):")


@router.message(SupportEditState.waiting_avg_handle)
async def edit_support_avg_handle_save(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if not (1 <= value <= 120):
            raise ValueError
        save_support_settings(avg_handle_minutes=value)
        await message.answer(f"✅ زمان متوسط رسیدگی: {value} دقیقه")
        await state.clear()
        await admin_settings_menu(message)
    except ValueError:
        await message.answer("مقدار نامعتبر است. یک عدد صحیح بین 1 تا 120 وارد کنید:")


@router.callback_query(F.data == "day_plans_manage")
async def day_plans_manage(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    text, kb = _day_plans_kb_and_text()
    await cb.message.edit_text(text, reply_markup=kb.as_markup())
    await cb.answer()


class DayPlanState(StatesGroup):
    waiting_name = State()
    waiting_days = State()
    waiting_price = State()


@router.callback_query(F.data == "dayplan_add")
async def dayplan_add_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(DayPlanState.waiting_name)
    await cb.message.edit_text("نام پلن جدید را وارد کنید:")
    await cb.answer()


@router.message(DayPlanState.waiting_name)
async def dayplan_add_name(message: Message, state: FSMContext):
    await state.update_data(dp_name=message.text.strip())
    await state.set_state(DayPlanState.waiting_days)
    await message.answer("تعداد روز را وارد کنید:")


@router.message(DayPlanState.waiting_days)
async def dayplan_add_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except Exception:
        await message.answer("عدد روز نامعتبر است. دوباره ارسال کنید:")
        return
    await state.update_data(dp_days=days)
    await state.set_state(DayPlanState.waiting_price)
    await message.answer(f"قیمت (تومان) را وارد کنید (پیشنهادی: {days * CHARGE_RATE_PER_DAY:,}):")


@router.message(DayPlanState.waiting_price)
async def dayplan_add_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(",", ""))
        if price <= 0:
            raise ValueError
    except Exception:
        await message.answer("قیمت نامعتبر است. دوباره ارسال کنید:")
        return
    data = await state.get_data()
    name = data.get("dp_name")
    days = data.get("dp_days")
    DAY_PLANS[name] = {"days": days, "price": price}
    await state.clear()
    text, kb = _day_plans_kb_and_text()
    await message.edit_text("✅ پلن زمانی اضافه شد.\n\n" + text, reply_markup=kb.as_markup())


class EditJobSchedule(StatesGroup):
    waiting_field = State()
    waiting_value = State()
    editing_job = State()


@router.callback_query(F.data.startswith("jobedit_"))
async def job_edit_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    job = cb.data[8:]
    if job not in JOB_SCHEDULES:
        await cb.answer("وظیفه یافت نشد.", show_alert=True)
        return
    conf = JOB_SCHEDULES[job]
    kb = InlineKeyboardBuilder()
    for k, v in conf.items():
        if k == "type":
            continue
        kb.button(text=f"{k}: {v}", callback_data=f"jobfield_{job}_{k}")
    kb.button(text="⬅️ بازگشت", callback_data="jobs_manage")
    kb.adjust(1)
    display = JOB_DISPLAY_NAMES.get(job, job)
    text = f"⚙️ تنظیمات زمان‌بندی برای {display}:\n" + "\n".join([f"{k}: {v}" for k, v in conf.items()])
    await cb.message.edit_text(text, reply_markup=kb.as_markup())
    await state.update_data(editing_job=job)
    await cb.answer()


@router.callback_query(F.data.startswith("jobfield_"))
async def job_field_edit_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS:
        return
    data = cb.data[len("jobfield_") :]
    job, field = data.rsplit("_", 1)
    await state.update_data(editing_job=job, editing_field=field)
    await cb.message.edit_text(f"مقدار جدید برای {field} را وارد کنید:")
    await state.set_state(EditJobSchedule.waiting_value)
    await cb.answer()


@router.message(EditJobSchedule.waiting_value)
async def job_field_update(message: Message, state: FSMContext):
    data = await state.get_data()
    job = data["editing_job"]
    field = data["editing_field"]
    value = message.text.strip()
    try:
        value = int(value)
    except Exception:
        pass
    if job in JOB_SCHEDULES:
        JOB_SCHEDULES[job][field] = value
        save_job_schedules()
        await message.answer(f"✅ مقدار {field} برای {job} به {value} تغییر یافت.")
    else:
        await message.answer("وظیفه یافت نشد.")
    await state.clear()
