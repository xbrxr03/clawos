/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { ApprovalOverlay } from './overlays/ApprovalOverlay'

// Tauri opens the approval overlay at index.html#/overlay/approval. Detect
// that here and render the minimal overlay UI instead of the full dashboard
// shell — keeps the overlay window light and free of dashboard chrome.
const isApprovalOverlay =
  typeof window !== 'undefined' &&
  (window.location.hash || '').startsWith('#/overlay/approval')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isApprovalOverlay ? <ApprovalOverlay /> : <App />}
  </StrictMode>
)
