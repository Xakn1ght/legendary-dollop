// Receipt image selection state shared by purchase/charge/vip flows:
// validate type -> canvas-compress to JPEG -> object-URL preview (base64 on
// Android) -> lazy base64 for the submit payload.

import { useCallback, useRef, useState } from 'react';

import { hapticSelection } from './telegram.js';
import { showToast } from './ui.js';

export function compressImage(file, maxWidth = 1920, maxHeight = 1920, quality = 0.85) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        try {
          let width = img.width, height = img.height;
          if (width > maxWidth || height > maxHeight) {
            const ratio = Math.min(maxWidth / width, maxHeight / height);
            width = Math.round(width * ratio);
            height = Math.round(height * ratio);
          }
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#FFFFFF';
          ctx.fillRect(0, 0, width, height);
          ctx.drawImage(img, 0, 0, width, height);
          canvas.toBlob((blob) => {
            if (blob) resolve(blob);
            else canvas.toBlob((blob2) => { resolve(blob2 || file); }, 'image/jpeg', 0.7);
          }, 'image/jpeg', quality);
        } catch (canvasErr) {
          console.error('Canvas error:', canvasErr);
          resolve(file);
        }
      };
      img.onerror = () => {
        console.error('Image failed to load, using original');
        resolve(file);
      };
      img.src = e.target.result;
    };
    reader.onerror = () => {
      console.error('FileReader error');
      resolve(file);
    };
    reader.readAsDataURL(file);
  });
}

export function readAsDataURL(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(new Error('read_failed'));
    r.readAsDataURL(blob);
  });
}

// `busy(fn)` wraps async work in the caller's loading overlay.
// `t(key)` resolves the caller's translations (fileTooLarge, selectImage, errorOccurred).
export function useReceipt({ busy, getT }) {
  const [receiptFile, setReceiptFile] = useState(null);
  const [previewSrc, setPreviewSrc] = useState('');
  const base64Ref = useRef(null);
  const objectUrlRef = useRef(null);

  const handleSelect = useCallback(async (event) => {
    const t = getT();
    const file = event.target.files[0];
    if (!file) return;
    // Any image is fine: canvas compression re-encodes to JPEG below, and the
    // server re-encodes again (image_security). Only reject clear non-images.
    const looksImage = (file.type || '').startsWith('image/') || /\.(jpg|jpeg|png|webp|heic|heif)$/i.test(file.name);
    if (!looksImage) {
      showToast('فقط فایل تصویر مجاز است');
      try { event.target.value = ''; } catch (_) { /* ignore */ }
      return;
    }
    let processedFile = file;
    await busy(async () => {
      try { processedFile = await compressImage(file); } catch (e) {
        console.error('Compression failed:', e);
        processedFile = file;
      }
    });
    if (processedFile.size > 10 * 1024 * 1024) {
      showToast(t('fileTooLarge'));
      try { event.target.value = ''; } catch (_) { /* ignore */ }
      return;
    }
    setReceiptFile(processedFile);
    base64Ref.current = null;
    try {
      if (objectUrlRef.current) { try { URL.revokeObjectURL(objectUrlRef.current); } catch (_) { /* ignore */ } }
      objectUrlRef.current = URL.createObjectURL(processedFile);
      setPreviewSrc(objectUrlRef.current);
    } catch (e) { console.error('Preview setup error:', e); }
    try {
      const dataUrl = await readAsDataURL(processedFile);
      base64Ref.current = dataUrl;
      // Some Android WebViews render blob: URLs unreliably; prefer the data URL there.
      const isAndroid = /android/i.test(navigator.userAgent);
      if (isAndroid || !objectUrlRef.current) setPreviewSrc(dataUrl);
      hapticSelection();
    } catch (_) {
      base64Ref.current = null;
    }
  }, [busy, getT]);

  // Returns the base64 payload or null (after showing the right toast).
  const getBase64ForSubmit = useCallback(async () => {
    const t = getT();
    if (!base64Ref.current) {
      if (!receiptFile) { showToast(t('selectImage')); return null; }
      try { base64Ref.current = await readAsDataURL(receiptFile); } catch (_e) {
        showToast(t('errorOccurred'));
        return null;
      }
    }
    if (!base64Ref.current || base64Ref.current.length < 100) { showToast(t('selectImage')); return null; }
    return base64Ref.current;
  }, [receiptFile, getT]);

  const cleanup = useCallback(() => {
    if (objectUrlRef.current) { try { URL.revokeObjectURL(objectUrlRef.current); } catch (_) { /* ignore */ } }
  }, []);

  // Wrong photo picked → wipe selection so the user can retake/reselect.
  const clear = useCallback(() => {
    if (objectUrlRef.current) { try { URL.revokeObjectURL(objectUrlRef.current); } catch (_) { /* ignore */ } }
    objectUrlRef.current = null;
    base64Ref.current = null;
    setReceiptFile(null);
    setPreviewSrc('');
  }, []);

  return { receiptFile, previewSrc, handleSelect, getBase64ForSubmit, cleanup, clear };
}
