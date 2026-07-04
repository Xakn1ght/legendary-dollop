import React from 'react';

// Inline SVG flags for the most common server countries (legacy parity);
// anything else falls back to /api/dashboard/flags/{code}.png, then a pin icon.
export const FLAG_PIN = (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M21 10C21 17 12 23 12 23C12 23 3 17 3 10C3 7.61305 3.94821 5.32387 5.63604 3.63604C7.32387 1.94821 9.61305 1 12 1C14.3869 1 16.6761 1.94821 18.364 3.63604C20.0518 5.32387 21 7.61305 21 10Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="currentColor" />
    <circle cx="12" cy="10" r="3" stroke="#fff" strokeWidth="2" fill="none" />
  </svg>
);

const COUNTRY_FLAGS = {
  Germany: (
    <svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#FFCD05" d="M0 27a4 4 0 0 0 4 4h28a4 4 0 0 0 4-4v-4H0v4z" /><path fill="#ED1F24" d="M0 14h36v9H0z" /><path fill="#141414" d="M32 5H4a4 4 0 0 0-4 4v5h36V9a4 4 0 0 0-4-4z" /></svg>
  ),
  Netherlands: (
    <svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#EEE" d="M0 14h36v8H0z" /><path fill="#AE1F28" d="M32 5H4a4 4 0 0 0-4 4v5h36V9a4 4 0 0 0-4-4z" /><path fill="#20478B" d="M4 31h28a4 4 0 0 0 4-4v-5H0v5a4 4 0 0 0 4 4z" /></svg>
  ),
  Turkey: (
    <svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg"><path fill="#ED1F34" d="M8.258,126.624v258.753c0,19.763,16.022,35.785,35.785,35.785h423.914c19.763,0,35.785-16.022,35.785-35.785V126.624c0-19.763-16.022-35.785-35.785-35.785H44.043C24.28,90.839,8.258,106.86,8.258,126.624z" /><path fill="#FFFFFF" d="M210.305,337.677c-45.109,0-81.677-36.568-81.677-81.677s36.568-81.677,81.677-81.677c22.245,0,42.402,8.906,57.133,23.33c-19.526-31.397-54.323-52.311-94.019-52.311c-61.115,0-110.658,49.543-110.658,110.658s49.543,110.658,110.658,110.658c39.696,0,74.492-20.915,94.019-52.312C252.708,328.771,232.55,337.677,210.305,337.677z" /><polygon fill="#FFFFFF" points="277.628,256 309.847,243.659 311.627,209.204 333.32,236.033 366.638,227.079 347.826,256 366.638,284.921 333.32,275.967 311.627,302.796 309.847,268.341" /></svg>
  ),
  France: (
    <svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#ED2939" d="M0 5h12v31H0z" /><path fill="#FFF" d="M12 5h12v31H12z" /><path fill="#002395" d="M24 5h12v31H24z" /></svg>
  ),
  USA: (
    <svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#B22234" d="M0 5h36v31H0z" /><path fill="#FFF" d="M0 9h36v3H0zm0 6h36v3H0zm0 6h36v3H0zm0 6h36v3H0z" /><path fill="#3C3B6E" d="M0 5h16v17H0z" /></svg>
  ),
  'United Kingdom': (
    <svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#00247D" d="M0 5h36v31H0z" /><path stroke="#FFF" strokeWidth="6" d="M0 5l36 31M36 5L0 36" /><path stroke="#CF142B" strokeWidth="4" d="M0 5l36 31M36 5L0 36" /><path stroke="#FFF" strokeWidth="10" d="M18 5v31M0 20.5h36" /><path stroke="#CF142B" strokeWidth="6" d="M18 5v31M0 20.5h36" /></svg>
  ),
  Switzerland: (
    <svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#D52B1E" d="M0 5h36v31H0z" /><path fill="#FFF" d="M15 11h6v14h-6zm-4 4h14v6H11z" /></svg>
  ),
};

const CODE_TO_NAME = {
  DE: 'Germany', NL: 'Netherlands', TR: 'Turkey', FR: 'France',
  US: 'USA', GB: 'United Kingdom', CH: 'Switzerland', AE: 'UAE',
};

export function Flag({ countryName, countryCode }) {
  const [imgFailed, setImgFailed] = React.useState(false);
  const code = String(countryCode || '').trim().toUpperCase();
  const nameKey = CODE_TO_NAME[code] || countryName;
  const inline = COUNTRY_FLAGS[nameKey] || COUNTRY_FLAGS[countryName];
  if (inline) return inline;
  if (!imgFailed && code && /^[A-Z]{2}$/.test(code)) {
    return (
      <img
        loading="lazy"
        src={'/api/dashboard/flags/' + code.toLowerCase() + '.png'}
        alt={countryName || code}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        onError={() => setImgFailed(true)}
      />
    );
  }
  return FLAG_PIN;
}
