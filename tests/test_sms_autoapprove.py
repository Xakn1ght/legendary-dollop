"""Offline tests for ASTROBYTE's SMS auto-approval core (no DB, no Telegram).

Run: PYTHONPATH=src python tests/test_sms_autoapprove.py
Loads the pure module by path so it needs no app package / env.

Units: bank SMS amounts are RIAL; order/candidate amounts are TOMAN.
850,000 rial == 85,000 toman.
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
# Real deposit as forwarded on Jul 5 — note the TRAILING plus (RTL rendering).
SMS_TRAILING = (
    "80000523451006\nمبلغ:850,000+\nمانده:552,577,448\n04/14\n14:13\n"
    "بابت :انتقال از کارت 6219861428977804 به کارت 6221061103953057 "
    "با شماره بازیابی 178324819389 با شماره پیگیری 266579"
)
SMS_FA = ("مبلغ:+۱۷۰٬۰۰۰\nانتقال از کارت ۶۰۳۷۹۹******۴۵۶۷ به کارت ۶۲۲۱۰۶۱۱۰۳۹۵۳۰۵۷ "
          "با شماره پیگیری ۹۹۰۰۱")
SMS_DEBIT = "مبلغ:-500,000\nبرداشت از کارت 6221061103953057 با شماره پیگیری 111"
SMS_DEBIT_TRAILING = "مبلغ:500,000-\nمانده:10,000\nانتقال از کارت 6221061103953057 با شماره پیگیری 112"
SMS_DEBIT_NO_SIGN = "مبلغ:500,000\nمانده:10,000\nبرداشت از کارت 6221061103953057 با شماره پیگیری 113"


def test_parse():
    d = s.parse_bank_sms(SMS1)
    assert d and d['amount'] == 850000 and d['source_last4'] == '3264'
    assert d['dest_last4'] == '3057' and d['tracking'] == '248125'
    assert d['amount_unit'] == 'rial'


def test_parse_trailing_plus():
    d = s.parse_bank_sms(SMS_TRAILING)
    assert d is not None, 'trailing + (RTL) must still parse as a credit'
    assert d['amount'] == 850000 and d['source_last4'] == '7804'
    assert d['tracking'] == '266579' and d['retrieval'] == '178324819389'


def test_parse_fa():
    d = s.parse_bank_sms(SMS_FA)
    assert d['amount'] == 170000 and d['source_last4'] == '4567' and d['tracking'] == '99001'


def test_debit_and_garbage():
    assert s.parse_bank_sms(SMS_DEBIT) is None
    assert s.parse_bank_sms(SMS_DEBIT_TRAILING) is None, 'trailing minus is a debit'
    assert s.parse_bank_sms(SMS_DEBIT_NO_SIGN) is None, 'برداشت without + is a debit'
    assert s.parse_bank_sms('nope') is None


def test_amount_toman_conversion():
    d = s.parse_bank_sms(SMS1)
    assert s.deposit_amount_toman(d) == 85000  # 850,000 rial -> 85,000 toman
    assert s.deposit_amount_toman({'amount': 850000, 'amount_unit': 'toman'}) == 850000
    assert s.deposit_amount_toman({'amount': 850005}) is None  # not divisible by 10
    assert s.deposit_amount_toman({'amount': 850000}) == 85000  # legacy pooled deposit


def test_dest_filter():
    d = s.parse_bank_sms(SMS1)
    assert s.dest_card_allowed(d, {'3057'}) and not s.dest_card_allowed(d, {'9999'})
    assert s.dest_card_allowed(d, set())


def test_match_unique_typed_ids():
    d = s.parse_bank_sms(SMS1)  # 850,000 rial == 85,000 toman
    cands = [
        {'order_id': 'sub:11', 'amount': 85000, 'receipt_ts': 1000, 'receipt_last4': None},
        {'order_id': 'charge:4', 'amount': 17000, 'receipt_ts': 1000, 'receipt_last4': None},
        {'order_id': 'vip:2', 'amount': 30000, 'receipt_ts': 1000, 'receipt_last4': None},
    ]
    assert s.pick_match(d, cands, 1200, 2700) == ('approve', 'sub:11')


def test_match_rial_never_compared_raw():
    d = s.parse_bank_sms(SMS1)
    # An order priced at the RAW rial figure must NOT match (that would be 10x).
    cands = [{'order_id': 'sub:9', 'amount': 850000, 'receipt_ts': 1000, 'receipt_last4': None}]
    assert s.pick_match(d, cands, 1200, 2700) == ('none', [])


def test_match_none_and_window():
    d = s.parse_bank_sms(SMS1)
    cands = [{'order_id': 'sub:1', 'amount': 85000, 'receipt_ts': 1000, 'receipt_last4': None}]
    assert s.pick_match(d, cands, 999999, 2700) == ('none', [])
    assert s.pick_match(d, [{'order_id': 'x', 'amount': 1, 'receipt_ts': 1000}], 1200, 2700) == ('none', [])


def test_match_ambiguous_then_card_breaks():
    d = s.parse_bank_sms(SMS1)  # source 3264
    amb = [
        {'order_id': 'sub:1', 'amount': 85000, 'receipt_ts': 1000, 'receipt_last4': None},
        {'order_id': 'charge:2', 'amount': 85000, 'receipt_ts': 1100, 'receipt_last4': None},
    ]
    k, ids = s.pick_match(d, amb, 1200, 2700)
    assert k == 'ambiguous' and set(ids) == {'sub:1', 'charge:2'}
    carded = [
        {'order_id': 'sub:1', 'amount': 85000, 'receipt_ts': 1000, 'receipt_last4': '0000'},
        {'order_id': 'charge:2', 'amount': 85000, 'receipt_ts': 1100, 'receipt_last4': '3264'},
    ]
    assert s.pick_match(d, carded, 1200, 2700) == ('approve', 'charge:2')


def test_match_collision_broken_by_ref():
    # The receipt of one order shows the SAME retrieval number as the SMS ->
    # definitive join even though amounts and cards collide.
    d = s.parse_bank_sms(SMS_TRAILING)  # retrieval 178324819389
    cands = [
        {'order_id': 'sub:1', 'amount': 85000, 'receipt_ts': 1000, 'receipt_last4': '7804'},
        {'order_id': 'charge:2', 'amount': 85000, 'receipt_ts': 1100, 'receipt_last4': '7804',
         'refs': ['178324819389']},
    ]
    assert s.pick_match(d, cands, 1200, 2700) == ('approve', 'charge:2')


def test_ref_never_overrides_amount_gate():
    d = s.parse_bank_sms(SMS_TRAILING)
    cands = [{'order_id': 'sub:1', 'amount': 99000, 'receipt_ts': 1000,
              'receipt_last4': None, 'refs': ['178324819389']}]
    assert s.pick_match(d, cands, 1200, 2700) == ('none', [])


def test_normalize_card_last4_rtl_guard():
    """Item 8 (2026-07-18): image-derived card normalization must survive both
    masked layouts and drop BIN-prefix misreads entirely."""
    # Print order: prefix first, real last-4 at the end.
    assert s.normalize_card_last4('6104 33** **** 2336') == '2336'
    assert s.normalize_card_last4('6219 86** **** 7804') == '7804'
    # RTL-FLIPPED rendering: the BIN sits at the visual END; real last-4 is
    # the clear group at the START (the two live Jul-2026 incidents).
    assert s.normalize_card_last4('1781 43** **** 6104') == '1781'
    assert s.normalize_card_last4('7804 86** **** 6219') == '7804'
    # A bare "last-4" equal to a known Iranian BIN is a misread -> dropped.
    for bin4 in ('6104', '6221', '6219', '6037', '5892', '5057', '5022'):
        assert s.normalize_card_last4(bin4) is None, bin4
    # Bare legit last-4 / full PAN still work.
    assert s.normalize_card_last4('2336') == '2336'
    assert s.normalize_card_last4('6219861908723264') == '3264'
    # Full PAN whose true last-4 collides with a BIN: still dropped (rare,
    # and a dropped card only costs a tie-break — never a false veto).
    assert s.normalize_card_last4('6219861908726104') is None
    # Both ends look like a BIN -> untrustworthy -> dropped.
    assert s.normalize_card_last4('6104 33** **** 6219') is None
    # Neither end recognizable -> print-order assumption (last group).
    assert s.normalize_card_last4('1234 56** **** 5678') == '5678'
    # Persian digits and junk.
    assert s.normalize_card_last4('۱۷۸۱ ۴۳** **** ۶۱۰۴') == '1781'
    assert s.normalize_card_last4(None) is None
    assert s.normalize_card_last4('12') is None
    assert s.normalize_card_last4('کارت') is None


def test_sms_source_card_exempt_from_bin_guard():
    """The SMS-side payer card comes from machine-formatted bank TEXT (logical
    order — the RTL visual flip cannot happen), so a last-4 that merely
    collides with a BIN must be KEPT there (dropping it would defer real
    payments, the exact failure the guard prevents)."""
    sms = ("مبلغ:+850,000\nمانده:1,000\n"
           "بابت :انتقال از کارت 6219861908726104 به کارت 6221061103953057 "
           "با شماره پیگیری 424242")
    d = s.parse_bank_sms(sms)
    assert d and d['source_last4'] == '6104'


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
        print('PASS', fn.__name__)
    print(f'\nAll {len(fns)} ASTROBYTE SMS-autoapprove tests passed.')
