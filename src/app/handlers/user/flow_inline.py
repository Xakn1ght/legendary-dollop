"""Inline-keyboard bridge for the FSM money flows (purchase / charge / add-subscription).

The reply keyboards on the money path became inline keyboards, but the existing
text handlers stay the source of truth. Each prompt stores its button labels in
FSM data under ``_fkb`` (plus a generation counter ``_fkb_gen``); the buttons
carry only ``fkb:<gen>:<idx>`` so long Persian plan names never hit the 64-byte
callback_data limit. On tap, the label is resolved back to text, a synthetic
text Message is built from the tapped message, and the event is re-propagated
through the dispatcher — the same text handlers run, and typed text keeps
working in parallel.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router(name="flow_inline_bridge")


async def ikb(state: FSMContext, rows: list[list[str]]) -> InlineKeyboardMarkup:
    """Build an inline keyboard from rows of label strings.

    Labels are written to FSM data so the callback only needs an index; sending
    a new keyboard bumps the generation and expires all previous ones.
    """
    data = await state.get_data()
    gen = int(data.get("_fkb_gen") or 0) + 1
    labels: list[str] = []
    kb_rows: list[list[InlineKeyboardButton]] = []
    for row in rows:
        btns = []
        for label in row:
            btns.append(InlineKeyboardButton(text=label, callback_data=f"fkb:{gen}:{len(labels)}"))
            labels.append(label)
        kb_rows.append(btns)
    await state.update_data(_fkb_gen=gen, _fkb=labels)
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


def resolve_label(data: dict, cb_data: str) -> str | None:
    """Return the label for a fkb callback, or None if stale/invalid."""
    try:
        _, gen_s, idx_s = (cb_data or "").split(":")
        gen, idx = int(gen_s), int(idx_s)
    except ValueError:
        return None
    if gen != int(data.get("_fkb_gen") or 0):
        return None
    labels = data.get("_fkb") or []
    if not (0 <= idx < len(labels)):
        return None
    return labels[idx]


@router.callback_query(F.data.startswith("fkb:"))
async def flow_inline_tap(cb: CallbackQuery, **data):
    state: FSMContext = data["state"]
    label = resolve_label(await state.get_data(), cb.data)
    if label is None:
        await cb.answer(
            "⏳ این دکمه منقضی شده — از دکمه‌های آخرین پیام استفاده کنید.",
            show_alert=True,
        )
        return
    if not isinstance(cb.message, Message):
        await cb.answer()
        return
    await cb.answer()
    try:
        # Kill the tapped keyboard so the choice can't be double-submitted.
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    fake = cb.message.model_copy(
        update={"text": label, "from_user": cb.from_user, "entities": None, "photo": None, "caption": None}
    ).as_(cb.bot)
    # Re-propagate as a plain text message. Outer middlewares (session, rate
    # limit, FSM) already ran for this callback update — their products are in
    # `data` and flow through to the text handlers unchanged.
    dispatcher = data["dispatcher"]
    fwd = {k: v for k, v in data.items() if k not in ("event_router",)}
    await dispatcher.propagate_event("message", fake, **fwd)
