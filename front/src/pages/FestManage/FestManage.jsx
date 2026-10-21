import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import Navbar from '../../components/Navbar'
import Footer from '../../components/Footer'
import { ErrorBanner, StatusPill, PrimaryButton, Field, Input } from '../../components/ui'
import { getFest, getMyFests, getManagedFestEvents, setFestStatus, updateFest } from '../../services/api'
import { errorMessage } from '../../lib/errors'
import EventsTab from './EventsTab'
import RegistrationsTab from './RegistrationsTab'
import TeamTab from './TeamTab'

function SettingsTab({ fest, onSaved }) {
  const [form, setForm] = useState({ name: fest.name, tagline: fest.tagline ?? '', banner_url: fest.banner_url ?? '', logo_url: fest.logo_url ?? '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const set = (k, v) => { setSaved(false); setForm((f) => ({ ...f, [k]: v })) }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await updateFest(fest.slug, {
        name: form.name,
        tagline: form.tagline || null,
        banner_url: form.banner_url || null,
        logo_url: form.logo_url || null,
      })
      setSaved(true)
      onSaved()
    } catch (err) {
      setError(errorMessage(err, 'Could not save.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="bg-white rounded-3xl shadow-sm p-6 space-y-4 max-w-xl">
      <ErrorBanner>{error}</ErrorBanner>
      <Field label="Fest name"><Input required value={form.name} onChange={(e) => set('name', e.target.value)} /></Field>
      <Field label="Tagline"><Input value={form.tagline} onChange={(e) => set('tagline', e.target.value)} /></Field>
      <Field label="Banner image URL"><Input type="url" value={form.banner_url} onChange={(e) => set('banner_url', e.target.value)} placeholder="https://…" /></Field>
      <Field label="Logo URL"><Input type="url" value={form.logo_url} onChange={(e) => set('logo_url', e.target.value)} placeholder="https://…" /></Field>
      <div className="flex items-center gap-3">
        <PrimaryButton type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save'}</PrimaryButton>
        {saved && <span className="text-sm text-green-600">Saved</span>}
      </div>
    </form>
  )
}

const TABS = [
  { id: 'events', label: 'Events' },
  { id: 'registrations', label: 'Registrations' },
  { id: 'team', label: 'Team' },
  { id: 'settings', label: 'Fest page' },
]

export default function FestManage() {
  const { slug } = useParams()
  const [fest, setFest] = useState(null)
  const [myRole, setMyRole] = useState(null)
  const [events, setEvents] = useState([])
  const [tab, setTab] = useState('events')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusBusy, setStatusBusy] = useState(false)

  const loadEvents = useCallback(() => {
    getManagedFestEvents(slug).then((r) => setEvents(r.data)).catch((err) => setError(errorMessage(err, 'Could not load events.')))
  }, [slug])

  const loadFest = useCallback(() => getFest(slug).then((r) => setFest(r.data)), [slug])

  useEffect(() => {
    setLoading(true)
    Promise.all([getMyFests(), loadFest()])
      .then(([mine]) => {
        const membership = mine.data.find((f) => f.slug === slug)
        setMyRole(membership ? membership.my_role : null)
      })
      .catch(() => setError('Fest not found, or you do not have access to it.'))
      .finally(() => setLoading(false))
  }, [slug, loadFest])

  const isStaff = myRole === 'owner' || myRole === 'core' || myRole === 'admin'
  useEffect(() => { if (isStaff) loadEvents() }, [isStaff, loadEvents])

  const toggleLive = async () => {
    setStatusBusy(true); setError('')
    try {
      await setFestStatus(slug, fest.status === 'live' ? 'draft' : 'live')
      await loadFest()
    } catch (err) {
      setError(errorMessage(err, 'Could not change the fest status.'))
    } finally {
      setStatusBusy(false)
    }
  }

  const shell = (children) => (
    <div className="min-h-screen bg-[#fafaf9]">
      <Navbar />
      <div className="max-w-5xl mx-auto px-6 pt-28 pb-20">{children}</div>
      <Footer />
    </div>
  )

  if (loading) return shell(<div className="bg-white rounded-2xl h-40 animate-pulse" />)

  if (!fest || !myRole) {
    return shell(
      <div className="text-center py-20">
        <p className="text-gray-500 mb-4">{error || 'You do not have access to manage this fest.'}</p>
        <Link to="/organizer" className="text-orange-500 font-semibold hover:underline">← Back to your fests</Link>
      </div>,
    )
  }

  if (!isStaff) {
    return shell(
      <div className="text-center py-20">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{fest.name}</h1>
        <p className="text-gray-500 mb-4">You are a volunteer on this fest. Management tools are for the director and core team.</p>
        <Link to={`/fest/${fest.slug}`} className="text-orange-500 font-semibold hover:underline">View the fest page →</Link>
      </div>,
    )
  }

  const pendingTotal = events.reduce((n, e) => n + e.pending_count, 0)

  return shell(
    <>
      <Link to="/organizer" className="text-sm text-gray-400 hover:text-gray-600">← Your fests</Link>
      <div className="flex items-start justify-between gap-4 flex-wrap mt-3 mb-8">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-3xl font-bold text-gray-900 tracking-tight">{fest.name}</h1>
            <StatusPill status={fest.status} />
          </div>
          <Link to={`/fest/${fest.slug}`} className="text-sm text-violet-600 hover:text-violet-800">
            View public page →
          </Link>
        </div>
        <button
          onClick={toggleLive}
          disabled={statusBusy}
          className={`text-sm font-semibold px-5 py-2.5 rounded-full border transition-colors disabled:opacity-60 ${
            fest.status === 'live'
              ? 'border-gray-200 text-gray-700 hover:bg-gray-50'
              : 'bg-green-500 border-green-500 text-white hover:bg-green-600'
          }`}
        >
          {statusBusy ? 'Updating…' : fest.status === 'live' ? 'Take offline (draft)' : 'Make fest live'}
        </button>
      </div>

      {fest.status !== 'live' && (
        <div className="mb-6 bg-amber-50 border border-amber-100 text-amber-800 text-sm px-4 py-3 rounded-xl">
          This fest is a draft. Only your team can see it, and students cannot get passes yet. Make it live when you are ready.
        </div>
      )}
      <ErrorBanner>{error}</ErrorBanner>

      <div className="flex gap-1 border-b border-gray-200 mb-8 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-3 text-sm font-semibold whitespace-nowrap border-b-2 -mb-px transition-colors ${
              tab === t.id ? 'border-gray-900 text-gray-900' : 'border-transparent text-gray-400 hover:text-gray-700'
            }`}
          >
            {t.label}
            {t.id === 'registrations' && pendingTotal > 0 && (
              <span className="ml-2 text-[11px] bg-orange-500 text-white rounded-full px-2 py-0.5">{pendingTotal}</span>
            )}
          </button>
        ))}
      </div>

      {tab === 'events' && <EventsTab fest={fest} events={events} reload={loadEvents} />}
      {tab === 'registrations' && <RegistrationsTab events={events} reload={loadEvents} />}
      {tab === 'team' && <TeamTab slug={slug} myRole={myRole} />}
      {tab === 'settings' && <SettingsTab fest={fest} onSaved={loadFest} />}
    </>,
  )
}
