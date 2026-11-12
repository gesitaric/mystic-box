import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/theme.css'
import Root from './Root.jsx'
import { startPointerParallax } from './pointerParallax.js'

startPointerParallax()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
