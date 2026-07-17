import React from 'react';

// Smart precision: tiny (sub-1GB test plans) keep a decimal so the number
// never rounds to "0"; ≥10GB drops decimals for a calmer read.
const gbNum = (v) => String(Number(v.toFixed(v >= 10 ? 0 : 1)));

function formatDaysLeft(sub, fmt, t) {
  const expireTs = sub.expire;
  if (!expireTs) return '';
  const now = Math.floor(Date.now() / 1000);
  const daysLeft = Math.ceil((expireTs - now) / (60 * 60 * 24));
  if (daysLeft < 0) return t('expired');
  return `${fmt(daysLeft)} ${t('daysLeft')}`;
}

// The glance read of a card: how much is LEFT, as a health-colored meter
// (PRODUCT.md: "how much traffic/days do I have left" in under a second).
function usageInfo(sub) {
  const used = Math.max(sub.used_traffic || 0, 0) / (1024 * 1024 * 1024);
  const limit = Math.max(sub.data_limit || 0, 0) / (1024 * 1024 * 1024);
  const remaining = Math.max(limit - used, 0);
  const pct = limit > 0 ? Math.max(0, Math.min(100, (remaining / limit) * 100)) : 100;
  const health = pct > 40 ? 'ok' : pct > 15 ? 'warn' : 'bad';
  return { used, limit, remaining, pct, health };
}

export function SubscriptionSection({ t, fmt, subscriptions, subsLoaded, selectedSubId, searchQuery, onSearch, onSelect, onContinue }) {
  const q = searchQuery.trim().toLowerCase();
  const list = q
    ? subscriptions.filter((s) => {
      const name = s.name || s.username || s.marzban_username || '';
      return String(name).toLowerCase().includes(q) || String(s.id).includes(q);
    })
    : subscriptions;
  const noSubs = subsLoaded && subscriptions.length === 0;

  return (
    <div className="section active" id="section-sub">
      <div className="card">
        <div className="card-title">
          <div className="icon">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" /></svg>
          </div>
          <span>{t('selectSubscription')}</span>
        </div>
        <div className="card-subtitle">{t('selectSubHint')}</div>

        <div id="subsContainer">
          <input
            className="sub-search"
            id="subSearch"
            type="search"
            autoComplete="off"
            spellCheck="false"
            maxLength={64}
            placeholder={t('searchSubs')}
            value={searchQuery}
            onChange={(e) => onSearch(e.target.value)}
          />
          {noSubs && (
            <div className="no-subs" id="noSubsMsg">
              <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" /></svg>
              <h3>{t('noSubscriptions')}</h3>
              <p>{t('noSubsHint')}</p>
            </div>
          )}
          {!noSubs && (
            <div className="subs-scroll" id="subsScroll">
              <div className="subs-grid" id="subsGrid">
                {list.length === 0 && <div className="subs-empty">{t('noSearchResults')}</div>}
                {list.map((sub) => {
                  const name = sub.name || sub.username || sub.marzban_username || `Subscription #${sub.id}`;
                  const daysLeft = formatDaysLeft(sub, fmt, t);
                  const selected = String(sub.id) === String(selectedSubId);
                  // Unlimited subs can't be charged — the approve path would
                  // set a finite limit and downgrade them (server rejects too).
                  const unlimited = !sub.data_limit;
                  const u = usageInfo(sub);
                  return (
                    <div
                      key={sub.id}
                      className={`sub-card${selected ? ' selected' : ''}${unlimited ? ' unchargeable' : ''}`}
                      data-sub-id={sub.id}
                      role="button"
                      tabIndex={unlimited ? -1 : 0}
                      aria-disabled={unlimited || undefined}
                      onClick={unlimited ? undefined : () => onSelect(sub.id)}
                      onKeyDown={unlimited ? undefined : (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(sub.id); } }}
                    >
                      <div className="sub-card-top">
                        <div className="sub-name">{name}</div>
                        <div className="sub-check" aria-hidden="true">
                          <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" /></svg>
                        </div>
                      </div>
                      {unlimited ? (
                        <div className="sub-unlimited-note">{t('unlimitedNoCharge')}</div>
                      ) : (
                        <>
                          {/* Lead with what the user cares about: what's LEFT. */}
                          <div className={`sub-remaining h-${u.health}`}>
                            <b>{fmt(gbNum(u.remaining))}</b> {t('GB')} {t('remainingWord')}
                          </div>
                          <div className={`sub-usage-track h-${u.health}`} aria-hidden="true">
                            <span className="sub-usage-fill" style={{ width: `${Math.max(u.pct, 3)}%` }} />
                          </div>
                          <div className="sub-foot">
                            <span className="sub-foot-usage">
                              {fmt(gbNum(u.used))} / {fmt(gbNum(u.limit))} {t('GB')}
                            </span>
                            {daysLeft && <span className="sub-foot-days">{daysLeft}</span>}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bottom-actions">
        <button className="btn btn-primary" id="btnSelectSub" disabled={!selectedSubId} onClick={onContinue}>
          <span>{t('continue')}</span>
        </button>
      </div>
    </div>
  );
}
