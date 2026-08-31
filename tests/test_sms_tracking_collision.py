"""Bank tracking numbers repeat. A replay must be dropped; a second REAL
payment sharing a tracking number must still be pooled, must get its own
cross-system claim key, and must not auto-approve on amount alone.

    PYTHONPATH=src .venv/bin/python tests/test_sms_tracking_collision.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from app.services import sms_autoapprove as core  # noqa: E402

SMS = ('واریز به حساب\n'
       'مبلغ: +{amount:,} ریال\n'
       'از کارت {src}\n'
       'به کارت 622106******1234\n'
       'شماره پیگیری: {track}\n'
       'شماره بازیابی: {ret}')


def check(name, cond):
    assert cond, name


def dep(amount=5_000_000, src='603799******1111', track='445566', ret='778899'):
    d = core.parse_bank_sms(SMS.format(amount=amount, src=src, track=track, ret=ret))
    assert d, 'fixture SMS did not parse'
    return d


def test_permuted_pol_codes_join():
    """The bank SMS and the customer's receipt app print the SAME POL code
    with its segments in different orders. Exact equality misses that and the
    real payment rides the full veto grace for nothing (bakbot order #2998)."""
    sms_code = '140505030173131084179145020'
    receipt_code = '14050503145020131084179'
    check('permuted segments join', core.pol_refs_join(sms_code, receipt_code))
    check('through refs_join too', core.refs_join([sms_code], [receipt_code]))

    # Same day, different serial: NOT the same transaction.
    check('different serial does not join',
          not core.pol_refs_join(sms_code, '14050503145020999888777'))
    # Different day entirely.
    check('different date does not join',
          not core.pol_refs_join(sms_code, '140505040173131084179145020'))
    # Short card-to-card refs never enter the segment comparison.
    check('short refs still need exact equality',
          core.refs_join(['248125'], ['248125'])
          and not core.refs_join(['248125'], ['248126']))
    check('empty side never joins', not core.refs_join([], ['248125']))


def test_second_opinion_merge():
    """Two independent reads of one receipt: keep only what they agree on."""
    from app.services import sms_ai

    a = {'success': True, 'amount': 1_700_000, 'amount_unit': 'rial',
         'source_card_last4': '2336', 'ref_numbers': ['111']}
    b = {'success': True, 'amount': 700_000, 'amount_unit': 'rial',
         'source_card_last4': '2336', 'ref_numbers': ['222']}
    merged = sms_ai.merge_receipt_reads(a, b)
    check('disagreeing amount is dropped', merged['amount'] is None)
    check('agreeing card survives', merged['source_card_last4'] == '2336')
    check('refs are unioned', merged['ref_numbers'] == ['111', '222'])

    # One read simply missed the card: the other's value stands.
    c = dict(a, source_card_last4=None)
    check('a field only one read saw survives',
          sms_ai.merge_receipt_reads(a, c)['source_card_last4'] == '2336')
    check('a single read is returned untouched',
          sms_ai.merge_receipt_reads(a, None) == a)


def main():
    base = dep()
    assert base['dedup_id'] == '445566', base['dedup_id']

    # exact replay -> duplicate
    assert core.classify_deposit_identity([base], dep()) == 'duplicate'
    assert core.deposit_fingerprint(base) == core.deposit_fingerprint(dep())

    # each strong field on its own proves a distinct transaction
    for label, other in (
        ('amount', dep(amount=7_000_000)),
        ('retrieval', dep(ret='000111')),
        ('source card', dep(src='610433******2336')),
    ):
        assert core.classify_deposit_identity([base], other) == 'collision', label
        assert core.deposit_fingerprint(base) != core.deposit_fingerprint(other), label
        assert core.deposit_fingerprint(other).startswith('sms2:'), label

    # fails closed: a field only one side carries never proves a difference
    sparse = dict(base, retrieval=None, source_last4=None)
    assert core.classify_deposit_identity([sparse], base) == 'duplicate'
    assert not core.deposits_materially_distinct(sparse, base)

    # re-forwarding an accepted collision stays idempotent
    accepted = dep(amount=7_000_000)
    accepted['claim_id'] = core.deposit_fingerprint(accepted)
    assert core.classify_deposit_identity([base, accepted], dep(amount=7_000_000)) == 'duplicate'

    # a different tracking number is simply new
    assert core.classify_deposit_identity([base], dep(track='999000')) == 'new'

    print('PASS  tracking-collision identity')

    test_permuted_pol_codes_join()
    print('PASS  permuted POL reference join')

    test_second_opinion_merge()
    print('PASS  second-opinion receipt merge')


if __name__ == '__main__':
    main()
