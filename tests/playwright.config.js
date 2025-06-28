/**
 * Playwright configuration for Echoes E2E testing
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // Test directory
  testDir: './e2e',
  
  // Timeout settings
  timeout: 30000,
  expect: {
    timeout: 5000,
  },
  
  // Test execution
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'test-results/e2e/html-report' }],
    ['junit', { outputFile: 'test-results/e2e/junit.xml' }],
    ['json', { outputFile: 'test-results/e2e/results.json' }],
    ['line'],
  ],
  
  // Global test settings
  use: {
    // Base URL
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    
    // Browser settings
    headless: process.env.CI ? true : false,
    viewport: { width: 1280, height: 720 },
    
    // Screenshots and videos
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    
    // Permissions
    permissions: ['microphone', 'geolocation'],
    geolocation: { latitude: 40.7829, longitude: -73.9654 }, // Central Park
    
    // Network settings
    ignoreHTTPSErrors: true,
    acceptDownloads: true,
    
    // Context options
    locale: 'en-US',
    timezoneId: 'America/New_York',
  },
  
  // Test projects for different browsers and scenarios
  projects: [
    // Desktop browsers
    {
      name: 'Desktop Chrome',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'Desktop Firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'Desktop Safari',
      use: { ...devices['Desktop Safari'] },
    },
    
    // Mobile browsers
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
    
    // Tablet
    {
      name: 'Tablet',
      use: { ...devices['iPad Pro'] },
    },
    
    // Accessibility testing
    {
      name: 'Accessibility',
      use: { 
        ...devices['Desktop Chrome'],
        // Force reduced motion for accessibility tests
        reducedMotion: 'reduce',
      },
      testMatch: '**/accessibility.spec.js',
    },
    
    // Performance testing
    {
      name: 'Performance',
      use: {
        ...devices['Desktop Chrome'],
        // Network throttling for performance tests
        launchOptions: {
          args: ['--disable-web-security', '--disable-features=VizDisplayCompositor'],
        },
      },
      testMatch: '**/performance.spec.js',
    },
    
    // Security testing
    {
      name: 'Security',
      use: {
        ...devices['Desktop Chrome'],
        // Enable additional security features
        extraHTTPHeaders: {
          'X-Test-Security': 'enabled',
        },
      },
      testMatch: '**/security.spec.js',
    },
  ],
  
  // Development server
  webServer: process.env.CI ? undefined : {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
  
  // Output directory
  outputDir: 'test-results/e2e/artifacts',
  
  // Global setup and teardown
  globalSetup: require.resolve('./e2e/global-setup.js'),
  globalTeardown: require.resolve('./e2e/global-teardown.js'),
  
  // Test metadata
  metadata: {
    testType: 'e2e',
    application: 'Echoes Audio Time Machine',
    environment: process.env.NODE_ENV || 'test',
    version: process.env.npm_package_version || '1.0.0',
  },
});