import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Field, Input, Select, ErrorBanner, PrimaryButton } from '../../components/ui'
import { createEvent, updateEvent } from '../../services/api'
import { errorMessage } from '../../lib/errors'

const CATEGORIES = ['Cultural', 'Technical', 'Sports', 'Music', 'Business', 'Gaming', 'Fashion', 'Literary', 'Technology', 'Finance', 'Design', 'Education']

const emptyForm = {
  title: '', description: '', date: '', time: '', location: '', category: '', image_url: '',
  paid: false, price: '', requires_registration: false, registration_limit: '', approval_mode: 'auto',
}

const toForm = (e) => ({
  title: e.title ?? '',
  description: e.description ?? '',
  date: e.date ? e.date.slice(0, 10) : '',
  time: e.time ?? '',
  location: e.location ?? '',
  category: e.category ?? '',
  image_url: e.image_url ?? '',
  paid: !e.is_free,
  price: e.is_free ? '' : String(e.price ?? ''),
  requires_registration: !!e.requires_registration,
  registration_limit: e.registration_limit == null ? '' : String(e.registration_limit),
  approval_mode: e.approval_mode ?? 'auto',
})

// Backend field values for a form state
const toPayload = (f) => ({
  title: f.title.trim(),
  description: f.description || null,
  date: `${f.date}T00:00:00`,
  time: f.time || null,
  location: f.location || null,
  category: f.category || null,
  image_url: f.image_url || null,
  is_free: !f.paid,
  price: f.paid ? parseFloat(f.price) : 0,
  requires_registration: f.requires_registration,
  is_paid: f.requires_registration && f.paid,
  registration_limit: f.requires_registration && f.registration_limit ? parseInt(f.registration_limit, 10) : null,
  approval_mode: f.approval_mode,
})

function EventForm({ fest, event, onSaved, onCancel }) {
  const editing = !!event
  const [form, setForm] = useState(editing ? toForm(event) : emptyForm)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = toPayload(form)
      if (editing) {
        // Only send what changed: registration fields are locked once people have registered, even if re-sent unchanged
        const before = toPayload(toForm(event))
        const changed = Object.fromEntries(Object.entries(payload).filter(([k, v]) => v !== before[k]))
        if (Object.keys(changed).length > 0) await updateEvent(event.id, changed)
      } else {
        await createEvent({ ...payload, event_type: 'fest', fest_id: fest.id, college_id: fest.college_id })
      }
      onSaved()
    } catch (err) {
      setError(errorMessage(err, 'Could not save the event.'))
    } finally {
      setBusy(false)
    }
  }

  const locked = editing && event.registration_count > 0

  return (
    <form onSubmit={submit} className="bg-white rounded-3xl shadow-sm p-6 space-y-4">
      <h2 className="font-bold text-gray-900">{editing ? 'Edit event' : 'New event'}</h2>
      <ErrorBanner>{error}</ErrorBanner>
      <Field label="Title *"><Input required value={form.title} onChange={(e) => set('title', e.target.value)} placeholder="e.g. Battle of Bands" /></Field>
      <Field label="Description">
        <textarea
          value={form.description}
          onChange={(e) => set('description', e.target.value)}
          rows={3}
          className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-400/50 text-sm resize-none"
        />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Date *"><Input required type="date" value={form.date} onChange={(e) => set('date', e.target.value)} /></Field>
        <Field label="Time"><Input type="time" value={form.time} onChange={(e) => set('time', e.target.value)} /></Field>
      </div>
      <Field label="Venue"><Input value={form.location} onChange={(e) => set('location', e.target.value)} placeholder="e.g. Main Auditorium" /></Field>
      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="Category">
          <Select value={form.category} onChange={(e) => set('category', e.target.value)}>
            <option value="">Select</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </Field>
        <Field label="Cover image URL"><Input type="url" value={form.image_url} onChange={(e) => set('image_url', e.target.value)} placeholder="https://…" /></Field>
      </div>

      <div className="rounded-2xl bg-gray-50 p-4 space-y-4">
        <label className="flex items-center gap-3 text-sm font-medium text-gray-800">
          <input
            type="checkbox"
            checked={form.requires_registration}
            disabled={locked}
            onChange={(e) => set('requires_registration', e.target.checked)}
          />
          Students must register for this event
        </label>
        {locked && <p className="text-xs text-gray-400">Registration settings are locked because people have already registered.</p>}
        {form.requires_registration && (
          <>
            <div className="grid sm:grid-cols-2 gap-4">
              <Field label="Seat limit" hint="Leave empty for no limit">
                <Input type="number" min={1} value={form.registration_limit} onChange={(e) => set('registration_limit', e.target.value)} />
              </Field>
              <Field label="Approval">
                <Select value={form.approval_mode} onChange={(e) => set('approval_mode', e.target.value)}>
                  <option value="auto">Automatic: confirmed instantly</option>
                  <option value="manual">Manual: committee approves each one</option>
                </Select>
              </Field>
            </div>
          </>
        )}
        <label className="flex items-center gap-3 text-sm font-medium text-gray-800">
          <input type="checkbox" checked={form.paid} disabled={locked} onChange={(e) => set('paid', e.target.checked)} />
          Paid event
        </label>
        {form.paid && (
          <>
            <Field label="Price (₹)"><Input type="number" min={1} required value={form.price} onChange={(e) => set('price', e.target.value)} /></Field>
            <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
              Online payment is not live yet. Students who register for a paid event are marked as paid without being charged, so collect the money yourselves for now.
            </p>
          </>
        )}
      </div>

      <div className="flex gap-3">
        <PrimaryButton type="submit" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Publish event'}</PrimaryButton>
        <button type="button" onClick={onCancel} className="text-sm font-semibold text-gray-500 px-4">Cancel</button>
      </div>
      {!editing && <p className="text-xs text-gray-400">Events are visible on your fest page as soon as you publish them, once the fest itself is live.</p>}
    </form>
  )
}

