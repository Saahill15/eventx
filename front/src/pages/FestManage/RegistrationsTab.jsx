import { useState, useEffect } from 'react'
import { StatusPill, ErrorBanner, Select } from '../../components/ui'
import { getEventRegistrations, decideRegistration, downloadRegistrations } from '../../services/api'
import { errorMessage } from '../../lib/errors'

export default function RegistrationsTab({ events, reload }) {
  const withRegistration = events.filter((e) => e.requires_registration)
  const [eventId, setEventId] = useState(withRegistration[0]?.id ?? null)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = (id) => {
    if (!id) return
    setLoading(true)
    getEventRegistrations(id)
      .then((r) => setRows(r.data))
      .catch((err) => setError(errorMessage(err, 'Could not load registrations.')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { setError(''); load(eventId) }, [eventId])

  const decide = async (id, approve) => {
    setError('')
    try {
      await decideRegistration(id, approve)
      load(eventId)
      reload()
    } catch (err) {
      setError(errorMessage(err, 'Could not update that registration.'))
      load(eventId)
    }
  }

  const exportCsv = async () => {
    setError('')
    try {
      const res = await downloadRegistrations(eventId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `registrations-event-${eventId}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError('Could not download the file.')
    }
  }

  if (withRegistration.length === 0) {
    return (
      <div className="bg-white rounded-2xl p-10 text-center text-gray-500">
        None of your events take registrations yet. Turn on "Students must register" when you add or edit an event.
      </div>
    )
  }

  const count = (status) => rows.filter((r) => r.approval_status === status).length

  return (
    <div>
      <div className="flex flex-wrap items-end gap-4 mb-5">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Event</label>
          <Select value={eventId ?? ''} onChange={(e) => setEventId(parseInt(e.target.value, 10))}>
            {withRegistration.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </Select>
        </div>
        <button
          onClick={exportCsv}
          disabled={rows.length === 0}
          className="text-sm font-semibold border border-gray-200 bg-white px-5 py-3 rounded-xl hover:bg-gray-50 disabled:opacity-50"
        >
          Download CSV
        </button>
      </div>

      <ErrorBanner>{error}</ErrorBanner>

      <p className="text-sm text-gray-500 mb-3">
        {rows.length} total · {count('approved')} confirmed · {count('pending')} waiting · {count('rejected')} rejected
      </p>

      {loading ? (
        <div className="bg-white rounded-2xl h-24 animate-pulse" />
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-2xl p-10 text-center text-gray-500">Nobody has registered yet.</div>
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.id} className="bg-white rounded-2xl shadow-sm p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-gray-900 truncate">{r.user_name}</p>
                <p className="text-xs text-gray-400 truncate">{r.user_email}</p>
                <p className="text-xs text-gray-400 mt-1">
                  Registered {new Date(r.created_at).toLocaleDateString('en-IN')} · Payment: {r.payment_status}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <StatusPill status={r.approval_status} />
                {r.approval_status === 'pending' && (
                  <>
                    <button onClick={() => decide(r.id, true)} className="text-xs font-semibold bg-green-500 text-white px-3 py-1.5 rounded-full hover:bg-green-600">Approve</button>
                    <button onClick={() => decide(r.id, false)} className="text-xs font-semibold bg-red-500 text-white px-3 py-1.5 rounded-full hover:bg-red-600">Reject</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
