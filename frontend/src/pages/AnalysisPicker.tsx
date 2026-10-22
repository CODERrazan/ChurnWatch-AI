import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, PageHeader } from '../components/ui'

export default function AnalysisPicker() {
  const nav = useNavigate()
  const [id, setId] = useState('')
  const [date, setDate] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!id.trim()) return
    nav(`/customers/${encodeURIComponent(id.trim())}/analysis${date ? `?snapshot_date=${date}` : ''}`)
  }
  return (
    <>
      <PageHeader title="AI analysis" subtitle="Choose a customer to explain. You can also open a customer from the explorer and select Run AI analysis." />
      <Card>
        <form className="tools" onSubmit={submit}>
          <label>Customer ID
            <input className="input" required value={id} onChange={(e) => setId(e.target.value)} placeholder="e.g. CUST_00022" />
          </label>
          <label>Snapshot date (optional)
            <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <button className="btn primary" type="submit">Continue</button>
        </form>
        <p className="caption">Leave the date empty to use the latest snapshot. Nothing is sent to the model until you select Analyze on the next page.</p>
      </Card>
    </>
  )
}
