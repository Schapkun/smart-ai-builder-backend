"use client"

import { useState, useEffect } from "react"
import { supabase } from "../lib/supabaseClient"

interface Version {
  id: string
  prompt: string
  html: string
  supabase_instructions: string
  timestamp: string
}

export default function Home() {
  const [prompt, setPrompt] = useState("")
  const [supabaseOutput, setSupabaseOutput] = useState("")
  const [version, setVersion] = useState("")
  const [versions, setVersions] = useState<Version[]>([])
  const [htmlPreview, setHtmlPreview] = useState("")
  const [showLiveProject, setShowLiveProject] = useState(true)

  useEffect(() => {
    fetchVersions()
  }, [])

  async function fetchVersions() {
    const { data, error } = await supabase
      .from("versions")
      .select("*")
      .order("timestamp", { ascending: false })
      .limit(20)

    if (error) {
      console.error("Fout bij ophalen versies:", error)
      return
    }
    setVersions(data || [])
  }

  async function handleSubmit() {
    try {
      const res = await fetch("https://smart-ai-builder-backend.onrender.com/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      })

      if (!res.ok) throw new Error("Backend fout: " + res.statusText)
      const data = await res.json()

      console.log("✅ AI HTML output:", data.html)

      setSupabaseOutput(data.supabase_instructions || "-")
      setVersion(data.version_timestamp || "-")
      setHtmlPreview(data.html || "<div style='color:red;'>Geen HTML ontvangen</div>")

      await supabase.from("versions").insert([
        {
          prompt,
          html: data.html,
          supabase_instructions: data.supabase_instructions,
          timestamp: data.version_timestamp,
        },
      ])

      fetchVersions()
    } catch (e: any) {
      alert("Fout bij AI-aanroep: " + e.message)
    }
  }

  async function handleSupabaseExecution() {
    try {
      const res = await fetch("https://smart-ai-builder-backend.onrender.com/execute-supabase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instructions: supabaseOutput }),
      })

      const data = await res.json()
      alert(data.message || "Instructies uitgevoerd.")
    } catch (err: any) {
      alert("Fout bij uitvoeren: " + err.message)
    }
  }

  function selectVersion(v: Version) {
    setPrompt(v.prompt)
    setSupabaseOutput(v.supabase_instructions)
    setVersion(v.timestamp)
    setHtmlPreview(v.html || "<div style='color:red;'>Geen HTML opgeslagen in deze versie</div>")
    console.log("🕓 Geselecteerde versie:", v.timestamp)
  }

  return (
    <div className="flex h-screen bg-zinc-900 text-white">
      {/* Left panel */}
      <aside className="w-1/3 p-6 flex flex-col gap-4 border-r border-zinc-800">
        <h1 className="text-3xl font-extrabold">Loveable Clone</h1>

        <label htmlFor="prompt" className="font-semibold">Prompt</label>
        <textarea
          id="prompt"
          className="flex-grow bg-zinc-800 p-4 rounded resize-none text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-green-500"
          placeholder="Typ hier je prompt..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />

        <button
          className="mt-4 bg-green-600 hover:bg-green-500 px-6 py-3 rounded text-lg font-semibold transition"
          onClick={handleSubmit}
        >
          Execute
        </button>

        <div>
          <h2 className="font-semibold text-sm text-zinc-400 mb-1">Supabase Instructions</h2>
          <pre className="bg-zinc-800 p-3 rounded text-xs whitespace-pre-wrap max-h-28 overflow-y-auto">
            {supabaseOutput}
          </pre>

          <button
            className="mt-2 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded text-sm font-medium transition"
            onClick={handleSupabaseExecution}
          >
            Voer Supabase-instructies uit
          </button>
        </div>

        <div>
          <h2 className="font-semibold text-sm text-zinc-400 mb-1">Version</h2>
          <p className="text-xs text-zinc-300">{version}</p>
        </div>

        <div className="flex-grow overflow-y-auto mt-4 border-t border-zinc-800 pt-4">
          <h2 className="font-semibold text-sm text-zinc-400 mb-2">Version History</h2>
          <ul className="space-y-1 max-h-[220px] overflow-auto">
            {versions.map((v) => (
              <li
                key={v.id}
                className="cursor-pointer px-3 py-2 rounded hover:bg-zinc-700 transition"
                onClick={() => selectVersion(v)}
              >
                <time dateTime={v.timestamp} className="block text-xs text-zinc-500">
                  {new Date(v.timestamp).toLocaleString()}
                </time>
                <p className="truncate text-sm">{v.prompt}</p>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Right panel */}
      <main className="flex-1 p-8 overflow-auto bg-white text-black rounded-l-3xl shadow-inner">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-3xl font-extrabold">Live Project Preview</h1>
          <button
            onClick={() => setShowLiveProject(!showLiveProject)}
            className="bg-zinc-200 hover:bg-zinc-300 text-sm px-4 py-2 rounded"
          >
            {showLiveProject ? "Toon gegenereerde HTML" : "Toon Live Project"}
          </button>
        </div>

        {showLiveProject ? (
          <iframe
            src="https://meester.app"
            title="Live Supabase Project"
            className="w-full h-[85vh] rounded shadow-inner border"
          />
        ) : (
          <div
            className="w-full h-[85vh] rounded border p-4 overflow-auto bg-white text-black"
            dangerouslySetInnerHTML={{ __html: htmlPreview }}
          />
        )}
      </main>
    </div>
  )
}
