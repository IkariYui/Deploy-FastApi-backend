import React, { useState } from 'react'
import { Package, Linkedin, Github } from 'lucide-react'

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
    const API_URL = import.meta.env.VITE_API_URL

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

      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const disposition = res.headers.get('Content-Disposition') || ''
      const match = disposition.match(/filename="?(.+?)"?$/)
      const filename = match ? match[1] : 'resumen.xlsx'
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      setMessage('✅ Descarga lista: ' + filename)
    } catch (err) {
      console.error(err)
      setMessage('Error en la conexión con la API')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900 text-white">
      {/* Contenido principal centrado en pantalla */}
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-lg w-full bg-gray-800 rounded-2xl shadow-2xl p-8 text-center border border-gray-700">
          <div className="flex items-center justify-center gap-3 mb-6">
            <Package size={48} className="text-yellow-400" />
            <h1 className="text-3xl font-extrabold">Procesar Excel de envíos</h1>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="flex justify-center mb-4">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setFile(e.target.files[0])}
                className="text-sm text-gray-300 
                          file:mr-4 file:py-2 file:px-4 file:rounded-lg 
                          file:border-0 file:text-sm file:font-semibold 
                          file:bg-yellow-500 file:text-gray-900 
                          hover:file:bg-yellow-400"
              />
            </div>

            <div className="flex justify-center gap-4">
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 
                           text-white font-medium disabled:opacity-50"
              >
                {loading ? 'Procesando...' : 'Subir y procesar'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setFile(null)
                  setMessage('')
                }}
                className="px-5 py-2 rounded-lg bg-gray-600 hover:bg-gray-500 font-medium"
              >
                Limpiar
              </button>
            </div>
          </form>

          {message && <p className="mt-5 text-sm text-yellow-400">{message}</p>}

          <p className="mt-4 text-sm text-gray-400">
            La API espera una hoja llamada <b>"result"</b>. Si no existe, usará la primera hoja disponible.
          </p>
        </div>
      </main>

      {/* Footer diferenciado */}
      <footer className="bg-black py-5 border-t border-gray-700 text-center">
        <div className="flex justify-center gap-6 mb-3">
          <a
            href="https://www.linkedin.com/in/juan-guillermo-cuartas-valderrrama-7939841a0"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 hover:text-yellow-400 transition"
          >
            <Linkedin size={20} />
            <span>LinkedIn</span>
          </a>
          <a
            href="https://github.com/IkariYui"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 hover:text-yellow-400 transition"
          >
            <Github size={20} />
            <span>GitHub</span>
          </a>
        </div>

        <p className="text-xs text-gray-600">
          © {new Date().getFullYear()} Todos los derechos reservados
        </p>
      </footer>
    </div>
  )
}
