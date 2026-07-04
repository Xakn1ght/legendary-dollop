import { createContext, useContext } from 'react';

// Shared shell state passed down to pages (home/tasks/shop/profile).
// Shape (see ShellApp): { lang, t, setLanguage, page, navigate, currentSubId,
// selectSub, cachedSubs, loadSubscriptions, overview, fetchOverview,
// fetchOverviewById, geo, prefs helpers, openSupport, openPurchasePage,
// openChargePage, openTutorial, sheets/modals openers }
export const ShellContext = createContext(null);
export const useShell = () => useContext(ShellContext);