export default function EventsTab({ fest, events, reload }) {
  const [editing, setEditing] = useState(null) // null | 'new' | event

  const saved = () => { setEditing(null); reload() }

  if (editing) {
    return <EventForm fest={fest} event={editing === 'new' ? null : editing} onSaved={saved} onCancel={() => setEditing(null)} />
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-5">
        <p className="text-sm text-gray-500">{events.length} event{events.length === 1 ? '' : 's'}</p>
        <PrimaryButton onClick={() => setEditing('new')}>+ New event</PrimaryButton>
      </div>
      {events.length === 0 ? (
        <div className="bg-white rounded-2xl p-10 text-center text-gray-500">No events yet. Add your first one.</div>
      ) : (
        <div className="space-y-3">
          {events.map((e) => (
            <div key={e.id} className="bg-white rounded-2xl p-5 shadow-sm flex items-center justify-between gap-4 flex-wrap">
              <div className="min-w-0">
                <p className="font-semibold text-gray-900">{e.title}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  🗓 {new Date(e.date).toLocaleDateString('en-IN')}{e.time ? ` · ${e.time}` : ''}
                  {e.location ? ` · 📍 ${e.location}` : ''} · {e.is_free ? 'Free' : `₹${e.price}`}
                </p>
                <p className="text-xs mt-1 text-gray-500">
                  {e.requires_registration
                    ? `${e.registration_count}${e.registration_limit ? ` / ${e.registration_limit}` : ''} registered${e.pending_count ? ` · ${e.pending_count} waiting for approval` : ''}`
                    : 'No registration needed'}
                </p>
              </div>
              <div className="flex gap-3 flex-shrink-0">
                <Link to={`/events/${e.id}`} className="text-xs font-semibold text-gray-500 hover:text-gray-900">View</Link>
                <button onClick={() => setEditing(e)} className="text-xs font-semibold text-violet-600 hover:text-violet-800">Edit</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
