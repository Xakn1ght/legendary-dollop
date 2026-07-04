"""Offline tests for ASTROBYTE's SMS auto-approval core (no DB, no Telegram).

Run: PYTHONPATH=src python tests/test_sms_autoapprove.py
Loads the pure module by path so it needs no app package / env.
"""
import importlib.util
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "src", "app")


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s = _load("services/sms_autoapprove.py", "sms_autoapprove")

SMS1 = (
    "New SMS\nFrom: PARSIANBANK\n80000523451006\nمبلغ:+850,000\nمانده:524,127,448\n04/13\n23:07\n"
    "بابت :انتقال از کارت 6219861908723264 به کارت 6221061103953057 "
    "با شماره بازیابی 178319384569 با شماره پیگیری 248125"
)
SMS_FA = ("مبلغ:+۱۷۰٬۰۰۰\nانتقال از کارت ۶۰۳۷۹۹******۴۵۶۷ به کارت ۶۲۲۱۰۶۱۱۰۳۹۵۳۰۵۷ "
          "با شماره پیگیری ۹۹۰۰۱")
SMS_DEBIT = "مبلغ:-500,000\nبرداشت از کارت 6221061103953057 با شماره پیگیری 111"


def test_parse():
    d = s.parse_bank_sms(SMS1)
    assert d and d['amount'] == 850000 and d['source_last4'] == '3264'
    assert d['dest_last4'] == '3057' and d['tracking'] == '248125'


def test_parse_fa():
    d = s.parse_bank_sms(SMS_FA)
    assert d['amount'] == 170000 and d['source_last4'] == '4567' and d['tracking'] == '99001'


def test_debit_and_garbage():
    assert s.parse_bank_sms(SMS_DEBIT) is None
    assert s.parse_bank_sms('nope') is None


def test_dest_filter():
    d = s.parse_bank_sms(SMS1)
    assert s.dest_card_allowed(d, {'3057'}) and not s.dest_card_allowed(d, {'9999'})
    assert s.dest_card_allowed(d, set())


def test_match_unique_typed_ids():
    d = s.parse_bank_sms(SMS1)
    cands = [
        {'order_id': 'sub:11', 'amount': 850000, 'receipt_ts': 1000, 'receipt_last4': None},
        {'order_id': 'charge:4', 'amount': 170000, 'receipt_ts': 1000, 'receipt_last4': None},
        {'order_id': 'vip:2', 'amount': 300000, 'receipt_ts': 1000, 'receipt_last4': None},
    ]
    assert s.pick_match(d, cands, 1200, 2700) == ('approve', 'sub:11')


def test_match_none_and_window():
    d = s.parse_bank_sms(SMS1)
    cands = [{'order_id': 'sub:1', 'amount': 850000, 'receipt_ts': 1000, 'receipt_last4': None}]
    assert s.pick_match(d, cands, 999999, 2700) == ('none', [])
    assert s.pick_match(d, [{'order_id': 'x', 'amount': 1, 'receipt_ts': 1000}], 1200, 2700) == ('none', [])


def test_match_ambiguous_then_card_breaks():
    d = s.parse_bank_sms(SMS1)  # source 3264
    amb = [
        {'order_id': 'sub:1', 'amount': 850000, 'receipt_ts': 1000, 'receipt_last4': None},
        {'order_id': 'charge:2', 'amount': 850000, 'receipt_ts': 1100, 'receipt_last4': None},
    ]
    k, ids = s.pick_match(d, amb, 1200, 2700)
    assert k == 'ambiguous' and set(ids) == {'sub:1', 'charge:2'}
    carded = [
        {'order_id': 'sub:1', 'amount': 850000, 'receipt_ts': 1000, 'receipt_last4': '0000'},
        {'order_id': 'charge:2', 'amount': 850000, 'receipt_ts': 1100, 'receipt_last4': '3264'},
    ]
    assert s.pick_match(d, carded, 1200, 2700) == ('approve', 'charge:2')


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
        print('PASS', fn.__name__)
    print(f'\nAll {len(fns)} ASTROBYTE SMS-autoapprove tests passed.')
