// Small shared form pieces for the dashboard screens.

export const inputClass =
  'w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-400/50 focus:border-orange-300 transition-all text-sm bg-white'

export function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1.5">{hint}</p>}
    </div>
  )
}

export const Input = (props) => <input {...props} className={inputClass} />

export const Select = ({ children, ...props }) => (
  <select {...props} className={inputClass}>{children}</select>
)

export function ErrorBanner({ children }) {
  if (!children) return null
  return <div className="mb-5 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">{children}</div>
}

export function PrimaryButton({ children, ...props }) {
  return (
    <button
      {...props}
      className="bg-gray-900 text-white text-sm font-semibold px-5 py-2.5 rounded-full hover:bg-gray-700 transition-all active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  )
}

export const STATUS_STYLES = {
  approved: 'bg-green-50 text-green-600 border-green-100',
  pending:  'bg-yellow-50 text-yellow-600 border-yellow-100',
  rejected: 'bg-red-50 text-red-600 border-red-100',
  live:     'bg-green-50 text-green-600 border-green-100',
  draft:    'bg-gray-100 text-gray-500 border-gray-200',
}

export function StatusPill({ status }) {
  return (
    <span className={`text-[11px] font-semibold border px-2.5 py-0.5 rounded-full capitalize ${STATUS_STYLES[status] ?? STATUS_STYLES.pending}`}>
      {status}
    </span>
  )
}
