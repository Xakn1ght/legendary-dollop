export const translations = {
  en: {
    support: 'Support',
    helpCenter: 'Help Center',
    all: 'All',
    open: 'Open',
    closed: 'Closed',
    pending: 'Pending',
    noTickets: 'No tickets yet',
    createTicketPrompt: 'Create a ticket if you need assistance.',
    noMessages: 'No messages yet.',
    sending: 'Sending...',
    failedToLoad: 'Failed to load tickets',
    failedToSend: 'Failed to send',
    ticketCreated: 'Ticket created!',
    errorCreating: 'Error creating ticket',
    messageTooShort: 'Message must be at least 10 characters long',
    errorDeleting: 'Error deleting ticket',
    ticketDeleted: 'Ticket deleted',
    deleteConfirm: 'Delete this ticket?',
    typeMessage: 'Type a message...',
    categoryLabel: 'Category',
    selectCategory: 'Select category...',
    connection: 'Connection Issue',
    money: 'Payment & Billing',
    other: 'General / Other',
    subscriptionLabel: 'Subscription (Optional)',
    none: 'None',
    messageLabel: 'Message',
    describeIssue: 'Describe your issue...',
    createTicketBtn: 'Create Ticket',
    photoTooLarge: 'Image is too large (max 8MB)',
    photoSendFailed: 'Failed to send image',
    photoFailedRetry: 'Not sent, tap to retry',
    photoLabel: 'Photo',
    newTicket: 'New Ticket',
    noMessagesYet: 'No messages',
    loading: 'Loading...',
    loadingTickets: 'Loading tickets...',
    loadingMessages: 'Loading messages...',
    creatingTicket: 'Creating ticket...',
    deletingTicket: 'Deleting ticket...',
    redirecting: 'Redirecting...',
    search: 'Search...',
  },
  fa: {
    support: 'پشتیبانی',
    helpCenter: 'مرکز راهنما',
    all: 'همه',
    open: 'باز',
    closed: 'بسته',
    pending: 'در انتظار',
    noTickets: 'هنوز تیکتی ندارید',
    createTicketPrompt: 'در صورت نیاز یک تیکت ایجاد کنید.',
    noMessages: 'هنوز پیامی وجود ندارد.',
    sending: 'در حال ارسال...',
    failedToLoad: 'خطا در بارگذاری تیکت‌ها',
    failedToSend: 'ارسال نشد',
    ticketCreated: 'تیکت ایجاد شد!',
    errorCreating: 'خطا در ایجاد تیکت',
    messageTooShort: 'پیام باید حداقل ۱۰ کاراکتر باشد',
    errorDeleting: 'خطا در حذف تیکت',
    ticketDeleted: 'تیکت حذف شد',
    deleteConfirm: 'این تیکت حذف شود؟',
    typeMessage: 'پیامی بنویسید...',
    categoryLabel: 'دسته‌بندی',
    selectCategory: 'انتخاب دسته‌بندی...',
    connection: 'مشکل اتصال',
    money: 'پرداخت و مالی',
    other: 'سایر',
    subscriptionLabel: 'اشتراک (اختیاری)',
    none: 'هیچ‌کدام',
    messageLabel: 'پیام',
    describeIssue: 'مشکل خود را شرح دهید...',
    createTicketBtn: 'ایجاد تیکت',
    photoTooLarge: 'حجم تصویر زیاد است (حداکثر ۸ مگابایت)',
    photoSendFailed: 'ارسال تصویر ناموفق بود',
    photoFailedRetry: 'ارسال نشد، برای تلاش دوباره بزنید',
    photoLabel: 'تصویر',
    newTicket: 'تیکت جدید',
    noMessagesYet: 'بدون پیام',
    loading: 'در حال بارگذاری...',
    loadingTickets: 'در حال بارگذاری تیکت‌ها...',
    loadingMessages: 'در حال بارگذاری پیام‌ها...',
    creatingTicket: 'در حال ایجاد تیکت...',
    deletingTicket: 'در حال حذف تیکت...',
    redirecting: 'در حال انتقال...',
    search: 'جستجو...',
  },
};

export function makeT(lang) {
  return (key) => translations[lang]?.[key] || translations.en[key] || key;
}

// Backend validation errors -> localized user-facing message.
export function localizeValidationError(res, t, lang) {
  if (!res || res.error !== 'validation_error' || !Array.isArray(res.details) || res.details.length === 0) return null;
  const first = res.details[0] || {};
  const field = String(first.field || '');
  const msg = String(first.message || '');
  if (field === 'message' && /at least 10 characters/i.test(msg)) return t('messageTooShort');
  if (field === 'message' && /cannot be empty/i.test(msg)) return lang === 'fa' ? 'پیام نمی‌تواند خالی باشد' : 'Message cannot be empty';
  if (field === 'category' && /Field required/i.test(msg)) return lang === 'fa' ? 'لطفاً دسته‌بندی را انتخاب کنید' : 'Please select a category';
  return msg || null;
}

// Backend timestamps are naive UTC ISO strings — pin them to UTC so toLocale*
// renders in the device's timezone instead of being misread as local time.
export function parseTs(v) {
  if (!v) return new Date(NaN);
  if (typeof v === 'string' && !/(?:[zZ]|[+-]\d\d:?\d\d)$/.test(v)) v += 'Z';
  return new Date(v);
}
