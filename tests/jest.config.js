/**
 * Jest configuration for Echoes frontend testing
 */

module.exports = {
  // Test environment
  testEnvironment: 'jsdom',
  
  // Setup files
  setupFilesAfterEnv: ['<rootDir>/tests/frontend/setup.js'],
  
  // Module paths
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@/components/(.*)$': '<rootDir>/src/components/$1',
    '^@/contexts/(.*)$': '<rootDir>/src/contexts/$1',
    '^@/services/(.*)$': '<rootDir>/src/services/$1',
    '^@/utils/(.*)$': '<rootDir>/src/utils/$1',
    '^@/hooks/(.*)$': '<rootDir>/src/hooks/$1',
  },
  
  // File patterns
  testMatch: [
    '<rootDir>/tests/frontend/**/*.test.{js,jsx,ts,tsx}',
    '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
  ],
  
  // Coverage settings
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/index.js',
    '!src/serviceWorker.js',
    '!src/**/*.d.ts',
    '!src/**/*.stories.{js,jsx,ts,tsx}',
  ],
  
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  
  coverageReporters: [
    'text',
    'lcov',
    'html',
    'json-summary',
  ],
  
  // Module file extensions
  moduleFileExtensions: [
    'js',
    'jsx',
    'ts',
    'tsx',
    'json',
    'node',
  ],
  
  // Transform files
  transform: {
    '^.+\\.(js|jsx|ts|tsx)$': 'babel-jest',
    '^.+\\.css$': 'identity-obj-proxy',
    '^.+\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': 'jest-transform-stub',
  },
  
  // Module directories
  moduleDirectories: ['node_modules', '<rootDir>/src'],
  
  // Clear mocks
  clearMocks: true,
  
  // Verbose output
  verbose: true,
  
  // Test timeout
  testTimeout: 10000,
  
  // Global setup/teardown
  globalSetup: '<rootDir>/tests/frontend/globalSetup.js',
  globalTeardown: '<rootDir>/tests/frontend/globalTeardown.js',
  
  // Watch plugins
  watchPlugins: [
    'jest-watch-typeahead/filename',
    'jest-watch-typeahead/testname',
  ],
  
  // Reporters
  reporters: [
    'default',
    ['jest-junit', {
      outputDirectory: 'test-results/frontend',
      outputName: 'junit.xml',
      suiteName: 'Frontend Tests',
    }],
    ['jest-html-reporters', {
      publicPath: 'test-results/frontend',
      filename: 'report.html',
      expand: true,
    }],
  ],
  
  // Error handling
  errorOnDeprecated: true,
  
  // Parallel execution
  maxWorkers: '50%',
};