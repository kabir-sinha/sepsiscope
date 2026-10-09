// Shown on every page: this is a research prototype, not a medical device.
export function ResearchBanner() {
  return (
    <div
      role="alert"
      style={{
        padding: '0.5rem 1rem',
        background: '#7a1f1f',
        color: '#ffffff',
        fontWeight: 600,
        textAlign: 'center',
      }}
    >
      Research prototype — not for clinical use
    </div>
  )
}
