import logo from "../assets/logo.svg?raw";

// Vector trace of the Vora Addis logo. It is inlined so it takes the colour
// of its surroundings (gold on the dark sidebar, a faint tint as a watermark).
export default function BrandMark({ className = "" }: { className?: string }) {
  return <span className={`brand-logo ${className}`} role="img" aria-label="Vora Addis Hotel" dangerouslySetInnerHTML={{ __html: logo }} />;
}

/** The logo, very faint and centred behind the page content. */
export function Watermark() {
  return (
    <div className="watermark" aria-hidden="true">
      <BrandMark />
    </div>
  );
}
