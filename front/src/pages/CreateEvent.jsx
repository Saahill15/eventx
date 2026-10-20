import { useState, useEffect } from 'react'
import { errorMessage } from '../lib/errors'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { createEvent, getColleges } from '../services/api'

const CATEGORIES = ['Cultural', 'Technical', 'Sports', 'Music', 'Business', 'Gaming', 'Fashion', 'Literary', 'Technology', 'Finance', 'Design', 'Education']

const Field = ({ label, children }) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
    {children}
  </div>
)

const Input = (props) => (
  <input
    {...props}
    className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-400/50 focus:border-orange-300 transition-all text-sm bg-white"
  />
)

export default function CreateEvent() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    title: '', description: '', location: '', date: '',
    time: '', image_url: '', category: '', price: 0, is_free: true, college_id: '',
  })
  const [colleges, setColleges] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    getColleges().then((r) => setColleges(r.data || [])).catch(() => {})
  }, [])

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = {
        ...form,
        event_type: 'city',
        date: new Date(form.date).toISOString(),
        price: form.is_free ? 0 : parseFloat(form.price),
        college_id: form.college_id ? parseInt(form.college_id) : null,
      }
      await createEvent(payload)
      setSuccess(true)
    } catch (err) {
      setError(errorMessage(err, 'Failed to create event.'))
    } finally {
      setLoading(false)
    }
  }

  if (success) return (
    <div className="min-h-screen bg-[#fafaf9] flex items-center justify-center px-4">
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center max-w-md">
        <span className="text-6xl block mb-6">🎉</span>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Event Submitted!</h2>
        <p className="text-gray-500 mb-8">Your event is pending admin approval. We'll notify you once it's live.</p>
        <div className="flex gap-3 justify-center">
          <Link to="/organizer" className="bg-gray-900 text-white font-semibold px-6 py-3 rounded-full hover:bg-gray-700 transition-colors">
            Dashboard
          </Link>
          <Link to="/discover" className="border border-gray-200 text-gray-700 font-semibold px-6 py-3 rounded-full hover:bg-gray-50 transition-colors">
            Discover Events
          </Link>
        </div>
      </motion.div>
    </div>
  )

  return (
    <div className="min-h-screen bg-[#fafaf9]">
      <Navbar />
      <div className="max-w-2xl mx-auto px-6 pt-28 pb-20">
        <div className="mb-10">
          <span className="text-xs font-semibold text-orange-500 uppercase tracking-widest">Organiser</span>
          <h1 className="text-4xl font-bold text-gray-900 mt-2 tracking-tight">Create Event</h1>
          <p className="text-gray-500 mt-2">Fill in the details — it'll be reviewed by the admin team.</p>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">
            {error}
          </div>
        )}

        <motion.form
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          onSubmit={handleSubmit}
          className="bg-white rounded-3xl shadow-[0_2px_40px_rgba(0,0,0,0.07)] p-8 space-y-5"
        >
          <Field label="Event Title *">
            <Input type="text" value={form.title} onChange={(e) => set('title', e.target.value)} required placeholder="e.g. Annual Tech Summit 2026" />
          </Field>

          <Field label="Description">
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              rows={3}
              placeholder="Describe your event…"
              className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-400/50 focus:border-orange-300 transition-all text-sm resize-none"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Date *">
              <Input type="date" value={form.date} onChange={(e) => set('date', e.target.value)} required />
            </Field>
            <Field label="Time">
              <Input type="time" value={form.time} onChange={(e) => set('time', e.target.value)} />
            </Field>
          </div>

          <Field label="Location">
            <Input type="text" value={form.location} onChange={(e) => set('location', e.target.value)} placeholder="e.g. IIT Bombay, Powai" />
          </Field>

          <Field label="Category">
            <select
              value={form.category}
              onChange={(e) => set('category', e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 focus:outline-none focus:ring-2 focus:ring-orange-400/50 focus:border-orange-300 transition-all text-sm bg-white"
            >
              <option value="">Select category</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>

          <Field label="Cover Image URL (optional)">
            <Input type="url" value={form.image_url} onChange={(e) => set('image_url', e.target.value)} placeholder="https://…" />
          </Field>

          <Field label="College (optional)">
            <select
              value={form.college_id}
              onChange={(e) => set('college_id', e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 focus:outline-none focus:ring-2 focus:ring-orange-400/50 focus:border-orange-300 transition-all text-sm bg-white"
            >
              <option value="">No college affiliation</option>
              {colleges.map((c) => <option key={c.id} value={c.id}>{c.emoji} {c.name} — {c.area}</option>)}
            </select>
          </Field>

          {/* Pricing */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">Pricing</label>
            <div className="flex gap-3 mb-3">
              {[true, false].map((isFree) => (
                <button
                  key={String(isFree)}
                  type="button"
                  onClick={() => set('is_free', isFree)}
                  className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border-2 transition-all ${
                    form.is_free === isFree
                      ? 'border-orange-400 bg-orange-50 text-orange-700'
                      : 'border-gray-100 bg-white text-gray-600 hover:border-gray-200'
                  }`}
                >
                  {isFree ? 'Free' : 'Paid'}
                </button>
              ))}
            </div>
            {!form.is_free && (
              <Field label="Price (₹)">
                <Input type="number" value={form.price} onChange={(e) => set('price', e.target.value)} min={1} placeholder="e.g. 299" />
              </Field>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gray-900 text-white font-semibold py-4 rounded-2xl hover:bg-gray-700 transition-all active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'Submitting…' : 'Submit for Review'}
          </button>
        </motion.form>
      </div>
      <Footer />
    </div>
  )
}
