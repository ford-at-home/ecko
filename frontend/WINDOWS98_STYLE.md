# Windows 98 Style Guide for Echoes

This frontend has been fully refactored to use **98.css**, a CSS library that recreates the Windows 98 aesthetic.

## Overview

The Echoes frontend now features:
- Classic Windows 98 window frames with title bars
- Retro buttons with 3D beveled edges
- Windows 98 style form controls (dropdowns, inputs, etc.)
- Status bar at the bottom of the application
- Menu bar navigation
- Teal desktop background (#008080)

## Key Components

### Layout Structure
- **Window frames**: All content is wrapped in `.window` elements
- **Title bars**: Each window has a `.title-bar` with controls
- **Window body**: Content goes inside `.window-body`
- **Status bar**: Bottom navigation with `.status-bar`

### Custom Styles
Located in `/frontend/src/index.css`:
- **Emotion tags**: Custom Windows 98 style tags for emotions
- **Record button**: Large circular button for audio recording
- **Scrollbars**: Custom styled to match Windows 98 aesthetic
- **Form inputs**: Enhanced with Windows 98 styling

## Removed Dependencies
- Tailwind CSS
- Autoprefixer
- PostCSS
- @headlessui/react
- @heroicons/react

## Usage
The app automatically applies Windows 98 styling through:
1. Import of 98.css in index.css
2. Use of semantic 98.css classes
3. Custom styles for app-specific components

## Building
```bash
cd frontend
npm install
npm run build
npm run preview
```

The application is now a nostalgic Windows 98-styled audio journaling app!