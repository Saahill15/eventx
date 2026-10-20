import { useState, useEffect } from 'react'
import { errorMessage } from '../lib/errors'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import {
  getOrganizerRequests, approveOrganizer, rejectOrganizer,
  getPendingEvents, approveEvent, rejectEvent,
  getColleges, createCollege, deleteCollege,
} from '../services/api'

function Section({ title, children }) {
  return (
    <div className="mb-12">
      <h2 className="text-xl font-bold text-gray-900 mb-5 tracking-tight">{title}</h2>
      {children}
    </div>
  )
}

export default function AdminDashboard() {
  const [orgRequests, setOrgRequests] = useState([])
  const [pendingEvents, setPendingEvents] = useState([])
  const [colleges, setColleges] = useState([])
  const [newCollege, setNewCollege] = useState({ name: '', area: '', emoji: '🏛️' })
  const [collegeMsg, setCollegeMsg] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = () => {
    Promise.all([getOrganizerRequests(), getPendingEvents(), getColleges()])
      .then(([r1, r2, r3]) => { setOrgRequests(r1.data); setPendingEvents(r2.data); setColleges(r3.data) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  const [actionError, setActionError] = useState('')
  const action = async (fn, ...args) => {
    setActionError('')
    try { await fn(...args); refresh() } catch (err) { setActionError(errorMessage(err, 'That action failed.')); refresh() }
  }

  const handleAddCollege = async (e) => {
    e.preventDefault()
    setCollegeMsg('')
    try {
      await createCollege({ ...newCollege })
      setNewCollege({ name: '', area: '', emoji: '🏛️' })
      setCollegeMsg('College added!')
      refresh()
    } catch (err) {
      setCollegeMsg(errorMessage(err, 'Failed to add college.'))
    }
  }

  const ActionButtons = ({ onApprove, onReject }) => (
    <div className="flex gap-2">
      <button onClick={onApprove} className="text-xs font-semibold bg-green-500 text-white px-4 py-2 rounded-full hover:bg-green-600 transition-colors">
        Approve
      </button>
      <button onClick={onReject} className="text-xs font-semibold bg-red-500 text-white px-4 py-2 rounded-full hover:bg-red-600 transition-colors">
        Reject
      </button>
    </div>
  )

  return (
    <div className="min-h-screen bg-[#fafaf9]">
      <Navbar />
      <div className="max-w-5xl mx-auto px-6 pt-28 pb-20">
        {/* Header */}
        <div className="mb-10">
          <span className="text-xs font-semibold text-rose-500 uppercase tracking-widest">Admin</span>
          <h1 className="text-4xl font-bold text-gray-900 mt-2 tracking-tight">Admin Dashboard</h1>
          <p className="text-gray-500 mt-2">Review organiser requests & pending events</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-12">
          {[
            { label: 'Pending Org Requests', value: orgRequests.length,  color: 'bg-orange-50 text-orange-600' },
            { label: 'Pending Events',        value: pendingEvents.length, color: 'bg-violet-50 text-violet-600' },
            { label: 'Colleges',              value: colleges.length,      color: 'bg-teal-50 text-teal-600' },
          ].map((s) => (
            <div key={s.label} className={`${s.color} rounded-2xl p-6`}>
              <div className="text-3xl font-bold mb-1">{s.value}</div>
              <div className="text-sm font-medium opacity-75">{s.label}</div>
            </div>
          ))}
        </div>

        {actionError && (
          <div className="mb-6 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">{actionError}</div>
        )}

        {loading ? (
          <div className="text-gray-400 text-center py-10">Loading…</div>
        ) : (
          <>
            {/* Organiser Requests */}
            <Section title="Organiser Requests">
              {orgRequests.length === 0 ? (
                <p className="text-gray-400 text-sm">No pending requests.</p>
              ) : (
                <div className="space-y-3">
                  {orgRequests.map((req) => (
                    <motion.div
                      key={req.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-white rounded-2xl p-5 flex items-center justify-between gap-4 shadow-sm"
                    >
                      <div>
                        <p className="font-semibold text-gray-900 text-sm">
                          {req.user_name ?? `User #${req.user_id}`}
                          {req.user_email && <span className="font-normal text-gray-400"> · {req.user_email}</span>}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          Requested {new Date(req.requested_at).toLocaleDateString('en-IN')}
                        </p>
                      </div>
                      <ActionButtons
                        onApprove={() => action(approveOrganizer, req.id)}
                        onReject={()  => action(rejectOrganizer,  req.id)}
                      />
                    </motion.div>
                  ))}
                </div>
              )}
            </Section>

            {/* Pending Events */}
            <Section title="Pending Events">
              {pendingEvents.length === 0 ? (
                <p className="text-gray-400 text-sm">No pending events.</p>
              ) : (
                <div className="space-y-3">
                  {pendingEvents.map((event) => (
                    <motion.div
                      key={event.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-white rounded-2xl p-5 flex items-start justify-between gap-4 shadow-sm"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-gray-900">{event.title}</p>
                        <div className="flex flex-wrap gap-3 text-xs text-gray-400 mt-1">
                          {event.category && <span>🏷 {event.category}</span>}
                          {event.location && <span>📍 {event.location}</span>}
                          {event.date && <span>🗓 {new Date(event.date).toLocaleDateString('en-IN')}</span>}
                          <span>💳 {event.is_free ? 'Free' : `₹${event.price}`}</span>
                          {event.college_name && <span>🏛️ {event.college_name}</span>}
                        </div>
                        {event.description && (
                          <p className="text-xs text-gray-500 mt-2 line-clamp-2">{event.description}</p>
                        )}
                      </div>
                      <ActionButtons
                        onApprove={() => action(approveEvent, event.id)}
                        onReject={()  => action(rejectEvent,  event.id)}
                      />
                    </motion.div>
                  ))}
                </div>
              )}
            </Section>

            {/* College Management */}
            <Section title="College Management">
              {/* Add new college */}
              <form onSubmit={handleAddCollege} className="bg-white rounded-2xl p-5 shadow-sm mb-5">
                <p className="text-sm font-semibold text-gray-700 mb-4">Add College</p>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <input
                    required
                    type="text"
                    placeholder="College name *"
                    value={newCollege.name}
                    onChange={(e) => setNewCollege((p) => ({ ...p, name: e.target.value }))}
                    className="col-span-2 px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400/50"
                  />
                  <input
                    type="text"
                    placeholder="Area (e.g. Powai)"
                    value={newCollege.area}
                    onChange={(e) => setNewCollege((p) => ({ ...p, area: e.target.value }))}
                    className="px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400/50"
                  />
                  <input
                    type="text"
                    placeholder="Emoji 🏛️"
                    value={newCollege.emoji}
                    onChange={(e) => setNewCollege((p) => ({ ...p, emoji: e.target.value }))}
                    className="px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400/50"
                  />
                </div>
                {collegeMsg && <p className="text-xs mt-2 text-teal-600">{collegeMsg}</p>}
                <button type="submit" className="mt-3 bg-teal-600 text-white text-sm font-semibold px-5 py-2.5 rounded-full hover:bg-teal-700 transition-colors">
                  + Add College
                </button>
              </form>

              {/* College list */}
              {colleges.length === 0 ? (
                <p className="text-gray-400 text-sm">No colleges yet.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {colleges.map((c) => (
                    <div key={c.id} className="bg-white rounded-2xl p-4 flex items-center justify-between gap-3 shadow-sm">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{c.emoji ?? '🏛️'}</span>
                        <div>
                          <p className="font-semibold text-gray-900 text-sm">{c.name}</p>
                          <p className="text-xs text-gray-400">{c.area} · {c.event_count} event{c.event_count !== 1 ? 's' : ''}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => action(deleteCollege, c.id)}
                        className="text-xs font-semibold text-red-500 hover:text-red-700 transition-colors px-3 py-1.5 rounded-full hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </>
        )}
      </div>
      <Footer />
    </div>
  )
}
