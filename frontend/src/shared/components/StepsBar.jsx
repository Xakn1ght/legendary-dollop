import React from 'react';

export function StepsBar({ step }) {
  return (
    <div className="steps">
      {[1, 2, 3, 4].map((n) => (
        <div key={n} className={`step${n === step ? ' active' : ''}${n < step ? ' done' : ''}`} data-step={n} />
      ))}
    </div>
  );
}
