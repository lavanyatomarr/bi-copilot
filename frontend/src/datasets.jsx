import { createContext, useContext, useEffect, useState } from 'react'
import api from './api'

const DatasetContext = createContext(null)

export function DatasetProvider({ children }) {
  const [datasets, setDatasets] = useState([])
  const [activeId, setActiveId] = useState(
    () => Number(localStorage.getItem('activeDataset')) || null
  )
  const [loading, setLoading] = useState(true)

  async function refresh() {
    setLoading(true)
    try {
      const r = await api.get('/datasets')
      setDatasets(r.data)
      // if nothing is active yet, default to the most recent dataset
      if (!activeId && r.data.length) selectDataset(r.data[0].id)
    } finally {
      setLoading(false)
    }
  }

  function selectDataset(id) {
    setActiveId(id)
    localStorage.setItem('activeDataset', String(id))
  }

  useEffect(() => { refresh() }, [])

  const active = datasets.find((d) => d.id === activeId) || null

  return (
    <DatasetContext.Provider
      value={{ datasets, active, activeId, loading, refresh, selectDataset }}
    >
      {children}
    </DatasetContext.Provider>
  )
}

export const useDatasets = () => useContext(DatasetContext)
