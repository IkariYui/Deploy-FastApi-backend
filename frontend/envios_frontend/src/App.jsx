import React, { useState } from 'react'


export default function App() {
const [file, setFile] = useState(null)
const [loading, setLoading] = useState(false)
const [message, setMessage] = useState('')

const handleSubmit = async (e) => {
e.preventDefault()
if (!file) return setMessage('Selecciona primero un archivo .xlsx')


setLoading(true)
setMessage('')


const formData = new FormData()
formData.append('file', file)

const API_URL = import.meta.env.VITE_API_URL; 

try {
const res = await fetch(`${API_URL}/procesar`, {
method: 'POST',
body: formData,
})


if (!res.ok) {
const err = await res.json()
setMessage('Error: ' + (err.detail || res.statusText))
setLoading(false)
return
}
// Descargar archivo retornado
const blob = await res.blob()
const url = window.URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url
// intenta obtener filename desde headers
const disposition = res.headers.get('Content-Disposition') || ''
const match = disposition.match(/filename="?(.+?)"?$/)
const filename = match ? match[1] : 'resumen.xlsx'
a.download = filename
document.body.appendChild(a)
a.click()
a.remove()
window.URL.revokeObjectURL(url)
setMessage('Descarga lista: ' + filename)
} catch (err) {
console.error(err)
setMessage('Error en la conexión con la API')
} finally {
setLoading(false)
}
}
return (
<div className="min-h-screen flex items-center justify-center p-4">
<div className="max-w-xl w-full bg-white rounded-2xl shadow p-6">
<h1 className="text-xl font-semibold mb-4">Procesar Excel de envíos</h1>


<form onSubmit={handleSubmit}>
<input
type="file"
accept=".xlsx,.xls"
onChange={(e) => setFile(e.target.files[0])}
className="mb-4"
/>

<div className="flex gap-2">
<button
type="submit"
disabled={loading}
className="px-4 py-2 rounded bg-blue-600 text-white"
>
{loading ? 'Procesando...' : 'Subir y procesar'}
</button>

<button
type="button"
onClick={() => { setFile(null); setMessage('') }}
className="px-4 py-2 rounded border"
>
  Limpiar
</button>
</div>
</form>
{message && <p className="mt-4">{message}</p>}
<p className="mt-2 text-sm text-gray-500">La API espera una hoja llamada "result"; si no existe, intenta con la primera hoja.</p>
</div>
</div>
)
}
