// Adds DOM matchers like toBeDisabled() / toBeInTheDocument() to expect().
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Unmount whatever a test rendered so the next test starts from an empty page.
afterEach(() => cleanup())
