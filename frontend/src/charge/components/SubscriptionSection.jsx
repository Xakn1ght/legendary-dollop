import React from 'react';

function formatDataUsage(sub, fmt, t) {
  const usedGB = (sub.used_traffic || 0) / (1024 * 1024 * 1024);
  const limitGB = (sub.data_limit || 0) / (1024 * 1024 * 1024);
  return `${fmt(usedGB.toFixed(1))}/${fmt(limitGB.toFixed(0))} ${t('GB')}`;
}

function formatDaysLeft(sub, fmt, t) {
  const expireTs = sub.expire;
  if (!expireTs) return '';
  const now = Math.floor(Date.now() / 1000);
  const daysLeft = Math.ceil((expireTs - now) / (60 * 60 * 24));
  if (daysLeft < 0) return t('expired');
  return `${fmt(daysLeft)} ${t('daysLeft')}`;
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
                  const initial = (String(name).trim()[0] || 'S').toUpperCase();
                  const selected = String(sub.id) === String(selectedSubId);
                  return (
                    <div
                      key={sub.id}
                      className={`sub-card${selected ? ' selected' : ''}`}
                      data-sub-id={sub.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelect(sub.id)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(sub.id); } }}
                    >
                      <div className="sub-avatar" aria-hidden="true">{initial}</div>
                      <div className="sub-main">
                        <div className="sub-title-row">
                          <div className="sub-name">{name}</div>
                        </div>
                        <div className="sub-meta">
                          <span>
                            <svg viewBox="0 0 24 24"><path d="M2 20h20v-4H2v4zm2-3h2v2H4v-2zM2 4v4h20V4H2zm4 3H4V5h2v2zm-4 7h20v-4H2v4zm2-3h2v2H4v-2z" /></svg>
                            {formatDataUsage(sub, fmt, t)}
                          </span>
                          {daysLeft && (
                            <span>
                              <svg viewBox="0 0 24 24"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z" /></svg>
                              {daysLeft}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="sub-check" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" /></svg>
                      </div>
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
