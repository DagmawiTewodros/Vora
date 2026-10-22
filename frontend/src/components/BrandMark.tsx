import { useState } from "react";

// The hotel logo lives at public/brand/logo.svg or public/brand/logo.png.
// Until one is added, the hotel name is set in type as a wordmark.
const SOURCES = ["/brand/logo.svg", "/brand/logo.png"];

export default function BrandMark({ className = "" }: { className?: string }) {
  const [index, setIndex] = useState(0);
  if (index < SOURCES.length) {
    return <img className={`brand-logo ${className}`} src={SOURCES[index]} alt="Vora Addis Hotel" onError={() => setIndex(index + 1)} />;
  }
  return (
    <div className={`wordmark ${className}`} aria-label="Vora Addis Hotel">
      <span className="wordmark-name">VORA</span>
      <span className="wordmark-rule"><i />ADDIS<i /></span>
      <span className="wordmark-sub">HOTEL</span>
    </div>
  );
}

/** The logo, very faint and centred behind the page content. */
export function Watermark() {
  return (
    <div className="watermark" aria-hidden="true">
      <BrandMark />
    </div>
  );
}
