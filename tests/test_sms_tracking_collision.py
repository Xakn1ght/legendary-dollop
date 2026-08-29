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


def dep(amount=5_000_000, src='603799******1111', track='445566', ret='778899'):
    d = core.parse_bank_sms(SMS.format(amount=amount, src=src, track=track, ret=ret))
    assert d, 'fixture SMS did not parse'
    return d


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


if __name__ == '__main__':
    main()
