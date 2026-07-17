from aiogram import Router
from aiogram.fsm.state import State, StatesGroup

router = Router()

_last_link_click = {}
_last_text_refresh = {}
_last_image_refresh = {}


class ServiceManagementState(StatesGroup):
    charge_amount = State()
