import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { migrateStorage } from './storageKeys'

migrateStorage()                    // move data saved under the pre-Compass key names before anything reads it

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
