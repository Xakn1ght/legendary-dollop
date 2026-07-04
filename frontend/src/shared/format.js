export function formatNumber(num, lang) {
  return lang === 'fa' ? new Intl.NumberFormat('fa-IR').format(num) : new Intl.NumberFormat('en-US').format(num);
}

// Purchase-family variant: explicit numbering systems + manual digit fallback.
export function formatNumberExt(num, lang) {
  try {
    const locale = lang === 'fa' ? 'fa-IR-u-nu-arabext' : 'en-US-u-nu-latn';
    return new Intl.NumberFormat(locale).format(num);
  } catch (_) {
    const raw = String(num ?? '');
    if (lang !== 'fa') return raw;
    return raw.replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
  }
}
