/**
 * Turn an axios error into a message that is always a plain string.
 * FastAPI returns `detail` as a string for HTTP errors but as a list of objects for validation (422) errors,
 * which would crash React if rendered directly.
 */
export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : null
        const msg = d.msg ?? 'Invalid value'
        return field && field !== 'body' ? `${field}: ${msg}` : msg
      })
      .join('; ')
  }
  if (err?.response?.status === 429) return 'Too many attempts. Please wait a few minutes.'
  if (err && !err.response) return 'Cannot reach the server. Check your connection and try again.'
  return fallback
}
