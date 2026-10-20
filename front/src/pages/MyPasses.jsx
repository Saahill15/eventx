import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { QRCodeSVG } from 'qrcode.react'
import { getMyPasses, getEvent, getMyFestPasses, getMyRegistrations } from '../services/api'

function PassCard({ pass }) {
  const [event, setEvent] = useState(null)

  useEffect(() => {
    getEvent(pass.event_id).then((r) => setEvent(r.data)).catch(() => {})
  }, [pass.event_id])

  const dateStr = new Date(pass.created_at).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-3xl overflow-hidden shadow-[0_2px_20px_rgba(0,0,0,0.08)]"
    >
      {/* Top  */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-700 px-6 py-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold text-orange-400 uppercase tracking-widest mb-1">EventX Pass</p>
          <h3 className="text-white font-bold text-lg leading-tight">
            {event ? event.title : 'Loading…'}
          </h3>
          {event && <p className="text-gray-400 text-xs mt-1">📍 {event.location ?? 'TBD'}</p>}
        </div>
        <span className={`text-xs font-bold px-3 py-1.5 rounded-full flex-shrink-0 ${
          pass.payment_status === 'free'
            ? 'bg-green-500/20 text-green-300 border border-green-500/30'
            : 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30'
        }`}>
          {pass.payment_status === 'free' ? 'FREE' : pass.payment_status.toUpperCase()}
        </span>
      </div>

      {/* Bottom */}
      <div className="px-6 py-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs text-gray-400 mb-1">Pass Code</p>
          <p className="font-mono font-bold text-gray-900 text-base tracking-widest bg-gray-100 px-3 py-2 rounded-xl">
            {pass.pass_code}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-400 mb-1">Registered</p>
          <p className="text-sm font-medium text-gray-700">{dateStr}</p>
        </div>
      </div>
    </motion.div>
  )
}

const REG_STATUS_STYLES = {
  approved: 'bg-green-50 text-green-600 border-green-100',
  pending:  'bg-yellow-50 text-yellow-600 border-yellow-100',
  rejected: 'bg-red-50 text-red-600 border-red-100',
}

function RegistrationRow({ registration }) {
  const [event, setEvent] = useState(null)
  useEffect(() => {
    getEvent(registration.event_id).then((r) => setEvent(r.data)).catch(() => {})
  }, [registration.event_id])
  return (
    <li className="flex items-center justify-between gap-3 py-2.5">
      <Link to={`/events/${registration.event_id}`} className="text-sm font-medium text-gray-800 hover:text-orange-600 truncate">
        {event ? event.title : 'Event'}
      </Link>
      <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border capitalize flex-shrink-0 ${REG_STATUS_STYLES[registration.approval_status] ?? REG_STATUS_STYLES.pending}`}>
        {registration.approval_status}
      </span>
    </li>
  )
}

function FestPassCard({ pass, registrations }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-3xl overflow-hidden shadow-[0_2px_20px_rgba(0,0,0,0.08)]"
    >
      <div className="bg-gradient-to-r from-violet-900 to-indigo-800 px-6 py-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold text-violet-300 uppercase tracking-widest mb-1">Fest Entry Pass</p>
          <Link to={`/fest/${pass.fest_slug}`} className="text-white font-bold text-lg leading-tight hover:underline">
            {pass.fest_name ?? 'Fest'}
          </Link>
        </div>
        <span className={`text-xs font-bold px-3 py-1.5 rounded-full flex-shrink-0 border ${
          pass.status !== 'approved'
            ? 'bg-red-500/20 text-red-300 border-red-500/30'
            : pass.checked_in
              ? 'bg-gray-500/30 text-gray-200 border-gray-400/30'
              : 'bg-green-500/20 text-green-300 border-green-500/30'
        }`}>
          {pass.status !== 'approved' ? 'BLOCKED' : pass.checked_in ? 'USED' : 'VALID'}
        </span>
      </div>
      <div className="px-6 py-5 flex flex-col sm:flex-row gap-6 items-center sm:items-start">
        <div className="bg-white p-3 rounded-2xl border border-gray-100 flex-shrink-0">
          <QRCodeSVG value={pass.qr_code} size={132} />
        </div>
        <div className="flex-1 w-full min-w-0">
          <p className="text-xs text-gray-400 mb-1">Your registrations</p>
          {registrations.length === 0 ? (
            <p className="text-sm text-gray-500">None yet. Open the fest page to register for events.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {registrations.map((r) => <RegistrationRow key={r.id} registration={r} />)}
            </ul>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default function MyPasses() {
  const [passes, setPasses] = useState([])
  const [festPasses, setFestPasses] = useState([])
  const [registrations, setRegistrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  useEffect(() => {
    Promise.all([getMyPasses(), getMyFestPasses(), getMyRegistrations()])
      .then(([p, fp, regs]) => { setPasses(p.data); setFestPasses(fp.data); setRegistrations(regs.data) })
      .catch(() => setError('Failed to load passes.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-[#fafaf9]">
      <Navbar />
      <div className="max-w-3xl mx-auto px-6 pt-28 pb-20">
        <div className="mb-10">
          <span className="text-xs font-semibold text-orange-500 uppercase tracking-widest">Wallet</span>
          <h1 className="text-4xl font-bold text-gray-900 mt-2 tracking-tight">My Passes</h1>
          <p className="text-gray-500 mt-2">Your fest entry passes and event registrations</p>
        </div>

        {loading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="bg-white rounded-3xl h-36 animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <p className="text-red-500 text-center py-10">{error}</p>
        ) : passes.length === 0 && festPasses.length === 0 ? (
          <div className="text-center py-20">
            <span className="text-5xl block mb-4">🎫</span>
            <p className="text-gray-500 mb-4">No passes yet.</p>
            <Link to="/fests" className="bg-gray-900 text-white font-semibold px-6 py-3 rounded-full hover:bg-gray-700 transition-colors inline-block">
              Browse College Fests →
            </Link>
          </div>
        ) : (
          <div className="space-y-5">
            {festPasses.map((fp) => (
              <FestPassCard
                key={`fest-${fp.id}`}
                pass={fp}
                registrations={registrations.filter((r) => r.fest_pass_id === fp.id)}
              />
            ))}
            {passes.map((pass) => <PassCard key={pass.id} pass={pass} />)}
          </div>
        )}
      </div>
      <Footer />
    </div>
  )
}
