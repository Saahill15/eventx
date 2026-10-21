import { useState, useEffect } from 'react'
import { Field, Input, Select, ErrorBanner, PrimaryButton } from '../../components/ui'
import { getFestMembers, addFestMember, removeFestMember } from '../../services/api'
import { useAuth } from '../../context/AuthContext'
import { errorMessage } from '../../lib/errors'

const ROLE_LABEL = { owner: 'Festival director', core: 'Core team', volunteer: 'Volunteer' }
const ROLE_HELP = {
  core: 'Can manage events, registrations and the team',
  volunteer: 'Can help on the day. No management access',
}

export default function TeamTab({ slug, myRole }) {
  const { user } = useAuth()
  const [members, setMembers] = useState([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('volunteer')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = () => getFestMembers(slug).then((r) => setMembers(r.data)).catch((err) => setError(errorMessage(err)))
  useEffect(() => { load() }, [slug])

  const canGrantCore = myRole === 'owner' || myRole === 'admin'

  const add = async (e) => {
    e.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      await addFestMember(slug, { email: email.trim(), role })
      setEmail('')
      setNotice('Added to your team.')
      load()
    } catch (err) {
      setError(errorMessage(err, 'Could not add that person.'))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (member) => {
    if (!window.confirm(`Remove ${member.user_name ?? 'this person'} from the team?`)) return
    setError(''); setNotice('')
    try {
      await removeFestMember(slug, member.user_id)
      load()
    } catch (err) {
      setError(errorMessage(err, 'Could not remove that person.'))
    }
  }

  const canRemove = (m) => {
    if (m.user_id === user?.id) return false
    if (m.role === 'owner') return myRole === 'admin'
    if (m.role === 'core') return canGrantCore
    return true
  }

  const order = { owner: 0, core: 1, volunteer: 2 }
  const sorted = [...members].sort((a, b) => order[a.role] - order[b.role])

  return (
    <div className="space-y-8">
      <form onSubmit={add} className="bg-white rounded-3xl shadow-sm p-6 space-y-4">
        <h2 className="font-bold text-gray-900">Add a team member</h2>
        <ErrorBanner>{error}</ErrorBanner>
        {notice && <div className="bg-green-50 border border-green-100 text-green-700 text-sm px-4 py-3 rounded-xl">{notice}</div>}
        <div className="grid sm:grid-cols-[1fr_220px] gap-4">
          <Field label="Their EventX email" hint="They need an EventX account first. Ask them to sign up.">
            <Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@college.edu" />
          </Field>
          <Field label="Role" hint={ROLE_HELP[role]}>
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="volunteer">Volunteer</option>
              {canGrantCore && <option value="core">Core team</option>}
            </Select>
          </Field>
        </div>
        <PrimaryButton type="submit" disabled={busy}>{busy ? 'Adding…' : 'Add to team'}</PrimaryButton>
      </form>

      <div className="space-y-3">
        {sorted.map((m) => (
          <div key={m.id} className="bg-white rounded-2xl p-4 shadow-sm flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="font-semibold text-gray-900 truncate">{m.user_name}{m.user_id === user?.id ? ' (you)' : ''}</p>
              <p className="text-xs text-gray-400 truncate">{m.user_email}</p>
            </div>
            <div className="flex items-center gap-4 flex-shrink-0">
              <span className="text-xs font-semibold text-violet-600 bg-violet-50 border border-violet-100 px-2.5 py-1 rounded-full">{ROLE_LABEL[m.role] ?? m.role}</span>
              {canRemove(m) && (
                <button onClick={() => remove(m)} className="text-xs font-semibold text-red-500 hover:text-red-700">Remove</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
