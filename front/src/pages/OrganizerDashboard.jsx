import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { Field, Input, Select, ErrorBanner, PrimaryButton, StatusPill } from '../components/ui'
import { getMyFests, getMyEvents, getColleges, createFest } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../lib/errors'

const ROLE_LABEL = { owner: 'Festival director', core: 'Core team', volunteer: 'Volunteer', admin: 'Admin' }

const slugify = (text) =>
  text.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60)

function CreateFestForm({ colleges, onCreated, onCancel }) {
  const [form, setForm] = useState({ name: '', slug: '', tagline: '', college_id: '' })
  const [slugEdited, setSlugEdited] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const setName = (name) =>
    setForm((f) => ({ ...f, name, slug: slugEdited ? f.slug : slugify(name) }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await createFest({
        name: form.name,
        slug: form.slug,
        tagline: form.tagline || null,
        college_id: form.college_id ? parseInt(form.college_id, 10) : null,
        status: 'draft',
      })
      onCreated(res.data)
    } catch (err) {
      setError(errorMessage(err, 'Could not create the fest.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="bg-white rounded-3xl shadow-sm p-6 mb-8 space-y-4">
      <h2 className="font-bold text-gray-900">New fest</h2>
      <ErrorBanner>{error}</ErrorBanner>
      <Field label="Fest name *">
        <Input required value={form.name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Mood Indigo 2026" />
      </Field>
      <Field label="Web address *" hint={`Your fest page will be at /fest/${form.slug || 'your-fest'}`}>
        <Input
          required
          value={form.slug}
          onChange={(e) => { setSlugEdited(true); setForm((f) => ({ ...f, slug: e.target.value.toLowerCase() })) }}
          placeholder="mood-indigo-2026"
          pattern="[a-z0-9]+(-[a-z0-9]+)*"
          title="Lowercase letters, numbers and single hyphens"
        />
      </Field>
      <Field label="Tagline">
        <Input value={form.tagline} onChange={(e) => setForm((f) => ({ ...f, tagline: e.target.value }))} placeholder="One line about your fest" />
      </Field>
      <Field label="College">
        <Select value={form.college_id} onChange={(e) => setForm((f) => ({ ...f, college_id: e.target.value }))}>
          <option value="">Not listed / none</option>
          {colleges.map((c) => <option key={c.id} value={c.id}>{c.emoji} {c.name}</option>)}
        </Select>
      </Field>
      <p className="text-xs text-gray-400">The fest starts as a draft that only your team can see. Make it live when you are ready.</p>
      <div className="flex gap-3">
        <PrimaryButton type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create fest'}</PrimaryButton>
        <button type="button" onClick={onCancel} className="text-sm font-semibold text-gray-500 px-4">Cancel</button>
      </div>
    </form>
  )
}

export default function OrganizerDashboard() {
  const { isOrganizer } = useAuth()
  const navigate = useNavigate()
  const [fests, setFests] = useState([])
  const [cityEvents, setCityEvents] = useState([])
  const [colleges, setColleges] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    const loads = [getMyFests().then((r) => setFests(r.data))]
    if (isOrganizer) {
      loads.push(getMyEvents().then((r) => setCityEvents(r.data)).catch(() => {}))
      loads.push(getColleges().then((r) => setColleges(r.data)).catch(() => {}))
    }
    Promise.all(loads)
      .catch((err) => setError(errorMessage(err, 'Could not load your fests.')))
      .finally(() => setLoading(false))
  }, [isOrganizer])

  return (
    <div className="min-h-screen bg-[#fafaf9]">
      <Navbar />
      <div className="max-w-5xl mx-auto px-6 pt-28 pb-20">
        <div className="flex items-start justify-between mb-10 gap-4 flex-wrap">
          <div>
            <span className="text-xs font-semibold text-violet-500 uppercase tracking-widest">Committee</span>
            <h1 className="text-4xl font-bold text-gray-900 mt-2 tracking-tight">Your fests</h1>
            <p className="text-gray-500 mt-2">Run events, registrations and your team in one place.</p>
          </div>
          {isOrganizer && !creating && (
            <PrimaryButton onClick={() => setCreating(true)}>+ New fest</PrimaryButton>
          )}
        </div>

        <ErrorBanner>{error}</ErrorBanner>

        {creating && (
          <CreateFestForm
            colleges={colleges}
            onCancel={() => setCreating(false)}
            onCreated={(fest) => navigate(`/organizer/fest/${fest.slug}`)}
          />
        )}

        {loading ? (
          <div className="space-y-4">
            {[...Array(2)].map((_, i) => <div key={i} className="bg-white rounded-2xl h-24 animate-pulse" />)}
          </div>
        ) : fests.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-3xl">
            <span className="text-5xl block mb-4">🎪</span>
            {isOrganizer ? (
              <p className="text-gray-500">You are not part of a fest yet. Create one to get started.</p>
            ) : (
              <>
                <p className="text-gray-500 mb-5 max-w-md mx-auto">
                  You are not on any fest committee. If you are running a fest, request organiser access and we will set you up,
                  or ask your fest director to add your email.
                </p>
                <Link to="/profile" className="bg-gray-900 text-white font-semibold px-6 py-3 rounded-full hover:bg-gray-700 transition-colors inline-block">
                  Request organiser access
                </Link>
              </>
            )}
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-5">
            {fests.map((fest) => (
              <motion.div key={fest.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <Link
                  to={`/organizer/fest/${fest.slug}`}
                  className="block bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <StatusPill status={fest.status} />
                    <span className="text-[11px] font-medium text-gray-400">{ROLE_LABEL[fest.my_role] ?? fest.my_role}</span>
                  </div>
                  <h2 className="font-bold text-gray-900 text-lg">{fest.name}</h2>
                  {fest.tagline && <p className="text-sm text-gray-500 mt-1 line-clamp-1">{fest.tagline}</p>}
                  <p className="text-xs text-gray-400 mt-3">{fest.event_count} live event{fest.event_count === 1 ? '' : 's'}</p>
                </Link>
              </motion.div>
            ))}
          </div>
        )}

        {isOrganizer && (
          <div className="mt-16">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-gray-800">Standalone city events</h2>
              <Link to="/events/create" className="text-xs font-semibold text-violet-600 hover:text-violet-800">+ New city event</Link>
            </div>
            {cityEvents.length === 0 ? (
              <p className="text-sm text-gray-400">None yet. City events are reviewed by an admin before they go live.</p>
            ) : (
              <div className="space-y-3">
                {cityEvents.map((event) => (
                  <div key={event.id} className="bg-white rounded-2xl p-4 flex items-center justify-between gap-4 shadow-sm">
                    <div className="min-w-0">
                      <p className="font-semibold text-gray-900 truncate">{event.title}</p>
                      <p className="text-xs text-gray-400">{new Date(event.date).toLocaleDateString('en-IN')}</p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <StatusPill status={event.status} />
                      <Link to={`/events/${event.id}`} className="text-xs font-semibold text-gray-500 hover:text-gray-900">View →</Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <Footer />
    </div>
  )
}
